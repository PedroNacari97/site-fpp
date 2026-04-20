import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from gestao.utils import normalize_cpf

from .models import LoginGuard, SecurityEvent


SUPERADMIN_MFA_SESSION_KEY = "superadmin_mfa_pending"


def get_client_ip(request):
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "").strip()[:45]


def get_user_agent(request):
    return (request.META.get("HTTP_USER_AGENT") or "").strip()[:255]


def get_request_url(request, *, max_length=500):
    """URL absoluta da requisicao (com esquema + host + path + query).

    Fallback para `request.path` quando o request nao expoe `build_absolute_uri`.
    Limitada a `max_length` caracteres — suficiente para armazenar em
    CharField/URLField sem estourar. Usada como evidencia forense do ponto de
    origem de aceites/consentimentos (LGPD art. 8).
    """
    if request is None:
        return ""
    try:
        url = request.build_absolute_uri()
    except Exception:
        url = getattr(request, "path", "") or ""
    return (url or "")[:max_length]


def normalize_login_identifier(identifier, scope="default"):
    raw_identifier = (identifier or "").strip()
    if scope == "superadmin":
        return raw_identifier.lower()
    normalized_cpf = normalize_cpf(raw_identifier)
    return normalized_cpf or raw_identifier.lower()


def log_security_event(event_type, *, request=None, user=None, identifier="", details=None):
    SecurityEvent.objects.create(
        user=user,
        event_type=event_type,
        identifier=(identifier or "")[:150],
        ip_address=get_client_ip(request) if request else "",
        user_agent=get_user_agent(request) if request else "",
        details=json.dumps(details or {}, ensure_ascii=True),
    )


def _get_login_guard(identifier, ip_address, scope):
    return LoginGuard.objects.get_or_create(
        identifier=identifier or "<vazio>",
        ip_address=ip_address or "",
        scope=scope,
    )[0]


def _ip_only_identifier():
    return "<ip>"


def _ip_only_scope(scope):
    return f"{scope}:ip"


def get_lockout_remaining_seconds(identifier, ip_address, scope):
    guard = LoginGuard.objects.filter(
        identifier=identifier or "<vazio>",
        ip_address=ip_address or "",
        scope=scope,
    ).first()
    if not guard or not guard.locked_until:
        return 0

    now = timezone.now()
    if guard.locked_until <= now:
        guard.failed_attempts = 0
        guard.locked_until = None
        guard.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        return 0

    return int((guard.locked_until - now).total_seconds())


def is_login_allowed(request, identifier, scope):
    normalized_identifier = normalize_login_identifier(identifier, scope=scope)
    ip_address = get_client_ip(request)
    seconds = max(
        get_lockout_remaining_seconds(normalized_identifier, ip_address, scope),
        get_lockout_remaining_seconds(_ip_only_identifier(), ip_address, _ip_only_scope(scope)),
    )
    return seconds == 0, seconds


def _register_guard_failure(
    request,
    *,
    identifier,
    scope,
    limit,
    lockout_minutes,
    event_prefix,
    user=None,
    reason="invalid_credentials",
):
    guard = _get_login_guard(identifier, get_client_ip(request), scope)
    guard.failed_attempts += 1
    details = {
        "scope": scope,
        "failed_attempts": guard.failed_attempts,
        "reason": reason,
    }

    if guard.failed_attempts >= limit:
        guard.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
        details["locked_until"] = guard.locked_until.isoformat()
        log_security_event(
            f"{event_prefix}_locked",
            request=request,
            user=user,
            identifier=identifier,
            details=details,
        )
    else:
        log_security_event(
            f"{event_prefix}_failed",
            request=request,
            user=user,
            identifier=identifier,
            details=details,
        )

    guard.save(update_fields=["failed_attempts", "locked_until", "updated_at"])


def register_login_failure(request, identifier, scope, *, user=None, reason="invalid_credentials"):
    normalized_identifier = normalize_login_identifier(identifier, scope=scope)
    _register_guard_failure(
        request,
        identifier=normalized_identifier or "<vazio>",
        scope=scope,
        limit=settings.SECURITY_LOGIN_FAILURE_LIMIT,
        lockout_minutes=settings.SECURITY_LOGIN_LOCKOUT_MINUTES,
        event_prefix="login",
        user=user,
        reason=reason,
    )
    _register_guard_failure(
        request,
        identifier=_ip_only_identifier(),
        scope=_ip_only_scope(scope),
        limit=settings.SECURITY_LOGIN_FAILURE_LIMIT,
        lockout_minutes=settings.SECURITY_LOGIN_LOCKOUT_MINUTES,
        event_prefix="login_ip",
        user=user,
        reason=reason,
    )


def reset_login_failures(request, identifier, scope):
    normalized_identifier = normalize_login_identifier(identifier, scope=scope)
    LoginGuard.objects.filter(
        identifier=normalized_identifier or "<vazio>",
        ip_address=get_client_ip(request),
        scope=scope,
    ).delete()


def is_security_action_allowed(request, identifier, scope):
    normalized_identifier = normalize_login_identifier(identifier, scope=scope)
    ip_address = get_client_ip(request)
    seconds = max(
        get_lockout_remaining_seconds(normalized_identifier, ip_address, scope),
        get_lockout_remaining_seconds(_ip_only_identifier(), ip_address, _ip_only_scope(scope)),
    )
    return seconds == 0, seconds


def register_security_action_attempt(
    request,
    identifier,
    scope,
    *,
    limit,
    lockout_minutes,
    event_prefix,
    reason="request",
):
    normalized_identifier = normalize_login_identifier(identifier, scope=scope)
    _register_guard_failure(
        request,
        identifier=normalized_identifier or "<vazio>",
        scope=scope,
        limit=limit,
        lockout_minutes=lockout_minutes,
        event_prefix=event_prefix,
        reason=reason,
    )
    _register_guard_failure(
        request,
        identifier=_ip_only_identifier(),
        scope=_ip_only_scope(scope),
        limit=limit,
        lockout_minutes=lockout_minutes,
        event_prefix=f"{event_prefix}_ip",
        reason=reason,
    )


def format_lockout_message(seconds):
    total_minutes = max(1, (seconds + 59) // 60)
    return (
        "Muitas tentativas de acesso. Aguarde "
        f"{total_minutes} minuto(s) antes de tentar novamente."
    )


def mask_email(email):
    local_part, _, domain = (email or "").partition("@")
    if not local_part or not domain:
        return email
    masked_local = local_part[:2] + "*" * max(len(local_part) - 2, 1)
    return f"{masked_local}@{domain}"


def _build_mfa_hash(code):
    return salted_hmac("superadmin-mfa", code).hexdigest()


def clear_superadmin_mfa(request):
    request.session.pop(SUPERADMIN_MFA_SESSION_KEY, None)
    request.session.modified = True


def get_pending_superadmin_mfa(request):
    challenge = request.session.get(SUPERADMIN_MFA_SESSION_KEY)
    if not challenge:
        return None
    expires_at = challenge.get("expires_at")
    if not expires_at:
        clear_superadmin_mfa(request)
        return None
    try:
        expires_at_dt = timezone.datetime.fromisoformat(expires_at)
    except ValueError:
        clear_superadmin_mfa(request)
        return None
    if timezone.is_naive(expires_at_dt):
        expires_at_dt = timezone.make_aware(expires_at_dt, timezone.get_current_timezone())
    if expires_at_dt <= timezone.now():
        log_security_event(
            "superadmin_mfa_expired",
            request=request,
            identifier=challenge.get("identifier", ""),
            details={"user_id": challenge.get("user_id")},
        )
        clear_superadmin_mfa(request)
        return None
    challenge["masked_email"] = challenge.get("masked_email") or mask_email(challenge.get("email", ""))
    return challenge


def start_superadmin_mfa_challenge(request, user, identifier):
    if not settings.SUPERADMIN_MFA_ENABLED:
        return True, ""

    email = (user.email or "").strip()
    if not email:
        log_security_event(
            "superadmin_mfa_missing_email",
            request=request,
            user=user,
            identifier=identifier,
        )
        return False, "O superadmin precisa ter um email cadastrado para concluir o acesso."

    verification_code = f"{secrets.randbelow(1000000):06d}"
    expires_at = timezone.now() + timedelta(
        minutes=settings.SUPERADMIN_MFA_CODE_TTL_MINUTES
    )
    request.session[SUPERADMIN_MFA_SESSION_KEY] = {
        "user_id": user.id,
        "identifier": normalize_login_identifier(identifier, scope="superadmin"),
        "email": email,
        "masked_email": mask_email(email),
        "code_hash": _build_mfa_hash(verification_code),
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
    }
    request.session.modified = True

    try:
        send_mail(
            subject="Codigo de verificacao NCFly",
            message=(
                "Use o codigo abaixo para concluir o acesso de superadmin na NCFly:\n\n"
                f"{verification_code}\n\n"
                f"Valido ate {timezone.localtime(expires_at):%d/%m/%Y %H:%M}."
            ),
            from_email=getattr(settings, "SUPPORT_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        log_security_event(
            "superadmin_mfa_send_error",
            request=request,
            user=user,
            identifier=identifier,
            details={"error": str(exc.__class__.__name__)},
        )
        clear_superadmin_mfa(request)
        return False, "Nao foi possivel enviar o codigo de verificacao agora."
    log_security_event(
        "superadmin_mfa_sent",
        request=request,
        user=user,
        identifier=identifier,
        details={"expires_at": expires_at.isoformat()},
    )
    return True, ""


def verify_superadmin_mfa_code(request, raw_code):
    challenge = get_pending_superadmin_mfa(request)
    if not challenge:
        return None, "Sua verificacao expirou. Faca login novamente."

    normalized_code = "".join(ch for ch in str(raw_code or "") if ch.isdigit())[:6]
    attempts = int(challenge.get("attempts") or 0) + 1
    challenge["attempts"] = attempts
    request.session[SUPERADMIN_MFA_SESSION_KEY] = challenge
    request.session.modified = True

    if attempts > settings.SUPERADMIN_MFA_ATTEMPT_LIMIT:
        log_security_event(
            "superadmin_mfa_locked",
            request=request,
            identifier=challenge.get("identifier", ""),
            details={"attempts": attempts},
        )
        clear_superadmin_mfa(request)
        return None, "Muitas tentativas de verificacao. Faca login novamente."

    if not constant_time_compare(challenge["code_hash"], _build_mfa_hash(normalized_code)):
        log_security_event(
            "superadmin_mfa_failed",
            request=request,
            identifier=challenge.get("identifier", ""),
            details={"attempts": attempts},
        )
        return None, "Codigo de verificacao invalido."

    user = get_user_model().objects.filter(
        pk=challenge.get("user_id"),
        is_superuser=True,
    ).first()
    if not user:
        clear_superadmin_mfa(request)
        return None, "Nao foi possivel concluir a verificacao."

    clear_superadmin_mfa(request)
    log_security_event(
        "superadmin_mfa_verified",
        request=request,
        user=user,
        identifier=challenge.get("identifier", ""),
    )
    return user, ""
