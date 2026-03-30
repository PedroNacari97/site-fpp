from django.conf import settings
from django.db import models


class ActiveUserSession(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_session_control",
    )
    session_key = models.CharField(max_length=40, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id}:{self.session_key or 'sem-sessao'}"


class LoginGuard(models.Model):
    identifier = models.CharField(max_length=150)
    ip_address = models.CharField(max_length=45, blank=True, default="")
    scope = models.CharField(max_length=40, default="default")
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("identifier", "ip_address", "scope")

    def __str__(self):
        return f"{self.scope}:{self.identifier}@{self.ip_address or 'sem-ip'}"


class SecurityEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    event_type = models.CharField(max_length=50)
    identifier = models.CharField(max_length=150, blank=True, default="")
    ip_address = models.CharField(max_length=45, blank=True, default="")
    user_agent = models.CharField(max_length=255, blank=True, default="")
    details = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} {self.identifier or self.user_id} em {self.created_at:%d/%m/%Y %H:%M}"
