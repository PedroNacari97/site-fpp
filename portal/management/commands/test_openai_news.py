from django.core.management.base import BaseCommand

from portal.services.ai_pipeline import (
    DEFAULT_NEWS_MODEL,
    _extract_response_text,
    _openai_request,
)


class Command(BaseCommand):
    help = "Testa a configuracao da OpenAI usada pelo portal de noticias."

    def handle(self, *args, **options):
        response = _openai_request(
            {
                "model": DEFAULT_NEWS_MODEL,
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Responda em uma unica linha confirmando que a integracao do portal de noticias esta funcionando.",
                            }
                        ],
                    }
                ],
            }
        )
        output_text = _extract_response_text(response) or "Sem texto de resposta."
        self.stdout.write(self.style.SUCCESS("OpenAI configurada com sucesso."))
        self.stdout.write(f"Modelo: {DEFAULT_NEWS_MODEL}")
        self.stdout.write(output_text)
