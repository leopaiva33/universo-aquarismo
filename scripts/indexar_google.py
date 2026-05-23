"""
Indexação automática no Google via Indexing API — Universo Aquarismo
====================================================================
Lê o sitemap do site, extrai todos os URLs e solicita indexação
ao Google para cada um via Google Indexing API.

Pré-requisitos (configuração única):
  1. Google Cloud Console → ativar "Indexing API" no projeto
  2. Criar conta de serviço → gerar chave JSON → salvar como
     scripts/google-service-account.json  (ou definir a variável
     de ambiente GOOGLE_SERVICE_ACCOUNT_JSON com o conteúdo do JSON)
  3. No Google Search Console → Configurações → Usuários e permissões
     → Adicionar o e-mail da conta de serviço como "Proprietário"

Uso local:
  pip install google-auth requests
  python scripts/indexar_google.py

Uso via GitHub Actions:
  Defina o secret GOOGLE_SERVICE_ACCOUNT_JSON com o conteúdo do JSON.
"""

from __future__ import annotations

import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Garante suporte a UTF-8 no Windows
os.environ.setdefault("PYTHONUTF8", "1")

try:
    import requests
    from google.oauth2 import service_account
    import google.auth.transport.requests as google_requests
except ImportError:
    print("❌ Dependências ausentes. Execute: pip install google-auth requests")
    sys.exit(1)


# ─── Config ───────────────────────────────────────────────────────────────────

SITEMAP_URL      = "https://universoaquarismo.com.br/sitemap-index.xml"
INDEXING_API_URL = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPES           = ["https://www.googleapis.com/auth/indexing"]
CREDENTIALS_FILE = Path(__file__).parent / "google-service-account.json"

# Intervalo entre chamadas à API (evita rate limit — quota: 200 req/dia)
DELAY_ENTRE_REQUESTS = 1.0  # segundos


# ─── Logging ──────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─── Credenciais ──────────────────────────────────────────────────────────────

def _carregar_dotenv() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def carregar_credenciais() -> service_account.Credentials:
    """Carrega credenciais da conta de serviço (JSON ou arquivo)."""
    json_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if json_env:
        log("🔑 Usando credenciais da variável GOOGLE_SERVICE_ACCOUNT_JSON")
        info = json.loads(json_env)
    elif CREDENTIALS_FILE.exists():
        log(f"🔑 Usando credenciais de {CREDENTIALS_FILE.name}")
        info = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    else:
        log("❌ Credenciais não encontradas.")
        log(f"   Crie {CREDENTIALS_FILE} ou defina GOOGLE_SERVICE_ACCOUNT_JSON")
        sys.exit(1)

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    auth_req = google_requests.Request()
    creds.refresh(auth_req)
    log(f"✅ Autenticado como: {info.get('client_email', 'desconhecido')}")
    return creds


# ─── Sitemap ──────────────────────────────────────────────────────────────────

def _extrair_urls_xml(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]


def buscar_urls_do_sitemap() -> list[str]:
    """Lê o sitemap index e retorna todos os URLs de conteúdo."""
    log(f"🗺️  Lendo sitemap: {SITEMAP_URL}")
    resp = requests.get(SITEMAP_URL, timeout=15)
    resp.raise_for_status()

    # sitemap-index aponta para sub-sitemaps
    sub_sitemaps = _extrair_urls_xml(resp.text)
    log(f"   {len(sub_sitemaps)} sub-sitemap(s) encontrado(s)")

    urls: list[str] = []
    for sub_url in sub_sitemaps:
        r = requests.get(sub_url, timeout=15)
        r.raise_for_status()
        paginas = _extrair_urls_xml(r.text)
        log(f"   {sub_url} → {len(paginas)} URL(s)")
        urls.extend(paginas)

    return urls


# ─── Indexing API ─────────────────────────────────────────────────────────────

def solicitar_indexacao(url: str, token: str) -> tuple[int, str]:
    """Envia uma URL para indexação. Retorna (status_code, mensagem)."""
    resp = requests.post(
        INDEXING_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"url": url, "type": "URL_UPDATED"},
        timeout=15,
    )
    if resp.status_code == 200:
        return 200, "✅ Indexação solicitada"
    body = resp.json()
    erro = body.get("error", {}).get("message", resp.text[:100])
    return resp.status_code, f"⚠️  {erro}"


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def main() -> None:
    _carregar_dotenv()

    log("=" * 60)
    log("🐠 Universo Aquarismo — Indexação Google")
    log("=" * 60)

    creds = carregar_credenciais()

    try:
        urls = buscar_urls_do_sitemap()
    except Exception as exc:
        log(f"❌ Erro ao ler sitemap: {exc}")
        sys.exit(1)

    if not urls:
        log("ℹ️  Nenhuma URL encontrada no sitemap.")
        sys.exit(0)

    log(f"\n📋 {len(urls)} URL(s) para indexar:")
    for u in urls:
        log(f"   {u}")

    log(f"\n🚀 Iniciando indexação ({DELAY_ENTRE_REQUESTS}s entre requests)...\n")

    ok = erros = 0
    for i, url in enumerate(urls, 1):
        # Token expira em 1h — renova se necessário
        if not creds.valid:
            creds.refresh(google_requests.Request())

        status, msg = solicitar_indexacao(url, creds.token)
        log(f"[{i:02d}/{len(urls)}] {msg}  {url}")

        if status == 200:
            ok += 1
        else:
            erros += 1

        if i < len(urls):
            time.sleep(DELAY_ENTRE_REQUESTS)

    log("\n" + "=" * 60)
    log(f"✅ Concluído: {ok} sucesso(s), {erros} erro(s) de {len(urls)} URL(s)")
    log("=" * 60)


if __name__ == "__main__":
    main()
