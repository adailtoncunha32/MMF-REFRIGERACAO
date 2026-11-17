"""
utils.py — Funções de apoio: normalização de dados, segurança (hash de
palavras-passe), deteção de duplicados, distâncias, ligações de contacto e
ordenação para a pesquisa urgente.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import secrets
import unicodedata
from datetime import date, datetime
from typing import Optional
from urllib.parse import quote, urlparse, urlunparse

import pandas as pd

from models import COORDENADAS, NAO_IDENTIFICADO

# ---------------------------------------------------------------------------
# Texto e normalização
# ---------------------------------------------------------------------------

_RE_TAGS = re.compile(r"<[^>]+>")
_RE_CONTROLO = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RE_ESPACOS = re.compile(r"[ \t]+")
_RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def limpar_texto(valor, limite: int = 0) -> str:
    """Remove marcação HTML e caracteres de controlo de texto vindo de fontes externas."""
    if valor is None:
        return ""
    texto = _RE_TAGS.sub(" ", str(valor))
    texto = _RE_CONTROLO.sub(" ", texto)
    texto = _RE_ESPACOS.sub(" ", texto).strip()
    if limite and len(texto) > limite:
        texto = texto[:limite].rstrip() + "…"
    return texto


_RE_MARCACAO = re.compile(r"[#*_>`|\[\]~]+")
_RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")
_RE_ROTULOS = re.compile(r"\b(Headline|Recent Activity|Reposted|Activity|About|Sobre|Atividade)\s*:?", re.I)


def limpar_resumo(valor, limite: int = 260) -> str:
    """Resumo legível: sem marcação Markdown, emojis nem rótulos copiados das páginas."""
    texto = limpar_texto(valor)
    texto = _RE_EMOJI.sub(" ", _RE_MARCACAO.sub(" ", texto))
    texto = _RE_ROTULOS.sub(" ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" -–·,.;:")
    if len(texto) > limite:
        texto = texto[:limite].rsplit(" ", 1)[0] + "…"
    return texto


def normalizar_texto(valor) -> str:
    """Minúsculas, sem acentos e sem pontuação — usado em comparações."""
    if not valor:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_email(valor) -> str:
    """Devolve o email em minúsculas ou string vazia se não for válido."""
    email = (valor or "").strip().lower()
    return email if _RE_EMAIL.match(email) else ""


def normalizar_telefone(valor) -> str:
    """Devolve apenas os dígitos do número, sem o indicativo de Portugal."""
    digitos = re.sub(r"\D", "", valor or "")
    if digitos.startswith("00351"):
        digitos = digitos[5:]
    elif digitos.startswith("351") and len(digitos) == 12:
        digitos = digitos[3:]
    return digitos if 9 <= len(digitos) <= 15 else ""


def url_segura(valor) -> str:
    """Aceita apenas ligações http/https; qualquer outro esquema é rejeitado."""
    url = (valor or "").strip()
    try:
        partes = urlparse(url)
    except ValueError:
        return ""
    if partes.scheme in ("http", "https") and partes.netloc:
        return url
    return ""


def normalizar_url(valor) -> str:
    """Forma canónica de um URL (sem www, parâmetros nem barra final)."""
    url = url_segura(valor)
    if not url:
        return ""
    partes = urlparse(url)
    dominio = partes.netloc.lower().removeprefix("www.")
    caminho = partes.path.rstrip("/")
    return urlunparse(("https", dominio, caminho, "", "", ""))


def extrair_dominio(valor) -> str:
    """Domínio de um URL, sem o prefixo www."""
    try:
        return urlparse(valor or "").netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def gerar_chave_dedup(nome: str, localizacao: str, especialidade: str) -> str:
    """Chave nome + localização + especialidade para detetar duplicados."""
    nome_n = normalizar_texto(nome)
    if not nome_n or nome_n == normalizar_texto(NAO_IDENTIFICADO):
        return ""
    return "|".join([nome_n, normalizar_texto(localizacao), normalizar_texto(especialidade)])


def lista_para_texto(valor, separador: str = ", ") -> str:
    """Converte listas guardadas em JSON num texto legível."""
    if isinstance(valor, (list, tuple)):
        return separador.join(str(v) for v in valor if str(v).strip())
    return "" if valor is None else str(valor)


def formatar_data(valor) -> str:
    """Datas no formato português (DD/MM/AAAA)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)) or valor is pd.NaT:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def nome_ficheiro_exportacao(extensao: str) -> str:
    """Exemplo: candidatos_avac_2026-11-16.xlsx"""
    return f"candidatos_avac_{date.today().isoformat()}.{extensao}"


# ---------------------------------------------------------------------------
# Segurança
# ---------------------------------------------------------------------------

_ITERACOES = 240_000


def hash_password(password: str) -> str:
    """Gera um hash PBKDF2-SHA256 com sal aleatório (nunca se guarda a palavra-passe)."""
    sal = secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(sal), _ITERACOES)
    return f"pbkdf2_sha256${_ITERACOES}${sal}${derivada.hex()}"


def verificar_password(password: str, guardado: str) -> bool:
    """Compara a palavra-passe com o hash guardado, em tempo constante."""
    try:
        _, iteracoes, sal, esperado = guardado.split("$")
        derivada = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(sal), int(iteracoes)
        )
        return hmac.compare_digest(derivada.hex(), esperado)
    except (ValueError, AttributeError):
        return False


def validar_password(password: str) -> Optional[str]:
    """Devolve uma mensagem de erro se a palavra-passe for fraca; None se for aceitável."""
    if len(password or "") < 8:
        return "A palavra-passe deve ter pelo menos 8 caracteres."
    if password.isdigit() or password.isalpha():
        return "A palavra-passe deve combinar letras e números."
    return None


def obter_variavel(nome: str) -> str:
    """Lê uma variável de ambiente (carregada do sistema ou do ficheiro .env)."""
    return (os.getenv(nome) or "").strip()


# ---------------------------------------------------------------------------
# Localização e distâncias
# ---------------------------------------------------------------------------

_COORDENADAS_NORM = {normalizar_texto(k): v for k, v in COORDENADAS.items()}


def localizar_coordenadas(texto: str) -> Optional[tuple[float, float]]:
    """Procura no texto o nome de uma zona conhecida e devolve as coordenadas."""
    alvo = normalizar_texto(texto)
    if not alvo:
        return None
    if alvo in _COORDENADAS_NORM:
        return _COORDENADAS_NORM[alvo]
    # Procura primeiro os nomes mais longos ("Vila Franca de Xira" antes de "Lisboa").
    for nome in sorted(_COORDENADAS_NORM, key=len, reverse=True):
        if re.search(rf"\b{re.escape(nome)}\b", alvo):
            return _COORDENADAS_NORM[nome]
    return None


def distancia_km(origem: tuple[float, float], destino: tuple[float, float]) -> float:
    """Distância em linha reta (fórmula de Haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*origem, *destino))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def distancia_entre_locais(local_a: str, local_b: str) -> Optional[float]:
    """Distância aproximada entre duas localizações em texto; None se desconhecida."""
    a, b = localizar_coordenadas(local_a), localizar_coordenadas(local_b)
    if a is None or b is None:
        return None
    return round(distancia_km(a, b), 1)


# ---------------------------------------------------------------------------
# Ligações de contacto (o envio é sempre decidido pelo utilizador)
# ---------------------------------------------------------------------------

def link_mailto(email: str, assunto: str, corpo: str) -> str:
    email = normalizar_email(email)
    if not email:
        return ""
    return f"mailto:{email}?subject={quote(assunto)}&body={quote(corpo)}"


def link_whatsapp(telefone: str, mensagem: str) -> str:
    numero = normalizar_telefone(telefone)
    if not numero:
        return ""
    if len(numero) == 9:  # número nacional sem indicativo
        numero = "351" + numero
    return f"https://wa.me/{numero}?text={quote(mensagem)}"


def link_telefone(telefone: str) -> str:
    numero = normalizar_telefone(telefone)
    if not numero:
        return ""
    return f"tel:+351{numero}" if len(numero) == 9 else f"tel:+{numero}"


# ---------------------------------------------------------------------------
# Ordenação da pesquisa urgente
# ---------------------------------------------------------------------------

def _corresponde_especialidade(linha: pd.Series, especialidades: list[str]) -> float:
    """1.0 = correspondência exata; 0.5 = parcial (palavras-chave); 0 = nenhuma."""
    if not especialidades:
        return 0.5
    perfil = normalizar_texto(
        " ".join(
            [
                lista_para_texto(linha.get("especialidades")),
                str(linha.get("cargo") or ""),
                lista_para_texto(linha.get("competencias")),
            ]
        )
    )
    ignorar = {"tecnico", "de", "da", "do", "em", "para", "com", "e", "a", "sistemas", "manutencao"}
    melhor = 0.0
    for esp in especialidades:
        alvo = normalizar_texto(esp)
        if alvo and alvo in perfil:
            return 1.0
        palavras = [p for p in alvo.split() if p not in ignorar]
        if palavras:
            acertos = sum(1 for p in palavras if p in perfil)
            melhor = max(melhor, 0.5 * acertos / len(palavras))
    return melhor


def ordenar_para_urgencia(
    df: pd.DataFrame,
    especialidades: list[str],
    local_servico: str,
    raio_km: int = 50,
    exige_viatura: bool = False,
    exige_fgas: bool = False,
    exige_deslocacao: bool = False,
) -> pd.DataFrame:
    """
    Ordena os candidatos para uma necessidade imediata. Critérios, por ordem de peso:
    disponibilidade imediata, score, proximidade, correspondência de competências,
    contacto direto e experiência comprovada.
    """
    if df.empty:
        return df.assign(prioridade=[], distancia_km=[], motivos=[])

    prioridades, distancias, motivos_todos = [], [], []
    for _, linha in df.iterrows():
        pontos, motivos = 0.0, []

        # 1) Disponibilidade imediata (máx. 35)
        classificacao = linha.get("disponibilidade_classificacao")
        if linha.get("disponibilidade_imediata") == "Sim" or classificacao == "Confirmada":
            pontos += 35
            motivos.append("Disponibilidade imediata")
        elif classificacao == "Provável":
            pontos += 20
            motivos.append("Disponibilidade provável")
        elif classificacao == "Não disponível":
            pontos -= 30

        # 2) Score da IA (máx. 25)
        pontos += 0.25 * float(linha.get("score") or 0)

        # 3) Proximidade (máx. 15)
        # Usa o dado mais específico disponível: concelho, depois localização, depois distrito.
        dist = None
        for campo in ("concelho", "localizacao", "distrito"):
            dist = distancia_entre_locais(str(linha.get(campo) or ""), local_servico)
            if dist is not None:
                break
        distancias.append(dist)
        if dist is not None:
            if dist <= raio_km:
                pontos += 15 * (1 - dist / max(raio_km, 1) * 0.6)
                motivos.append(f"A {dist:.0f} km")
            else:
                pontos -= 5

        # 4) Competências correspondentes (máx. 12)
        corresp = _corresponde_especialidade(linha, especialidades)
        pontos += 12 * corresp
        if corresp == 1.0:
            motivos.append("Especialidade exata")

        # 5) Contacto direto (máx. 8)
        if linha.get("telefone") or linha.get("email"):
            pontos += 8
            motivos.append("Contacto direto")

        # 6) Experiência comprovada (máx. 5)
        anos = linha.get("anos_experiencia")
        if anos is not None and not pd.isna(anos):
            pontos += min(float(anos), 10) * 0.5
            if anos >= 3:
                motivos.append(f"{int(anos)} anos de experiência")

        # Requisitos obrigatórios: penaliza quem declaradamente não cumpre.
        if exige_viatura and linha.get("viatura_propria") == "Não":
            pontos -= 40
        if exige_fgas and linha.get("certificacao_fgas") == "Não":
            pontos -= 40
        if exige_fgas and linha.get("certificacao_fgas") == "Sim":
            pontos += 5
            motivos.append("F-Gas")
        if exige_deslocacao and linha.get("disponibilidade_deslocacoes") == "Não":
            pontos -= 25

        prioridades.append(round(pontos, 1))
        motivos_todos.append(" · ".join(motivos))

    resultado = df.copy()
    resultado["prioridade"] = prioridades
    resultado["distancia_km"] = distancias
    resultado["motivos"] = motivos_todos
    return resultado.sort_values("prioridade", ascending=False).reset_index(drop=True)
