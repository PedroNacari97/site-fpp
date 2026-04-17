import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Assinatura, Pagamento

logger = logging.getLogger(__name__)


def _verify_hmac(request):
    """Verifica assinatura HMAC do webhook."""
    secret = getattr(settings, "PAYMENT_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("PAYMENT_WEBHOOK_SECRET nao configurado \u2014 webhook aceito sem verificacao")
        return True

    signature = request.headers.get("X-Webhook-Signature", "")
    if not signature:
        return False

    expected = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@csrf_exempt
@require_POST
def payment_webhook(request):
    """Endpoint para receber eventos do gateway de pagamento."""
    if not _verify_hmac(request):
        logger.warning("Webhook com assinatura HMAC invalida \u2014 ip=%s", request.META.get("REMOTE_ADDR", ""))
        return HttpResponseForbidden("Invalid signature")

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponseBadRequest("Invalid JSON")

    event_type = payload.get("event", "")
    gateway_ref = payload.get("id", "") or payload.get("payment_id", "")

    if not gateway_ref:
        return HttpResponseBadRequest("Missing payment reference")

    if Pagamento.objects.filter(gateway_ref=gateway_ref).exists():
        return HttpResponse("Already processed", status=200)

    try:
        logger.info("Webhook recebido: event=%s ref=%s", event_type, gateway_ref)
        _process_event(payload, event_type, gateway_ref)
    except Exception:
        logger.exception("Erro ao processar webhook: event=%s ref=%s", event_type, gateway_ref)
        return HttpResponseBadRequest("Processing error", status=500)

    return HttpResponse("OK")


def _process_event(payload, event_type, gateway_ref):
    """Processa evento do gateway."""
    subscription_id = payload.get("subscription_id", "") or payload.get("subscription", "")

    if not subscription_id:
        logger.warning("Webhook sem subscription_id: ref=%s", gateway_ref)
        return None

    with transaction.atomic():
        try:
            assinatura = Assinatura.objects.select_for_update().get(gateway_subscription_id=subscription_id)
        except Assinatura.DoesNotExist:
            logger.warning("Assinatura nao encontrada para subscription_id=%s", subscription_id)
            return None

        valor = payload.get("value", 0) or payload.get("amount", 0)
        metodo = payload.get("billingType", "") or payload.get("payment_method", "")

        metodo_map = {
            "CREDIT_CARD": "cartao",
            "PIX": "pix",
            "BOLETO": "boleto",
            "credit_card": "cartao",
            "pix": "pix",
            "boleto": "boleto",
        }
        metodo_interno = metodo_map.get(metodo, "")

        if event_type in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED", "payment.confirmed"):
            Pagamento.objects.create(
                assinatura=assinatura,
                valor=valor,
                status=Pagamento.STATUS_CONFIRMADO,
                metodo=metodo_interno,
                gateway_ref=gateway_ref,
                gateway_event_type=event_type,
                dados_gateway=payload,
            )
            from datetime import timedelta
            assinatura.status = Assinatura.STATUS_ATIVA
            assinatura.data_vencimento = timezone.now() + timedelta(days=30)
            assinatura.save(update_fields=["status", "data_vencimento", "atualizado_em"])
            logger.info("Pagamento confirmado: assinatura=%s ref=%s", assinatura.pk, gateway_ref)

        elif event_type in ("PAYMENT_OVERDUE", "PAYMENT_FAILED", "payment.failed"):
            Pagamento.objects.create(
                assinatura=assinatura,
                valor=valor,
                status=Pagamento.STATUS_FALHOU,
                metodo=metodo_interno,
                gateway_ref=gateway_ref,
                gateway_event_type=event_type,
                dados_gateway=payload,
            )
            assinatura.status = Assinatura.STATUS_INADIMPLENTE
            assinatura.save(update_fields=["status", "atualizado_em"])
            logger.info("Pagamento falhou: assinatura=%s ref=%s", assinatura.pk, gateway_ref)

        elif event_type in ("PAYMENT_REFUNDED", "payment.refunded"):
            Pagamento.objects.create(
                assinatura=assinatura,
                valor=valor,
                status=Pagamento.STATUS_ESTORNADO,
                metodo=metodo_interno,
                gateway_ref=gateway_ref,
                gateway_event_type=event_type,
                dados_gateway=payload,
            )
            logger.info("Pagamento estornado: assinatura=%s ref=%s", assinatura.pk, gateway_ref)

        elif event_type in ("SUBSCRIPTION_CANCELLED", "subscription.cancelled"):
            assinatura.status = Assinatura.STATUS_CANCELADA
            assinatura.cancelada_em = timezone.now()
            assinatura.save(update_fields=["status", "cancelada_em", "atualizado_em"])
            logger.info("Assinatura cancelada: assinatura=%s", assinatura.pk)
