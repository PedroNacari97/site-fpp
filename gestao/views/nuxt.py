import os

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

def gestao_nuxt(request, path=""):
    index_path = os.path.join(settings.BASE_DIR, "gestao_nuxt", "dist", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as index_file:
            return HttpResponse(index_file.read())
    return redirect("http://localhost:3000")


@login_required
def api_me(request):
    name = request.user.get_full_name() or request.user.username
    return JsonResponse({"name": name})
