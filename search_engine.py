"""
search_engine.py — Geração de consultas e pesquisa de informação pública
através da Tavily API.

A pesquisa usa exclusivamente o índice público da Tavily: não há acesso a
páginas com autenticação, CAPTCHAs ou paywalls, nem recolha direta (scraping)
de websites.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from utils import extrair_dominio, limpar_texto, normalizar_url, url_segura

# Limite de texto por resultado enviado à IA (controla custo e tempo de resposta).
MAX_CARACTERES_CONTEUDO = 6000
TEMPO_LIMITE_SEGUNDOS = 45

# Domínios que nunca correspondem a candidatos (lojas, classificados de equipamento, vídeo…).
DOMINIOS_EXCLUIDOS = [
    "amazon.es", "amazon.com", "ebay.com", "aliexpress.com", "leroymerlin.pt",
    "worten.pt", "fnac.pt", "mediamarkt.pt", "kuantokusta.pt", "youtube.com",
    "tiktok.com", "pinterest.com", "pinterest.pt", "wikipedia.org",
    # Portais de ofertas de emprego e agências: publicam vagas, não candidatos.
    "net-empregos.com", "emprego.sapo.pt", "pt.indeed.com", "indeed.com", "pt.jobsora.com",
    "jobsora.com", "manpower.pt", "adecco.com", "randstad.pt", "kellyservices.pt",
    "pt.jooble.org", "jooble.org", "glassdoor.com", "glassdoor.pt", "careerjet.pt",
    "itjobs.pt", "expressoemprego.pt", "pt.talent.com", "talent.com", "linkedin.com/jobs",
    "emprego.com", "jobleads.com", "gigroup.com", "pt.gigroup.com", "evolverh.pt", "egor.pt",
    "bracos.app", "emprego.clan.pt", "sercanto.pt", "pt.trabajo.org", "trabajo.org", "trabalhar.pt", "empregosonline.pt", "workana.com", "jobatus.pt", "kitempleo.pt",
]

# Sinais de que um resultado é uma OFERTA de emprego (não um profissional). Os perfis
# pessoais do LinkedIn nunca são filtrados por estes sinais.
_RE_OFERTA = re.compile(
    r"\(m/f\)|\bm/f\b|ofertas? de emprego|\bvagas?\b|\brecrut(?:a|amento)\b|candidat[ae]-se|"
    r"estamos a recrutar|we are hiring|job offer|/jobs?/|/vagas?/|/empregos?/|/careers?/|/carreiras?/|"
    r"bolsa[ _-]?(?:de[ _-])?emprego|oportunidades de emprego",
    re.IGNORECASE,
)


def parece_oferta_emprego(url: str, titulo: str, resumo: str) -> bool:
    """True se o resultado for uma oferta de emprego e não o perfil de um profissional."""
    if "linkedin.com/in/" in url.lower():
        return False
    return bool(_RE_OFERTA.search(f"{url} {titulo}") or _RE_OFERTA.search(resumo[:300]))

# Termos de pesquisa associados a cada opção de disponibilidade.
_TERMOS_DISPONIBILIDADE = {
    "Disponibilidade imediata": '"disponibilidade imediata"',
    "Deslocações": "deslocações",
    "Trabalho fora de Lisboa": '"disponível para deslocações"',
    "Assistência urgente": "piquete urgências",
    "Trabalho por turnos": "turnos",
    "Fins de semana": '"fins de semana"',
}

_TERMOS_CONTRATACAO = {
    "Prestação de serviços": 'freelancer OR "prestação de serviços" OR "trabalhador independente"',
    "Subcontratação": 'subempreiteiro OR "subcontratação" OR "trabalhador independente"',
    "Trabalho pontual": 'freelancer OR biscates OR "trabalhos pontuais"',
    "Trabalho temporário": '"trabalho temporário" OR "disponibilidade imediata"',
}


class ErroPesquisa(Exception):
    """Erro da pesquisa com mensagem adequada para mostrar ao utilizador."""


def _locais_de_pesquisa(localizacoes: list[str], outra: str) -> list[str]:
    """Converte as zonas escolhidas em termos de pesquisa."""
    mapa = {"Lisboa Centro": "Lisboa", "Grande Lisboa": "Lisboa", "Margem Sul": '"Margem Sul" Setúbal'}
    locais = []
    for local in localizacoes or []:
        if local == "Outra localização":
            if (outra or "").strip():
                locais.append(outra.strip())
        else:
            locais.append(mapa.get(local, local))
    return list(dict.fromkeys(locais)) or ["Lisboa"]


def gerar_consultas(parametros: dict, limite: int = 8, rodada: int = 0) -> list[str]:
    """
    Gera automaticamente as consultas combinando especialidade, localização,
    certificações, disponibilidade e tipo de trabalho.
    """
    especialidades = list(parametros.get("especialidades") or []) or [
        "Técnico de AVAC", "Técnico de refrigeração", "Técnico de ar condicionado",
    ]
    locais = _locais_de_pesquisa(parametros.get("localizacoes"), parametros.get("outra_localizacao", ""))
    disponibilidade = [
        _TERMOS_DISPONIBILIDADE[d] for d in parametros.get("disponibilidade") or []
        if d in _TERMOS_DISPONIBILIDADE
    ]
    termo_disp = disponibilidade[0] if disponibilidade else ""
    termo_contrato = _TERMOS_CONTRATACAO.get(parametros.get("tipo_contratacao", ""), "")
    exige_fgas = bool(parametros.get("exige_fgas")) or any(
        "fluorad" in e.lower() or "f-gas" in e.lower() for e in especialidades
    )

    # Todas as consultas procuram o PROFISSIONAL (perfil, currículo, quem procura trabalho),
    # nunca ofertas de emprego publicadas por empresas.
    # Perfis do LinkedIn só de Portugal (pt.linkedin.com).
    modelos = [
        'site:pt.linkedin.com/in "{esp}" {loc} "open to work" OR "à procura de emprego" OR "disponível"',
        '"{esp}" {loc} "procuro emprego" OR "procuro trabalho" OR "à procura de novas oportunidades"',
        'site:pt.linkedin.com/in "{esp}" {loc}',
        # Fontes onde o próprio profissional costuma deixar telefone ou email.
        '"{esp}" {loc} currículo OR CV "telemóvel" OR "contacto" OR "email" disponível',
        'site:facebook.com "{esp}" {loc} disponível OR "procuro trabalho" contacto',
        '"{esp}" {loc} currículo OR "curriculum vitae" OR CV experiência',
        '"{esp}" {loc} freelancer OR "trabalhador independente" OR "por conta própria" contacto',
        'site:pt.linkedin.com/in "{esp}" Portugal {loc} anos de experiência',
        'site:pt.linkedin.com/in "{esp}" {loc} manutenção instalação',
    ]
    if termo_contrato:
        modelos.insert(1, '"{esp}" {loc} ' + termo_contrato)
    if exige_fgas:
        modelos.insert(1, '"{esp}" {loc} "gases fluorados" OR "F-Gas" certificado técnico')

    # Cada nova pesquisa começa noutro ponto da lista de modelos e de especialidades,
    # para não devolver sempre os mesmos resultados (e os mesmos duplicados).
    if rodada:
        desloc = (rodada * 3) % len(modelos)
        modelos = modelos[desloc:] + modelos[:desloc]
        desloc_esp = rodada % len(especialidades)
        especialidades = especialidades[desloc_esp:] + especialidades[:desloc_esp]

    consultas: list[str] = []
    # Percorre os modelos em rondas para que todas as especialidades fiquem representadas.
    for indice_modelo, modelo in enumerate(modelos):
        for indice_esp, esp in enumerate(especialidades):
            loc = locais[(indice_esp + indice_modelo) % len(locais)]
            consulta = modelo.format(esp=esp, loc=loc)
            if termo_disp and indice_modelo == 0:
                consulta += f" {termo_disp}"
            if consulta not in consultas:
                consultas.append(consulta)
            if len(consultas) >= limite:
                return consultas
    return consultas


def _criar_cliente(api_key: str):
    if not (api_key or "").strip():
        raise ErroPesquisa("Falta a chave TAVILY_API_KEY. Introduza-a na barra lateral ou no ficheiro .env.")
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


def _pesquisar_uma(cliente, consulta: str, max_resultados: int) -> list[dict]:
    resposta = cliente.search(
        query=consulta,
        search_depth="advanced",
        max_results=max_resultados,
        include_raw_content=True,
        exclude_domains=DOMINIOS_EXCLUIDOS,
        country="portugal",
        timeout=TEMPO_LIMITE_SEGUNDOS,
    )
    return (resposta or {}).get("results") or []


def executar_pesquisa(
    api_key: str,
    consultas: list[str],
    max_resultados_total: int = 30,
    progresso: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[dict], list[str]]:
    """
    Executa as consultas em paralelo e devolve (resultados únicos, avisos).
    Lança ErroPesquisa apenas se nenhuma consulta tiver sucesso.
    """
    cliente = _criar_cliente(api_key)
    por_consulta = max(5, min(10, -(-max_resultados_total // max(len(consultas), 1)) + 3))

    brutos: list[tuple[int, dict]] = []
    avisos: list[str] = []
    falhas = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        tarefas = {
            executor.submit(_pesquisar_uma, cliente, consulta, por_consulta): indice
            for indice, consulta in enumerate(consultas)
        }
        for concluidas, tarefa in enumerate(as_completed(tarefas), start=1):
            try:
                for resultado in tarefa.result():
                    brutos.append((tarefas[tarefa], resultado))
            except Exception as exc:  # cada consulta falha de forma independente
                falhas += 1
                mensagem = _traduzir_erro(exc)
                if mensagem not in avisos:
                    avisos.append(mensagem)
            if progresso:
                progresso(concluidas, len(consultas))

    if falhas == len(consultas) and consultas:
        raise ErroPesquisa(avisos[0] if avisos else "A pesquisa falhou.")

    # Remove duplicados (mesmo URL) e resultados sem origem verificável.
    vistos: set[str] = set()
    resultados: list[dict] = []
    for indice_consulta, r in sorted(brutos, key=lambda par: -(par[1].get("score") or 0)):
        url = url_segura(r.get("url"))
        chave = normalizar_url(url)
        if not url or not chave or chave in vistos:
            continue
        vistos.add(chave)
        conteudo = limpar_texto(r.get("raw_content") or r.get("content") or "")
        resumo = limpar_texto(r.get("content") or "", 800)
        if len(conteudo) < 40 and len(resumo) < 40:
            continue
        if parece_oferta_emprego(url, limpar_texto(r.get("title")), resumo):
            continue  # ofertas de emprego não interessam: procuramos profissionais
        resultados.append(
            {
                "url": url,
                "titulo": limpar_texto(r.get("title"), 300),
                "dominio": extrair_dominio(url),
                "resumo": resumo,
                "conteudo": conteudo[:MAX_CARACTERES_CONTEUDO],
                "consulta": consultas[indice_consulta],
            }
        )
        if len(resultados) >= max_resultados_total:
            break
    return resultados, avisos
