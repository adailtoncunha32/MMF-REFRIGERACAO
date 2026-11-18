"""
search_engine.py — Pesquisa de profissionais À PROCURA DE TRABALHO através da Tavily API.

Estratégia (testada com resultados reais):
- A melhor fonte são os grupos públicos de Facebook de AVAC: cada página de grupo traz as
  publicações recentes com autor, data e texto. Cada publicação é tratada como um resultado.
- Pesquisas complementares procuram publicações com «procuro trabalho/emprego» (Facebook,
  LinkedIn e web em geral).
- Só passam para análise textos em que a própria pessoa diz que procura trabalho. Ofertas de
  emprego, empresas a recrutar, subempreitadas e anúncios de venda de serviços (preços,
  orçamentos) são descartados logo aqui — antes da IA, o que também torna a pesquisa mais rápida.

A pesquisa usa exclusivamente o índice público da Tavily: não há acesso a páginas com
autenticação, CAPTCHAs ou paywalls, nem recolha direta (scraping) de websites.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from utils import extrair_dominio, limpar_texto, normalizar_texto, normalizar_url, url_segura

# Limite de texto por resultado enviado à IA (controla custo e tempo de resposta).
MAX_CARACTERES_CONTEUDO = 6000
TEMPO_LIMITE_SEGUNDOS = 45
# Publicações mais antigas do que isto já não interessam (a pessoa provavelmente já arranjou trabalho).
DIAS_MAX_PUBLICACAO = 90

# Grupos públicos de Facebook de AVAC/refrigeração onde técnicos publicam «procuro trabalho».
# São lidos em todas as pesquisas; grupos novos encontrados nas pesquisas também são lidos.
GRUPOS_FACEBOOK = [
    "https://www.facebook.com/groups/428467057269607",   # Técnicos ar condicionado e AVAC
    "https://www.facebook.com/groups/186360468885355",   # Montadores de condutas e canalizadores de AVAC
    "https://www.facebook.com/groups/517940446700287",   # Oferta de trabalhos AVAC Portugal e mundo
    "https://www.facebook.com/groups/166298864018421",
]
MAX_GRUPOS_NOVOS = 6

# Domínios que nunca têm candidatos: lojas, vídeo, portais de ofertas de emprego, agências e
# classificados (OLX/CustoJusto têm sobretudo ofertas de empresas e venda de serviços).
DOMINIOS_EXCLUIDOS = [
    "amazon.es", "amazon.com", "ebay.com", "aliexpress.com", "leroymerlin.pt",
    "worten.pt", "fnac.pt", "mediamarkt.pt", "kuantokusta.pt", "youtube.com",
    "tiktok.com", "pinterest.com", "pinterest.pt", "wikipedia.org", "instagram.com",
    "net-empregos.com", "emprego.sapo.pt", "pt.indeed.com", "indeed.com", "pt.jobsora.com",
    "jobsora.com", "manpower.pt", "adecco.com", "randstad.pt", "kellyservices.pt",
    "pt.jooble.org", "jooble.org", "glassdoor.com", "glassdoor.pt", "careerjet.pt",
    "itjobs.pt", "expressoemprego.pt", "pt.talent.com", "talent.com", "linkedin.com/jobs",
    "emprego.com", "jobleads.com", "gigroup.com", "pt.gigroup.com", "evolverh.pt", "egor.pt",
    "bracos.app", "emprego.clan.pt", "sercanto.pt", "pt.trabajo.org", "trabajo.org", "trabalhar.pt",
    "empregosonline.pt", "workana.com", "jobatus.pt", "kitempleo.pt", "eurofirms.com", "hays.pt",
    "olx.pt", "m.olx.pt", "custojusto.pt", "fixando.pt", "zaask.pt",
]

# --- Classificação do texto (sempre sobre texto normalizado: minúsculas, sem acentos) ---------

# A própria pessoa diz que procura trabalho.
_RE_PROCURA = re.compile(
    r"\bprocuro (?:um |uma |novo |nova )?(?:trabalho|emprego|oportunidade|colocacao)\b|"
    r"\b(?:estou|ando) (?:a )?procura de (?:um |uma |novo |nova )?(?:trabalho|emprego|oportunidade)\b|"
    r"\bestou procurando (?:trabalho|emprego)\b|"
    r"\bdisponivel para (?:trabalhar|comecar|inicio imediato|integrar)\b|"
    r"\bopen ?to ?work\b|\bdesempregad[oa]\b"
)
# Empresa a recrutar, subempreitadas ou pedidos de equipas.
_RE_OFERTA = re.compile(
    r"\ba recrutar\b|\brecrutamos\b|\brecrutamento\b|\bprocuramos\b|\bsolicito o envio\b|"
    r"\bentrada imediata\b|\bprecisa(?:m)? se\b|\bprecisamos\b|"
    r"\badmite se\b|\badmitimos\b|\bcontrata se\b|\bcontratamos\b|\boferecemos\b|\benviar cv\b|"
    r"\benvie (?:o )?(?:seu )?cv\b|\bcandidaturas?\b|\bm f\b|\bvagas? (?:de|para)\b|"
    r"\bprocuro para\b|\bprocuro (?:equipas?|oficiais|tecnicos|profissionais|montadores|ajudantes|"
    r"pessoal|colaboradore?s?|subempreiteiros?)\b|\bsub ?empreitada\b|\bofertas? de (?:emprego|trabalho)\b|"
    r"\bestamos a contratar\b|\bvem fazer parte\b|\bjunta te\b"
)
# Venda de serviços a clientes (preços, orçamentos): não é alguém à procura de emprego.
_RE_SERVICO = re.compile(
    r"\d+ ?(?:€|eur\b|euros\b)|€ ?\d+|\borcamentos?\b|\bprecos?\b|\bdesde \d+|"
    r"\bfaco (?:instalac|manutenc|montagem)|\bpromocao\b|\bvendo\b"
)


def classificar_texto(titulo: str, texto: str) -> str:
    """'procura' (pessoa à procura de trabalho), 'oferta', 'servico' ou 'sem_sinal'."""
    t = normalizar_texto(f"{titulo} {texto}")
    # Os preços procuram-se no texto original (a normalização remove o símbolo €).
    servico = bool(_RE_SERVICO.search(t) or _RE_SERVICO.search(f"{titulo} {texto}".lower()))
    if _RE_OFERTA.search(t):
        return "oferta"
    if not _RE_PROCURA.search(t):
        return "servico" if servico else "sem_sinal"
    if servico and not re.search(r"\bprocuro (?:trabalho|emprego)\b", t):
        return "servico"
    return "procura"


def parece_oferta_emprego(url: str, titulo: str, resumo: str) -> bool:
    """True se o texto for uma oferta de emprego."""
    return classificar_texto(titulo, f"{url} {resumo}") == "oferta"


# --- Publicações de grupos de Facebook --------------------------------------------------------

_RE_PUBLICACAO = re.compile(
    r"^#{2,4} \[(?P<autor>[^\]]+?)\s*·\s*(?P<data>\d{4}-\d{2}-\d{2}[^\]]*)\]\((?P<url>https?://[^)\s]+)\)\s*$",
    re.MULTILINE,
)
_RE_AUTOR_URL = re.compile(r"\*\*Author:\*\*\s*\[[^\]]*\]\((https?://[^)\s]+)\)")
_RE_TITULO_GRUPO = re.compile(r"^# (.+)$", re.MULTILINE)


def _data_publicacao(texto: str) -> Optional[date]:
    try:
        return datetime.fromisoformat(texto.strip()[:10]).date()
    except ValueError:
        return None


def dividir_publicacoes(conteudo: str, url_pagina: str, dias_max: int = DIAS_MAX_PUBLICACAO,
                        hoje: Optional[date] = None) -> list[dict]:
    """Divide a página de um grupo de Facebook nas suas publicações (só as recentes)."""
    hoje = hoje or date.today()
    conteudo = conteudo or ""
    m_titulo = _RE_TITULO_GRUPO.search(conteudo)
    titulo_grupo = m_titulo[1].strip() if m_titulo else "Grupo de Facebook"
    marcas = list(_RE_PUBLICACAO.finditer(conteudo))
    publicacoes = []
    for i, m in enumerate(marcas):
        corpo = conteudo[m.end(): marcas[i + 1].start() if i + 1 < len(marcas) else len(conteudo)]
        publicada = _data_publicacao(m["data"])
        if publicada and (hoje - publicada) > timedelta(days=dias_max):
            continue
        texto = re.split(r"\n\s*- \*\*Author:\*\*", corpo)[0].strip()
        if len(texto) < 15:
            continue
        autor = limpar_texto(m["autor"], 150)
        m_autor = _RE_AUTOR_URL.search(corpo)
        url_autor = url_segura(m_autor[1]) if m_autor else ""
        publicacoes.append({
            "url": url_segura(m["url"]) or url_pagina,
            "titulo": f"{autor} · {titulo_grupo}",
            "dominio": "facebook.com",
            "resumo": limpar_texto(texto, 800),
            "conteudo": limpar_texto(
                f"Autor da publicação: {autor}\n"
                + (f"Perfil do autor: {url_autor}\n" if url_autor else "")
                + f"Publicado em: {publicada.isoformat() if publicada else 'data desconhecida'}\n"
                f"Grupo: {titulo_grupo}\n\n{texto}")[:MAX_CARACTERES_CONTEUDO],
            "autor": autor,
            "url_autor": url_autor,
            "data_publicacao": publicada.isoformat() if publicada else "",
        })
    return publicacoes


def _url_grupo(url: str) -> str:
    """URL base de um grupo de Facebook (sem /posts/… ou /permalink/…), ou ''."""
    m = re.match(r"https?://(?:www\.|m\.)?facebook\.com/groups/([^/?#]+)", url or "")
    return f"https://www.facebook.com/groups/{m[1]}" if m else ""


# --- Consultas --------------------------------------------------------------------------------

_AREA = 'AVAC OR "ar condicionado" OR refrigeração OR climatização OR "técnico de frio"'


def _locais_de_pesquisa(localizacoes: list[str], outra: str) -> list[str]:
    """Converte as zonas escolhidas em termos de pesquisa."""
    mapa = {"Lisboa Centro": "Lisboa", "Grande Lisboa": "Lisboa", "Margem Sul": "Setúbal"}
    locais = []
    for local in localizacoes or []:
        if local == "Outra localização":
            if (outra or "").strip():
                locais.append(outra.strip())
        else:
            locais.append(mapa.get(local, local))
    return list(dict.fromkeys(locais)) or ["Lisboa"]


def gerar_consultas(parametros: dict, limite: int = 10, rodada: int = 0) -> list[str]:
    """
    Consultas que só encontram pessoas a dizer que procuram trabalho. As consultas gerais
    (grupos de Facebook e LinkedIn) vêm primeiro; depois as de cada especialidade e zona.
    """
    especialidades = list(parametros.get("especialidades") or []) or [
        "técnico de AVAC", "técnico de refrigeração", "técnico de ar condicionado",
    ]
    locais = _locais_de_pesquisa(parametros.get("localizacoes"), parametros.get("outra_localizacao", ""))
    engenheiros = any("engenheir" in e.lower() for e in especialidades)

    gerais = [
        f'site:facebook.com/groups "procuro trabalho" {_AREA}',
        f'site:facebook.com/groups "procuro emprego" {_AREA}',
        f'site:facebook.com/groups "procuro uma oportunidade" OR "procuro oportunidade" {_AREA}',
        f'site:pt.linkedin.com/posts "procuro emprego" OR "procuro trabalho" OR "à procura de emprego" {_AREA}',
    ]
    if engenheiros:
        gerais.append('site:pt.linkedin.com/posts engenheiro AVAC OR climatização OR energia '
                      '"procuro" OR "à procura de" OR "#OpenToWork"')
    if parametros.get("exige_fgas"):
        gerais.append('"procuro trabalho" OR "procuro emprego" "gases fluorados" OR "F-Gas" técnico')

    por_especialidade = []
    for i, esp in enumerate(especialidades):
        loc = locais[i % len(locais)]
        por_especialidade.append(f'"{esp}" "procuro trabalho" OR "procuro emprego" OR "à procura de emprego" {loc}')
        por_especialidade.append(f'site:facebook.com "{esp}" "procuro trabalho" OR "procuro emprego" {loc}')
    # Cada nova pesquisa começa noutro ponto, para trazer resultados diferentes.
    if rodada and por_especialidade:
        desloc = (rodada * 2) % len(por_especialidade)
        por_especialidade = por_especialidade[desloc:] + por_especialidade[:desloc]

    return list(dict.fromkeys(gerais + por_especialidade))[:limite]


# --- Execução ---------------------------------------------------------------------------------

class ErroPesquisa(Exception):
    """Erro da pesquisa com mensagem adequada para mostrar ao utilizador."""


def _criar_cliente(api_key: str):
    if not (api_key or "").strip():
        raise ErroPesquisa("Falta a chave TAVILY_API_KEY nos «Secrets» do servidor (ou no ficheiro .env).")
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise ErroPesquisa(
            "A biblioteca 'tavily-python' não está instalada. Execute: pip install -r requirements.txt"
        ) from exc
    return TavilyClient(api_key=api_key.strip())


def _traduzir_erro(exc: Exception) -> str:
    """Transforma uma exceção da Tavily numa mensagem clara em português."""
    nome = type(exc).__name__.lower()
    texto = str(exc).lower()
    if "invalidapikey" in nome or "unauthorized" in texto or "401" in texto or "invalid api key" in texto:
        return "A chave da Tavily é inválida. Confirme o valor de TAVILY_API_KEY."
    if "usagelimit" in nome or "429" in texto or "rate limit" in texto or "usage limit" in texto:
        return "Foi atingido o limite de pedidos da Tavily. Aguarde alguns minutos ou reveja o seu plano."
    if "timeout" in nome or "timed out" in texto or "timeout" in texto:
        return "A Tavily demorou demasiado tempo a responder. Tente novamente."
    if "connection" in nome or "connection" in texto:
        return "Não foi possível ligar à Tavily. Verifique a ligação à Internet."
    return "A Tavily devolveu um erro inesperado. Tente novamente dentro de momentos."


def _pesquisar_uma(cliente, consulta: str) -> list[dict]:
    resposta = cliente.search(
        query=consulta,
        search_depth="advanced",
        max_results=10,
        include_raw_content=True,
        exclude_domains=DOMINIOS_EXCLUIDOS,
        country="portugal",
        timeout=TEMPO_LIMITE_SEGUNDOS,
    )
    return (resposta or {}).get("results") or []


def _ler_grupos(cliente, urls: list[str]) -> list[dict]:
    """Lê as páginas públicas dos grupos (publicações recentes)."""
    if not urls:
        return []
    resposta = cliente.extract(urls=urls, extract_depth="basic", timeout=TEMPO_LIMITE_SEGUNDOS)
    return [{"url": r.get("url"), "title": "", "content": "", "raw_content": r.get("raw_content") or ""}
            for r in (resposta or {}).get("results") or []]


def _para_resultados(bruto: dict, origem: str) -> list[dict]:
    """Converte um resultado da Tavily em um ou mais resultados (um por publicação de grupo)."""
    url = url_segura(bruto.get("url"))
    if not url:
        return []
    raw = bruto.get("raw_content") or ""
    if _url_grupo(url) and _RE_PUBLICACAO.search(raw):
        return [{**p, "consulta": origem} for p in dividir_publicacoes(raw, url)]
    conteudo = limpar_texto(raw or bruto.get("content") or "")
    resumo = limpar_texto(bruto.get("content") or "", 800) or conteudo[:800]
    if len(conteudo) < 40 and len(resumo) < 40:
        return []
    return [{
        "url": url,
        "titulo": limpar_texto(bruto.get("title"), 300),
        "dominio": extrair_dominio(url),
        "resumo": resumo,
        "conteudo": conteudo[:MAX_CARACTERES_CONTEUDO],
        "consulta": origem,
    }]


def _executar_em_paralelo(executor, pedidos: list[tuple[str, Callable[[], list[dict]]]], brutos: list,
                          avisos: list[str], progresso, feito: list[int], total: int) -> int:
    """Corre os pedidos em paralelo; devolve o número de falhas."""
    falhas = 0
    tarefas = {executor.submit(funcao): origem for origem, funcao in pedidos}
    for tarefa in as_completed(tarefas):
        try:
            brutos.extend((tarefas[tarefa], r) for r in tarefa.result())
        except Exception as exc:  # cada pedido falha de forma independente
            falhas += 1
            mensagem = _traduzir_erro(exc)
            if mensagem not in avisos:
                avisos.append(mensagem)
        feito[0] += 1
        if progresso:
            progresso(min(feito[0], total), total)
    return falhas


def executar_pesquisa(
    api_key: str,
    consultas: list[str],
    max_resultados_total: int = 30,
    progresso: Optional[Callable[[int, int], None]] = None,
    estatisticas: Optional[dict] = None,
    grupos_conhecidos: Optional[list[str]] = None,
) -> tuple[list[dict], list[str]]:
    """
    Pesquisa + leitura dos grupos de Facebook, em paralelo. Devolve (resultados de pessoas à
    procura de trabalho, avisos). `estatisticas` (opcional) recebe as contagens do que foi
    descartado, os grupos novos descobertos e as pessoas encontradas por grupo.
    Lança ErroPesquisa apenas se nenhum pedido tiver sucesso.
    """
    cliente = _criar_cliente(api_key)
    grupos = list(dict.fromkeys(GRUPOS_FACEBOOK + [g for g in (grupos_conhecidos or []) if _url_grupo(g)]))
    lotes_grupos = [grupos[i:i + 10] for i in range(0, len(grupos), 10)]  # a Tavily lê até 20 por pedido
    brutos: list[tuple[str, dict]] = []
    avisos: list[str] = []
    total = len(consultas) + len(lotes_grupos) + 1
    feito = [0]

    pedidos = [(c, lambda c=c: _pesquisar_uma(cliente, c)) for c in consultas]
    pedidos += [("Grupos de Facebook de AVAC", lambda l=l: _ler_grupos(cliente, l)) for l in lotes_grupos]
    with ThreadPoolExecutor(max_workers=8) as executor:
        falhas = _executar_em_paralelo(executor, pedidos, brutos, avisos, progresso, feito, total)
        # Grupos novos encontrados nas pesquisas: lê também as publicações recentes deles.
        novos = []
        for _, r in brutos:
            g = _url_grupo(r.get("url") or "")
            if g and g not in grupos and g not in novos:
                novos.append(g)
        novos = novos[:MAX_GRUPOS_NOVOS]
        if novos:
            falhas += _executar_em_paralelo(
                executor, [("Grupos encontrados na pesquisa", lambda: _ler_grupos(cliente, novos))],
                brutos, avisos, progresso, feito, total)
        elif progresso:
            progresso(total, total)

    if falhas >= len(pedidos) + (1 if novos else 0):
        raise ErroPesquisa(avisos[0] if avisos else "A pesquisa falhou.")

    # Remove duplicados (mesmo URL) e fica só com quem diz que procura trabalho.
    contagem = {"analisados": 0, "oferta": 0, "servico": 0, "sem_sinal": 0}
    vistos: set[str] = set()
    resultados: list[dict] = []
    for origem, bruto in sorted(brutos, key=lambda par: -(par[1].get("score") or 0)):
        for r in _para_resultados(bruto, origem):
            chave = normalizar_url(r["url"])
            if not chave or chave in vistos:
                continue
            vistos.add(chave)
            contagem["analisados"] += 1
            tipo = classificar_texto(r["titulo"], r["conteudo"])
            if tipo != "procura":
                contagem[tipo] += 1
                continue
            resultados.append(r)
    resultados.sort(key=lambda r: r.get("data_publicacao") or "", reverse=True)  # mais recentes primeiro
    if estatisticas is not None:
        pessoas_por_grupo: dict[str, int] = {}
        for r in resultados[:max_resultados_total]:
            g = _url_grupo(r["url"])
            if g:
                pessoas_por_grupo[g] = pessoas_por_grupo.get(g, 0) + 1
        estatisticas.update(contagem, grupos_novos=novos, pessoas_por_grupo=pessoas_por_grupo,
                            grupos_lidos=len(grupos) + len(novos))
    return resultados[:max_resultados_total], avisos
