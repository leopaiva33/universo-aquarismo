"""
Pipeline completo de publicação de artigos — Universo Aquarismo
===============================================================
Fluxo:
  1. Carrega variáveis de ambiente (suporta .env na raiz do projeto)
  2. Busca a próxima keyword pendente no Supabase
  3. Gera artigo completo via Claude API
  4. Busca imagem de destaque no Unsplash e salva em public/images/blog/
  5. Injeta heroImage no frontmatter e salva src/content/blog/<slug>.md
  6. Faz git add → commit → push (dispara deploy automático no Vercel)
  7. Atualiza status para 'publicado' no Supabase

Uso local:
  python scripts/gerar_artigo.py

Uso via GitHub Actions:
  Defina os secrets no repositório e o workflow chama este mesmo script.

Variáveis de ambiente obrigatórias:
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY

Variáveis opcionais:
  UNSPLASH_ACCESS_KEY  — sem ela a imagem é pulada
  GIT_USER_NAME        — nome para o commit (padrão: "github-actions[bot]")
  GIT_USER_EMAIL       — e-mail para o commit
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# Garante suporte a emojis/UTF-8 no terminal Windows
os.environ.setdefault("PYTHONUTF8", "1")
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

import httpx
import anthropic


# ─── Logging ──────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─── Carregamento de .env ─────────────────────────────────────────────────────

def _carregar_dotenv() -> None:
    """Lê o .env na raiz do projeto e injeta no os.environ (sem dependência externa)."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    log(f"📄 Carregando variáveis de {env_path}")
    with open(env_path, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            os.environ.setdefault(chave, valor)


_carregar_dotenv()


# ─── Configuração ─────────────────────────────────────────────────────────────

def _env(nome: str, obrigatorio: bool = True) -> str:
    valor = os.environ.get(nome, "")
    if obrigatorio and not valor:
        log(f"❌ Variável de ambiente obrigatória não definida: {nome}")
        sys.exit(1)
    return valor


ANTHROPIC_API_KEY   = _env("ANTHROPIC_API_KEY")
SUPABASE_URL        = _env("SUPABASE_URL")
SUPABASE_KEY        = _env("SUPABASE_KEY")
UNSPLASH_ACCESS_KEY = _env("UNSPLASH_ACCESS_KEY", obrigatorio=False)

GIT_USER_NAME  = os.environ.get("GIT_USER_NAME",  "github-actions[bot]")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "github-actions[bot]@users.noreply.github.com")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Raiz do projeto (um nível acima de scripts/)
PROJETO_ROOT = Path(__file__).parent.parent


# ─── Supabase ─────────────────────────────────────────────────────────────────

def buscar_keyword() -> dict | None:
    """Retorna a próxima keyword com status != 'publicado', ordenada por id, ou None."""
    log("🔍 Buscando palavra-chave pendente no Supabase...")
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/palavras_chave_aquario",
        headers=SUPABASE_HEADERS,
        params={"status": "neq.publicado", "order": "id.asc", "limit": "1"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def marcar_publicado(row_id: int) -> None:
    """Atualiza status → 'publicado' e define publicado_em com a data atual."""
    resp = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/palavras_chave_aquario",
        headers=SUPABASE_HEADERS,
        params={"id": f"eq.{row_id}"},
        json={"status": "publicado", "publicado_em": date.today().isoformat()},
        timeout=15,
    )
    resp.raise_for_status()
    log(f"✅ Supabase: id={row_id} marcado como 'publicado'")


# ─── Geração do artigo (Claude) ───────────────────────────────────────────────

_PROMPT_SISTEMA = """
Você é um redator editorial sênior especializado em aquarismo.
Escreva artigos completos, profundos e prontos para publicação,
alinhados com E-E-A-T e políticas do Google AdSense.

Regras obrigatórias:
- Nunca use keyword stuffing
- Nunca use clickbait ou promessas falsas
- Escreva em português brasileiro natural
- Varie o ritmo: alterne frases curtas e longas
- Parágrafos com no máximo 4 linhas
- Use tabelas para comparações sempre que relevante

Retorne SOMENTE o conteúdo do arquivo Markdown, começando com o frontmatter YAML (---).
Não inclua nenhum texto antes ou depois do arquivo .md.
""".strip()


def _montar_prompt(keyword: str, intencao: str) -> str:
    hoje = date.today().isoformat()
    return f"""
Crie um artigo SEO completo para o blog Universo Aquarismo.

Palavra-chave principal: "{keyword}"
Intenção de busca: {intencao}
Data de publicação: {hoje}

O arquivo deve começar com frontmatter YAML exatamente neste formato:
---
title: "[Título atrativo com a keyword, máximo 60 caracteres]"
description: "[Meta description com keyword, 120-155 caracteres]"
pubDate: {hoje}
category: "[categoria relevante]"
tags: [lista de 5-7 tags relevantes em kebab-case]
readTime: [número estimado de minutos de leitura]
featured: false
draft: false
---

Depois do frontmatter, escreva o artigo completo com:
1. Introdução direta (sem "Neste artigo veremos...")
2. Seções H2 com conteúdo substancial
3. Ao menos uma tabela comparativa quando relevante
4. Seção ## Perguntas Frequentes com 4-5 perguntas reais
5. Conclusão com CTA natural

Tamanho: 1.500 a 2.500 palavras.
""".strip()


def gerar_artigo(keyword: str, intencao: str) -> str:
    log(f"🤖 Gerando artigo via Claude para: '{keyword}'...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=_PROMPT_SISTEMA,
        messages=[{"role": "user", "content": _montar_prompt(keyword, intencao)}],
    )
    conteudo = message.content[0].text
    log(f"✍️  Artigo gerado ({len(conteudo.split())} palavras aprox.)")
    return conteudo


# ─── Imagem de destaque (Unsplash) ────────────────────────────────────────────

_TERMOS_EN: dict[str, str] = {
    "aquário": "aquarium", "peixe": "fish", "peixes": "fish",
    "planta": "plant", "plantas": "plants", "iluminação": "lighting",
    "lâmpada": "lamp", "luminária": "light fixture", "led": "led",
    "tropical": "tropical", "coral": "coral reef", "água": "water",
    "filtro": "filter", "bomba": "pump", "algas": "algae",
    "temperatura": "temperature", "ph": "ph water",
}


def _keyword_en(keyword: str) -> str:
    resultado = keyword.lower()
    for pt, en in _TERMOS_EN.items():
        resultado = resultado.replace(pt, en)
    return resultado


def _buscar_foto(query: str) -> dict | None:
    resp = httpx.get(
        "https://api.unsplash.com/search/photos",
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        params={"query": query, "per_page": 1, "orientation": "landscape"},
        timeout=15,
    )
    resp.raise_for_status()
    resultados = resp.json().get("results", [])
    return resultados[0] if resultados else None


def buscar_imagem_unsplash(keyword: str, slug: str) -> str | None:
    """Baixa foto do Unsplash e salva em public/images/blog/{slug}.jpg.
    Retorna o caminho público ou None se não disponível."""
    if not UNSPLASH_ACCESS_KEY:
        log("⚠️  UNSPLASH_ACCESS_KEY não definido — artigo será publicado sem imagem.")
        return None

    log(f"🖼️  Buscando imagem no Unsplash...")
    try:
        query = _keyword_en(keyword)
        foto = _buscar_foto(query) or _buscar_foto("aquarium tropical fish")

        if not foto:
            log("⚠️  Nenhuma imagem encontrada no Unsplash.")
            return None

        img_url  = foto["urls"]["regular"]
        autor    = foto["user"]["name"]
        perfil   = foto["user"]["links"]["html"]

        img_bytes = httpx.get(img_url, timeout=30, follow_redirects=True).content

        destino = PROJETO_ROOT / "public" / "images" / "blog"
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f"{slug}.jpg"
        arquivo.write_bytes(img_bytes)

        log(f"🖼️  Imagem salva: public/images/blog/{slug}.jpg  (foto: {autor} — {perfil})")
        return f"/images/blog/{slug}.jpg"

    except Exception as exc:
        log(f"⚠️  Erro ao buscar imagem no Unsplash: {exc}")
        return None


def injetar_hero_image(conteudo: str, hero_path: str) -> str:
    """Insere heroImage no frontmatter gerado pelo Claude."""
    partes = conteudo.split("---", 2)
    if len(partes) >= 3:
        partes[1] = partes[1].rstrip("\n") + f'\nheroImage: "{hero_path}"\n'
        return "---".join(partes)
    return conteudo


# ─── Slug e arquivo ───────────────────────────────────────────────────────────

_ACENTOS = str.maketrans(
    "áàãâéêíóõôúüç",
    "aaaaeeiooouuc",
)


def keyword_para_slug(keyword: str) -> str:
    slug = keyword.lower().translate(_ACENTOS)
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def salvar_artigo(slug: str, conteudo: str) -> Path:
    caminho = PROJETO_ROOT / "src" / "content" / "blog" / f"{slug}.md"
    caminho.write_text(conteudo, encoding="utf-8")
    log(f"💾 Artigo salvo: src/content/blog/{slug}.md")
    return caminho


# ─── Git: add → commit → push ────────────────────────────────────────────────

def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=PROJETO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def git_publicar(slug: str, keyword: str) -> bool:
    """Faz git add, commit e push. Retorna True se o push foi realizado."""
    log("📦 Preparando commit no git...")

    # Configura identidade (necessário em ambientes CI sem config global)
    _git("config", "user.name",  GIT_USER_NAME,  check=False)
    _git("config", "user.email", GIT_USER_EMAIL, check=False)

    # Adiciona artigo e imagem (se existir)
    arquivos: list[str] = [f"src/content/blog/{slug}.md"]
    img = PROJETO_ROOT / "public" / "images" / "blog" / f"{slug}.jpg"
    if img.exists():
        arquivos.append(f"public/images/blog/{slug}.jpg")

    _git("add", *arquivos)

    # Verifica se há algo staged
    diff = _git("diff", "--staged", "--quiet", check=False)
    if diff.returncode == 0:
        log("ℹ️  Nenhuma mudança staged — artigo pode já estar publicado.")
        return False

    # Commit
    msg = f"feat: artigo '{slug}' publicado automaticamente"
    resultado = _git("commit", "-m", msg)
    log(f"✅ Commit: {resultado.stdout.strip().splitlines()[0]}")

    # Push
    push = _git("push")
    if push.returncode == 0:
        log("🚀 Push realizado — deploy no Vercel será iniciado automaticamente.")
        return True

    # Tenta setar upstream e fazer push novamente
    _git("push", "--set-upstream", "origin", "main")
    log("🚀 Push realizado (upstream configurado).")
    return True


# ─── Deploy Vercel ────────────────────────────────────────────────────────────

def vercel_deploy() -> bool:
    """Executa 'npx vercel deploy --prod --yes' para forçar o deploy em produção.
    Retorna True se o deploy foi confirmado como READY."""
    log("🚀 Iniciando deploy no Vercel...")
    try:
        resultado = subprocess.run(
            ["npx", "vercel", "deploy", "--prod", "--yes"],
            cwd=PROJETO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        saida = resultado.stdout + resultado.stderr
        if resultado.returncode == 0 and ("READY" in saida or "Deployment completed" in saida):
            log("✅ Deploy Vercel concluído com sucesso.")
            return True
        log(f"⚠️  Deploy Vercel retornou código {resultado.returncode}:\n{saida[-500:]}")
        return False
    except FileNotFoundError:
        log("⚠️  npx/vercel não encontrado — pulando deploy automático.")
        return False
    except subprocess.TimeoutExpired:
        log("⚠️  Deploy Vercel excedeu o tempo limite (5 min).")
        return False
    except Exception as exc:
        log(f"⚠️  Erro no deploy Vercel: {exc}")
        return False


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main() -> None:
    log("=" * 60)
    log("🐠 Universo Aquarismo — Pipeline de publicação de artigos")
    log("=" * 60)

    # 1. Buscar keyword
    row = buscar_keyword()
    if not row:
        log("ℹ️  Nenhuma palavra-chave pendente. Nada a fazer.")
        sys.exit(0)

    keyword  = row["keyword"]
    intencao = row.get("intencao", "Informacional")
    row_id   = row["id"]
    log(f"🔑 Keyword: '{keyword}'  (id={row_id}, intenção={intencao})")

    slug = keyword_para_slug(keyword)
    log(f"🔗 Slug: {slug}")

    # 2. Gerar artigo
    conteudo = gerar_artigo(keyword, intencao)

    # 3. Buscar imagem
    hero_path = buscar_imagem_unsplash(keyword, slug)
    if hero_path:
        conteudo = injetar_hero_image(conteudo, hero_path)

    # 4. Salvar arquivo
    salvar_artigo(slug, conteudo)

    # 5. Git commit + push (se falhar, aborta antes de marcar no Supabase)
    try:
        publicado = git_publicar(slug, keyword)
    except subprocess.CalledProcessError as exc:
        log(f"❌ Erro no git: {exc.stderr.strip()}")
        log("   O arquivo foi salvo localmente, mas NÃO foi publicado.")
        log("   Status no Supabase NÃO foi atualizado.")
        sys.exit(1)

    # 6. Atualizar Supabase (só após push bem-sucedido)
    if publicado:
        try:
            marcar_publicado(row_id)
        except Exception as exc:
            log(f"⚠️  Artigo publicado no git, mas falha ao atualizar Supabase: {exc}")

    # 7. Deploy no Vercel via CLI
    vercel_ok = vercel_deploy()

    log("=" * 60)
    log(f"✅ Pipeline concluído para '{keyword}'")
    log(f"   URL: https://universoaquarismo.com.br/blog/{slug}/")
    if not vercel_ok:
        log("   ⚠️  Deploy Vercel não confirmado — verifique vercel.com")
    log("=" * 60)


if __name__ == "__main__":
    main()
