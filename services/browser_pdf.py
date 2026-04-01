import os
import shutil
import subprocess
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string


_BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def _resolve_browser_executable():
    configured = os.getenv("BROWSER_PDF_EXECUTABLE", "").strip()
    if configured and Path(configured).exists():
        return configured
    for candidate in _BROWSER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Nenhum navegador Chromium compativel foi encontrado para gerar PDF.")


def load_static_css(*relative_paths):
    chunks = []
    for relative_path in relative_paths:
        resolved = finders.find(relative_path)
        if isinstance(resolved, (list, tuple)):
            resolved = resolved[0] if resolved else None
        if not resolved:
            continue
        chunks.append(Path(resolved).read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def render_pdf_from_template(template_name, context, *, css_paths=(), timeout=90):
    browser_path = _resolve_browser_executable()
    inline_css = load_static_css(*css_paths)
    html = render_to_string(template_name, {**context, "inline_css": inline_css})
    temp_root = Path(getattr(settings, "BASE_DIR", Path.cwd())) / ".tmp" / "browser-pdf"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = temp_root / f"ncfly-pdf-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)

    try:
        html_path = temp_dir / "document.html"
        pdf_path = temp_dir / "document.pdf"
        html_path.write_text(html, encoding="utf-8")

        command = [
            browser_path,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(getattr(settings, "BASE_DIR", Path.cwd())),
        )
        return pdf_path.read_bytes()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
