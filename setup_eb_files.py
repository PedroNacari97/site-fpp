from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent

# 1) Criar .ebextensions/01_wsgi.config
ebext_dir = BASE_DIR / ".ebextensions"
ebext_dir.mkdir(parents=True, exist_ok=True)

wsgi_config = """option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: core/wsgi.py
"""
(ebext_dir / "01_wsgi.config").write_text(wsgi_config, encoding="utf-8")


# 2) Criar .platform/hooks/predeploy/01_migrate_collectstatic.sh
predeploy_dir = BASE_DIR / ".platform" / "hooks" / "predeploy"
predeploy_dir.mkdir(parents=True, exist_ok=True)

predeploy_script = """#!/bin/bash
set -e

# Ativa o virtualenv do EB e roda migrações + estáticos
source /var/app/venv/*/bin/activate

python manage.py migrate --noinput
python manage.py collectstatic --noinput
"""
predeploy_file = predeploy_dir / "01_migrate_collectstatic.sh"
predeploy_file.write_text(predeploy_script, encoding="utf-8")
os.chmod(predeploy_file, 0o755)  # Permissão de execução


# 3) Criar Procfile (opcional, se quiser forçar Gunicorn)
procfile_content = "web: gunicorn core.wsgi:application\n"
(Path(BASE_DIR) / "Procfile").write_text(procfile_content, encoding="utf-8")


# 4) Adicionar LOGGING no settings.py (se não existir)
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

print("✅ Arquivos de configuração criados:")
print(" - .ebextensions/01_wsgi.config")
print(" - .platform/hooks/predeploy/01_migrate_collectstatic.sh")
print(" - Procfile")
print("Se necessário, LOGGING adicionado ao core/settings.py")
