import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect

def gestao_nuxt(request, path=""):
    index_path = os.path.join(settings.BASE_DIR, "gestao_nuxt", "dist", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as index_file:
            return HttpResponse(index_file.read())
    return redirect("http://localhost:3000")
