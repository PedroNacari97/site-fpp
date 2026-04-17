from django.urls import path
from . import webhooks

urlpatterns = [
    path("pagamento/", webhooks.payment_webhook, name="payment_webhook"),
]
