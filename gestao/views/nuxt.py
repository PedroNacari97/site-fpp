from django.shortcuts import render

def gestao_nuxt(request, path=None):
    return render(request, "gestao/nuxt_index.html")
