from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages

def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        perfil = request.POST.get("perfil")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if perfil == "admin" and user.is_staff:
                return redirect('/admin/')
            elif perfil == "cliente" and not user.is_staff:
                return redirect('/painel/')
            else:
                messages.error(request, "Tipo de usuário inválido para esse acesso.")
        else:
            messages.error(request, "Usuário ou senha inválidos.")
    return render(request, "accounts/login.html")

