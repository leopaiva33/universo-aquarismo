"""
Gerador automático de artigos para o Universo Aquarismo.
Executado pelo GitHub Actions.

Fluxo:
1. Busca próxima palavra-chave pendente no Supabase
2. Gera artigo completo via API do Claude
3. Salva em src/content/blog/<slug>.md
4. Atualiza status no Supabase para 'publicado'
"""

import os
import re
import sys
import httpx
import anthropic
from datetime import date

# ─── Configuração ────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ─── Supabase ─────────────────────────────────────────────────────────────────

def buscar_keyword():
    """Retorna a próxima keyword pendente ou None se não houver."""
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/palavras_chave_aquario",
        headers=SUPABASE_HEADERS,
        params={
            "status": "neq.publicado",
            "order": "id.asc",
            "limit": "1",
        },
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def marcar_publicado(row_id: int):
    """Atualiza o status para 'publicado' e define publicado_em."""
    resp = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/palavras_chave_aquario",
        headers=SUPABASE_HEADERS,
        params={"id": f"eq.{row_id}"},
        json={"status": "publicado", "publicado_em": date.today().isoformat()},
    )
    resp.raise_for_status()
    print(f"✅ Supabase: id={row_id} marcado como publicado")

# ─── Geração do artigo ────────────────────────────────────────────────────────

PROMPT_SISTEMA = """
Você é um redator editorial sênior especializado em aquarismo.
Escreva artigos completos, profundos e prontos para publicação,
alinhados com E-E-A-T e políticas do Google AdSense.

Regras obrigatórias:
- Nunca use keyword stuffing
- Nunca use clickbait ou promessas falsas
- Escreva em português brasileiro natural
- Varie o ritmo: alterne frases curtas e longas
- Parágrafos com no máximo 4 linhas
- Use tabelas para comparações

Retorne SOMENTE o conteúdo do arquivo Markdown, começando com o frontmatter YAML (---).
Não inclua nenhum texto fora do arquivo .md.
""".strip()


def montar_prompt(keyword: str, intencao: str) -> str:
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
category: "Iluminação LED"
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
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    print(f"🤖 Gerando artigo para: '{keyword}'...")

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": montar_prompt(keyword, intencao)}],
    )
    return message.content[0].text


# ─── Slug e arquivo ───────────────────────────────────────────────────────────

def keyword_para_slug(keyword: str) -> str:
    """Converte keyword em slug kebab-case sem acentos."""
    slug = keyword.lower()
    trocas = {
        "á": "a", "à": "a", "ã": "a", "â": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "õ": "o", "ô": "o",
        "ú": "u", "ü": "u",
        "ç": "c",
    }
    for orig, sub in trocas.items():
        slug = slug.replace(orig, sub)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def salvar_artigo(slug: str, conteudo: str) -> str:
    caminho = f"src/content/blog/{slug}.md"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    print(f"💾 Artigo salvo em: {caminho}")
    return caminho


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    row = buscar_keyword()

    if not row:
        print("ℹ️  Nenhuma palavra-chave pendente no Supabase. Nada a fazer.")
        sys.exit(0)

    keyword  = row["keyword"]
    intencao = row.get("intencao", "Informacional")
    row_id   = row["id"]

    print(f"🔍 Palavra-chave encontrada: '{keyword}' (id={row_id}, intenção={intencao})")

    conteudo = gerar_artigo(keyword, intencao)
    slug     = keyword_para_slug(keyword)
    salvar_artigo(slug, conteudo)
    marcar_publicado(row_id)

    print("🚀 Pronto! O GitHub Actions vai commitar e o Vercel vai fazer o deploy.")


if __name__ == "__main__":
    main()
