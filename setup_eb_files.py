import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ===== 1) Criar arquivos do EB =====
print("📄 Criando arquivos de configuração do EB...")

# 1.1 .ebextensions/01_wsgi.config
ebext_dir = BASE_DIR / ".ebextensions"
ebext_dir.mkdir(parents=True, exist_ok=True)
(ebext_dir / "01_wsgi.config").write_text(
    "option_settings:\n"
    "  aws:elasticbeanstalk:container:python:\n"
    "    WSGIPath: core/wsgi.py\n",
    encoding="utf-8"
)

# 1.2 .platform/hooks/predeploy/01_migrate_collectstatic.sh
predeploy_dir = BASE_DIR / ".platform" / "hooks" / "predeploy"
predeploy_dir.mkdir(parents=True, exist_ok=True)
predeploy_script = """#!/bin/bash
set -e
source /var/app/venv/*/bin/activate
python manage.py migrate --noinput
python manage.py collectstatic --noinput
"""
predeploy_file = predeploy_dir / "01_migrate_collectstatic.sh"
predeploy_file.write_text(predeploy_script, encoding="utf-8")
os.chmod(predeploy_file, 0o755)  # Permissão de execução

# 1.3 Procfile
(Path(BASE_DIR) / "Procfile").write_text(
    "web: gunicorn core.wsgi:application\n", encoding="utf-8"
)

# 1.4 Adicionar LOGGING no settings.py (se não existir)
settings_path = BASE_DIR / "core" / "settings.py"
if settings_path.exists():
    settings_content = settings_path.read_text(encoding="utf-8")
    if "LOGGING = {" not in settings_content:
        logging_block = """
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'django.template': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    }
}
"""
        with open(settings_path, "a", encoding="utf-8") as f:
            f.write(logging_block)

print("✅ Arquivos criados.")

# ===== 2) Inicializar aplicação no EB =====
app_name = input("Digite o nome da aplicação no EB (ex: ncfly): ").strip()
region = input("Digite a região AWS (ex: us-east-2): ").strip()

print("🚀 Inicializando aplicação no EB...")
subprocess.run(["eb", "init", app_name, "--platform", "Python 3.13", "--region", region])

# ===== 3) Criar ambiente =====
env_name = input("Digite o nome do ambiente no EB (ex: ncfly-env): ").strip()
print(f"🌱 Criando ambiente '{env_name}'...")
subprocess.run(["eb", "create", env_name])

# ===== 4) Configurar variáveis de ambiente =====
secret_key = input("Cole sua DJANGO_SECRET_KEY (ou pressione Enter para gerar automaticamente): ").strip()
if not secret_key:
    import secrets
    secret_key = secrets.token_urlsafe(50)

allowed_hosts = ".elasticbeanstalk.com"
db_url = input("Cole o DATABASE_URL (ou deixe vazio para SQLite): ").strip()

print("⚙️ Definindo variáveis de ambiente...")
subprocess.run([
    "eb", "setenv",
    f"DJANGO_SECRET_KEY={secret_key}",
    f"DJANGO_ALLOWED_HOSTS={allowed_hosts}",
    f"DATABASE_URL={db_url}"
])

print("\n🎯 Tudo pronto! Agora é só fazer:")
print("    git add . && git commit -m 'Configuração EB' && eb deploy")
print("🌐 Para abrir: eb open")
