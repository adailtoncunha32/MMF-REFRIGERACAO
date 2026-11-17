"""
app.py — Interface Streamlit da aplicação "Técnicos AVAC Pro".

Executar com:  streamlit run app.py
"""

from __future__ import annotations

import html
import os
import time
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # carrega as chaves do ficheiro .env antes de importar os módulos

# Em alojamento na nuvem (Streamlit Community Cloud) as chaves vêm dos "Secrets".
try:
    for _nome in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "DATABASE_URL", "ANTHROPIC_MODEL",
                  "ADMIN_NOME", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
        if _nome in st.secrets and not os.getenv(_nome):
            os.environ[_nome] = str(st.secrets[_nome])
except Exception:  # sem ficheiro de segredos (execução local): usa-se apenas o .env
    pass

import database as db  # noqa: E402
from ai_analyzer import ErroIA, analisar_resultados, analisar_sem_ia  # noqa: E402
from database import ErroBaseDados  # noqa: E402
from export_utils import ErroExportacao, exportar_csv, exportar_excel, exportar_pdf  # noqa: E402
from models import (  # noqa: E402
    AREAS_EXPERIENCIA,
    CATEGORIAS_ESPECIALIDADES,
    CLASSIF_DISPONIBILIDADE,
    DISPONIBILIDADES,
    ESTADOS,
    ESTADOS_GESTOR,
    LOCALIZACOES,
    MEIOS_CONTACTO,
    NOME_APP,
    PERFIS_UTILIZADOR,
    RECOMENDACOES,
    RESULTADOS_CONTACTO,
    TIPOS_CONTRATACAO,
    TODAS_ESPECIALIDADES,
    TRI_ESTADO,
    CandidatoIA,
)
from search_engine import ErroPesquisa, executar_pesquisa, gerar_consultas  # noqa: E402
from utils import (  # noqa: E402
    formatar_data,
    link_mailto,
    link_telefone,
    link_whatsapp,
    lista_para_texto,
    limpar_resumo,
    nome_ficheiro_exportacao,
    normalizar_texto,
    obter_variavel,
    ordenar_para_urgencia,
    url_segura,
    validar_password,
)

st.set_page_config(page_title=NOME_APP, page_icon=":material/ac_unit:", layout="wide", initial_sidebar_state="expanded")

# Compatibilidade entre versões do Streamlit para "ocupar toda a largura".
_VERSAO = tuple(int(p) for p in st.__version__.split(".")[:2])
LARGURA = {"width": "stretch"} if _VERSAO >= (1, 50) else {"use_container_width": True}

AZUL_ESCURO, CIANO, VERDE, VERMELHO, CINZA = "#0B2545", "#13A8C9", "#1E9E6A", "#D64545", "#F3F6FA"
PALETA = [CIANO, AZUL_ESCURO, VERDE, "#5B7DB1", "#8ED1E0", "#F2A541", "#7A8CA3", VERMELHO]

PAGINAS_POR_PERFIL = {
    "Administrador": ["Painel", "Candidatos", "Serviço imediato", "Tarefas", "Contratações", "Administração"],
    "Recrutador": ["Painel", "Candidatos", "Serviço imediato", "Tarefas"],
    "Gestor": ["Painel", "Candidatos", "Contratações", "Tarefas"],
}
ICONES_PAGINA = {
    "Painel": "dashboard", "Candidatos": "engineering", "Serviço imediato": "bolt",
    "Tarefas": "task_alt", "Contratações": "handshake", "Administração": "settings",
}


# ---------------------------------------------------------------------------
# Aparência
# ---------------------------------------------------------------------------

def aplicar_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {CINZA}; }}
        .block-container {{ padding-top: 3.6rem; max-width: 1500px; }}
        section[data-testid="stSidebar"] {{ background: {AZUL_ESCURO}; }}
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] summary,
        section[data-testid="stSidebar"] small {{ color: #FFFFFF !important; }}
        section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.2); }}
        section[data-testid="stSidebar"] [data-testid="stExpander"] {{
            border: 1px solid rgba(255,255,255,.25); border-radius: 10px; }}
        section[data-testid="stSidebar"] button p {{ color: inherit !important; }}
        [data-testid^="stBaseButton-secondary"], [data-testid^="stBaseLinkButton-secondary"] {{
            background:#FFFFFF !important; color:{AZUL_ESCURO} !important;
            border:1.5px solid {AZUL_ESCURO} !important; border-radius:10px !important;
            font-weight:600 !important; opacity:1 !important; }}
        [data-testid^="stBaseButton-secondary"]:hover, [data-testid^="stBaseLinkButton-secondary"]:hover {{
            background:{AZUL_ESCURO} !important; color:#FFFFFF !important; }}
        [data-testid^="stBaseButton-primary"], [data-testid^="stBaseLinkButton-primary"] {{
            background:{CIANO} !important; color:#FFFFFF !important; border:1.5px solid {CIANO} !important;
            border-radius:10px !important; font-weight:700 !important; }}
        [data-testid^="stBaseButton-primary"]:hover, [data-testid^="stBaseLinkButton-primary"]:hover {{
            background:#0E8FAC !important; border-color:#0E8FAC !important; }}
        [data-testid^="stBaseButton"] p, [data-testid^="stBaseLinkButton"] p {{ font-weight:inherit; }}
        [data-testid^="stBaseButton"]:disabled {{ background:#E6EBF1 !important; color:#7A8CA3 !important;
            border-color:#C9D3DF !important; cursor:not-allowed; }}
        section[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"] {{
            border-color:#FFFFFF !important; }}
        .logo-app {{ display:flex; align-items:center; gap:.6rem; margin-bottom:.4rem; }}
        .logo-app .icone {{ font-size: 1.9rem; line-height:1; background:#FFFFFF; border-radius:12px;
            box-shadow:0 0 0 2px {CIANO};
            width:48px; height:48px; display:flex; align-items:center; justify-content:center; }}
        .logo-app .nome {{ color:#fff; font-weight:700; font-size:1.15rem; line-height:1.2; }}
        .logo-app .sub {{ color:#9FD8E6; font-size:.78rem; }}
        .cabecalho {{ background: linear-gradient(100deg, {AZUL_ESCURO} 0%, #134074 60%, {CIANO} 130%);
            color:#fff; border-radius:14px; padding:1.1rem 1.5rem; margin-bottom:1.1rem; }}
        .cabecalho h1 {{ color:#fff; font-size:1.55rem; margin:0; padding:0; }}
        .cabecalho p {{ color:#D6ECF3; margin:.2rem 0 0 0; font-size:.95rem; }}
        div[data-testid="stMetric"] {{ background:#fff; border:1px solid #E1E8F0;
            border-left:5px solid {CIANO}; border-radius:12px; padding:.8rem 1rem;
            box-shadow:0 1px 3px rgba(11,37,69,.06); }}
        div[data-testid="stMetricValue"] {{ color:{AZUL_ESCURO}; }}
        div[data-testid="stMetric"] label, div[data-testid="stMetric"] label *,
        div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] *,
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {{
            white-space:normal !important; overflow:visible !important; text-overflow:clip !important;
            word-break:normal !important; overflow-wrap:normal !important; }}
        div[data-testid="stMetric"] label {{ min-height:2.6em; align-items:flex-start; }}
        .cartao {{ background:#fff; border:1px solid #E1E8F0; border-radius:12px;
            padding:1rem 1.2rem; margin-bottom:.8rem; box-shadow:0 1px 3px rgba(11,37,69,.06); }}
        .cartao h3 {{ margin:0 0 .2rem 0; padding:0; color:{AZUL_ESCURO}; font-size:1.25rem; }}
        .cartao .linha {{ color:#4A5B70; font-size:.93rem; }}
        .etiqueta {{ display:inline-block; padding:.15rem .6rem; border-radius:999px;
            font-size:.78rem; font-weight:600; margin:.25rem .3rem 0 0; }}
        .et-azul {{ background:#E3F4F9; color:#0B6E86; }}
        .et-verde {{ background:#E2F5EC; color:#17734E; }}
        .et-cinza {{ background:#EDF1F6; color:#4A5B70; }}
        .et-vermelha {{ background:#FBE6E6; color:#A93232; }}
        .et-escura {{ background:{AZUL_ESCURO}; color:#fff; }}
        div[data-testid="stExpander"] {{ background:#fff; border-radius:12px; }}
        .stTabs [data-baseweb="tab"] {{ font-weight:600; }}
        /* ---------- Sem textos em inglês do Streamlit ---------- */
        [data-testid="InputInstructions"] {{ display:none !important; }}
        [data-testid="stElementToolbar"] {{ display:none !important; }}
        /* ---------- Caixas ---------- */
        div[data-testid="stVerticalBlockBorderWrapper"] {{ background:#fff; border-radius:14px; }}
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {{
            background:#F8FAFC; border-radius:10px; }}
        /* ---------- Painel ---------- */
        .funil {{ display:flex; align-items:stretch; gap:.4rem; background:#fff; border:1px solid #E1E8F0;
            border-radius:14px; padding:.7rem .9rem; margin-bottom:1.2rem; }}
        .funil-passo {{ flex:1; text-align:center; padding:.2rem 0; }}
        .funil-passo b {{ display:block; font-size:1.45rem; color:{AZUL_ESCURO}; line-height:1.1; }}
        .funil-passo span {{ color:#5B6B80; font-size:.8rem; }}
        .funil-seta {{ color:#A9B7C6; font-size:1.4rem; display:flex; align-items:center; }}
        .ln-topo {{ display:flex; align-items:baseline; gap:.6rem; }}
        .ln-nome {{ font-weight:700; color:{AZUL_ESCURO}; }}
        .ln-pont {{ background:{AZUL_ESCURO}; color:#fff; border-radius:999px; padding:0 .5rem;
            font-size:.75rem; font-weight:700; }}
        .ln-sub {{ color:#5B6B80; font-size:.84rem; }}
        .ln-nota {{ color:#0B6E86; font-size:.8rem; font-weight:600; margin-top:.1rem; }}
        /* ---------- Login ---------- */
        .login-cabecalho {{ display:flex; align-items:center; gap:1rem; margin:.2rem 0 1.4rem 0; }}
        .login-logo {{ width:58px; height:58px; border-radius:14px; background:#fff; display:flex;
            align-items:center; justify-content:center; font-size:2rem; box-shadow:0 0 0 2px {CIANO};
            flex-shrink:0; }}
        .login-nome {{ font-size:1.6rem; font-weight:700; color:{AZUL_ESCURO}; line-height:1.2; }}
        .login-texto {{ color:#5B6B80; font-size:.95rem; margin-top:.2rem; }}
        div[data-testid="stForm"]:has(.login-cabecalho) {{ padding:2.2rem 2.2rem 1.8rem 2.2rem; }}
        div[data-testid="stForm"]:has(.login-cabecalho) input {{ min-height:2.9rem; font-size:1rem; }}
        div[data-testid="stForm"]:has(.login-cabecalho) button {{ min-height:3rem; font-size:1.02rem; }}
        .st-key-link_guia {{ margin-top:.3rem; }}
        .st-key-link_guia button p {{ color:{CIANO} !important; font-weight:600; }}
        div[data-testid="stForm"] {{ background:#fff; border:1px solid #E1E8F0 !important; border-radius:18px;
            padding:1.4rem 1.5rem 1.1rem 1.5rem; box-shadow:0 10px 30px rgba(11,37,69,.08); }}
        /* ---------- Cartões de candidato (grelha) ---------- */
        .cc-topo {{ display:flex; gap:.75rem; align-items:flex-start; }}
        .cc-avatar {{ width:46px; height:46px; border-radius:50%; flex-shrink:0; display:flex;
            align-items:center; justify-content:center; font-weight:700; color:#fff; font-size:1rem;
            background: linear-gradient(135deg, {AZUL_ESCURO}, {CIANO}); }}
        .cc-nome {{ font-weight:700; color:{AZUL_ESCURO}; font-size:1.04rem; line-height:1.25; }}
        .cc-cargo {{ color:#4A5B70; font-size:.86rem; line-height:1.3; margin-top:.1rem;
            display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .cc-score {{ margin-left:auto; text-align:center; flex-shrink:0; }}
        .cc-score b {{ display:block; font-size:1.25rem; color:{AZUL_ESCURO}; line-height:1; }}
        .cc-score small {{ color:#7A8CA3; font-size:.7rem; }}
        .cc-barra {{ height:6px; background:#E6EEF5; border-radius:999px; margin:.7rem 0 .55rem 0;
            overflow:hidden; }}
        .cc-barra div {{ height:100%; border-radius:999px; background:{CIANO}; }}
        .cc-info {{ color:#4A5B70; font-size:.84rem; margin:.15rem 0; }}
        .cc-resumo {{ color:#5B6B80; font-size:.82rem; line-height:1.4; margin-top:.45rem; min-height:2.3em;
            display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
        .cc-motivo {{ color:#0B6E86; font-size:.8rem; margin-top:.35rem; font-weight:600; }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.cc-topo) {{ background:#fff; border-radius:14px;
            box-shadow:0 1px 3px rgba(11,37,69,.06); transition: box-shadow .15s, transform .15s; }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.cc-topo):hover {{
            box-shadow:0 8px 22px rgba(11,37,69,.12); transform: translateY(-2px); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def cabecalho(titulo: str, subtitulo: str) -> None:
    st.markdown(
        f'<div class="cabecalho"><h1>{html.escape(titulo)}</h1><p>{html.escape(subtitulo)}</p></div>',
        unsafe_allow_html=True,
    )


def etiqueta(texto: str, cor: str = "azul") -> str:
    """Etiqueta colorida; o texto é sempre escapado (pode vir de fontes externas)."""
    return f'<span class="etiqueta et-{cor}">{html.escape(str(texto))}</span>'


def cor_estado(estado: str) -> str:
    if estado in ("Aprovado", "Contratado", "Respondeu", "Em negociação"):
        return "verde"
    if estado in ("Rejeitado",):
        return "vermelha"
    if estado in ("Arquivado", "Sem resposta"):
        return "cinza"
    return "azul"


def avisar(mensagem: str, tipo: str = "success") -> None:
    """Guarda uma mensagem para ser mostrada depois do próximo recarregamento."""
    st.session_state.setdefault("avisos", []).append((tipo, mensagem))


def mostrar_avisos() -> None:
    for tipo, mensagem in st.session_state.pop("avisos", []):
        getattr(st, tipo)(mensagem)


def utilizador_atual() -> dict:
    return st.session_state["utilizador"]


def chave_api(nome: str) -> str:
    """Chave configurada no servidor (Secrets do alojamento ou ficheiro .env)."""
    return obter_variavel(nome)


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def _criar_admin_inicial() -> bool:
    """Cria o primeiro administrador a partir dos Secrets. Devolve True se já existir algum utilizador."""
    if db.contar_utilizadores() > 0:
        return True
    # Não existe registo público: o primeiro administrador vem dos Secrets do alojamento
    # (ADMIN_EMAIL / ADMIN_PASSWORD), que só o dono da aplicação controla.
    email_admin = obter_variavel("ADMIN_EMAIL")
    password_admin = obter_variavel("ADMIN_PASSWORD")
    if not email_admin or not password_admin or validar_password(password_admin):
        return False
    try:
        db.criar_utilizador(obter_variavel("ADMIN_NOME") or "Administrador",
                            email_admin, password_admin, "Administrador")
    except ErroBaseDados:
        pass  # pode ter sido criado ao mesmo tempo noutra sessão
    return db.contar_utilizadores() > 0


GUIA_UTILIZACAO = """
**1. Entrar** — use o email e a palavra-passe que o administrador lhe deu.

**2. Procurar profissionais** — na barra lateral escolha as especialidades, a zona e o raio, e clique
em **Procurar profissionais**. A pesquisa demora um a dois minutos e guarda os candidatos encontrados.

**3. Ver os candidatos** — na página **Candidatos** cada profissional aparece num cartão com o score,
a zona, a disponibilidade e o tipo de contacto. Use a pesquisa e os filtros rápidos para encontrar
quem precisa (por exemplo, «Com contacto direto» ou «Disponíveis»).

**4. Contactar** — clique em **Detalhes** e abra o separador **Contacto**:
- com telefone ou email, use **Telefonar**, **Abrir WhatsApp** ou **Enviar email**;
- sem contacto direto, use **Abrir perfil original** e envie mensagem pela plataforma (por exemplo, LinkedIn).

Depois registe o contacto em **Registar contacto efetuado** e, se precisar, crie um lembrete.

**5. Acompanhar** — no separador **Processo** atualize o estado (Contactado, Entrevista marcada,
Aprovado…). Notas, tarefas e entrevistas ficam guardadas na ficha de cada candidato.

**6. Serviço imediato** — para uma necessidade urgente, indique o serviço e a zona e veja primeiro quem
pode começar já e está mais perto.

**7. Exportar** — na página **Candidatos** exporte a lista filtrada para Excel, CSV ou PDF.

Dúvidas de acesso ou palavra-passe esquecida: fale com um administrador da plataforma.
"""


@st.dialog("Como usar a plataforma", width="large")
def _mostrar_guia() -> None:
    st.markdown(GUIA_UTILIZACAO)


def ecra_autenticacao() -> None:
    """Ecrã de início de sessão (não existe registo público)."""
    st.markdown("<style>.block-container { max-width: 1200px; padding-top: 6.5rem; }</style>",
                unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.55, 1])
    with centro:
        try:
            configurada = _criar_admin_inicial()
        except ErroBaseDados as exc:
            st.error(str(exc))
            st.stop()
        if not configurada:
            st.warning("A aplicação ainda não está configurada. O responsável técnico deve definir "
                       "ADMIN_EMAIL e ADMIN_PASSWORD (mínimo de 8 caracteres, com letras e números) "
                       "nos Secrets do alojamento.")
            st.stop()

        with st.form("iniciar_sessao", border=True):
            st.markdown(
                f'<div class="login-cabecalho"><div class="login-logo">❄️</div>'
                f'<div><div class="login-nome">{html.escape(NOME_APP)}</div>'
                f'<div class="login-texto">Inicie sessão com os dados fornecidos pelo administrador.</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            email = st.text_input("Email", placeholder="nome@empresa.pt")
            password = st.text_input("Palavra-passe", type="password", placeholder="••••••••")
            if st.form_submit_button("Entrar", icon=":material/login:", type="primary", **LARGURA):
                try:
                    utilizador = db.autenticar(email, password)
                except ErroBaseDados as exc:
                    utilizador = None
                    st.error(str(exc))
                if utilizador:
                    st.session_state["utilizador"] = utilizador
                    st.rerun()
                else:
                    time.sleep(1.5)  # abranda tentativas repetidas
                    st.error("Email ou palavra-passe incorretos, ou conta inativa.")

        if st.button("Como usar a plataforma", icon=":material/help:", type="tertiary", key="link_guia",
                     **LARGURA):
            _mostrar_guia()


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

_OMISSOES_PESQUISA = {
    "f_especialidades": [], "f_localizacoes": ["Grande Lisboa"], "f_outra": "", "f_raio": 30,
    "f_disponibilidade": [], "f_tipo": TIPOS_CONTRATACAO[0],
    "f_max": 20, "f_fgas": False,
}


def _nova_pesquisa() -> None:
    for chave, valor in _OMISSOES_PESQUISA.items():
        st.session_state[chave] = valor


def barra_lateral() -> str:
    u = utilizador_atual()
    pode_pesquisar = u["perfil"] in ("Administrador", "Recrutador")
    for chave, valor in _OMISSOES_PESQUISA.items():
        st.session_state.setdefault(chave, valor)

    with st.sidebar:
        st.markdown(
            '<div class="logo-app"><div class="icone">❄️</div><div>'
            f'<div class="nome">{html.escape(NOME_APP)}</div>'
            '<div class="sub">Recrutamento técnico com IA</div></div></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"{u['nome']} · {u['perfil']}")
        pagina = st.radio(
            "Navegação", PAGINAS_POR_PERFIL[u["perfil"]],
            format_func=lambda p: f":material/{ICONES_PAGINA[p]}: {p}", key="pagina", label_visibility="collapsed",
            on_change=lambda: st.session_state.pop("candidato_aberto", None),
        )
        st.divider()

        if pode_pesquisar:
            st.subheader("Procurar profissionais")
            st.button("Limpar critérios", icon=":material/restart_alt:", on_click=_nova_pesquisa, **LARGURA,
                      help="Limpa os critérios para começar uma pesquisa nova.")
            st.multiselect("Especialidades", TODAS_ESPECIALIDADES, key="f_especialidades",
                           placeholder="Escolha uma ou mais",
                           help="Sem seleção, são procurados técnicos de AVAC e refrigeração em geral.")
            st.multiselect("Localização", LOCALIZACOES, key="f_localizacoes", placeholder="Escolha as zonas")
            if "Outra localização" in st.session_state["f_localizacoes"]:
                st.text_input("Outra localização", key="f_outra", placeholder="Ex.: Torres Vedras")
            st.slider("Raio de pesquisa (km)", 5, 150, key="f_raio", step=5)
            st.multiselect("Disponibilidade", DISPONIBILIDADES, key="f_disponibilidade",
                           placeholder="Qualquer")
            st.selectbox("Tipo de contratação", TIPOS_CONTRATACAO, key="f_tipo")
            st.checkbox("Exigir certificação F-Gas", key="f_fgas")
            st.slider("Número máximo de resultados", 5, 50, key="f_max", step=5,
                      help="Resultados de pesquisa analisados pela IA. Mais resultados = mais tempo e custo.")

            if st.button("Procurar profissionais", icon=":material/search:", type="primary", **LARGURA):
                st.session_state["pedido_pesquisa"] = {
                    "especialidades": st.session_state["f_especialidades"],
                    "localizacoes": st.session_state["f_localizacoes"],
                    "outra_localizacao": st.session_state.get("f_outra", ""),
                    "raio_km": st.session_state["f_raio"],
                    "disponibilidade": st.session_state["f_disponibilidade"],
                    "tipo_contratacao": st.session_state["f_tipo"],
                    "exige_fgas": st.session_state["f_fgas"],
                    "max_resultados": st.session_state["f_max"],
                    "urgente": True,
                }
            st.divider()

        if st.button("Terminar sessão", **LARGURA):
            for chave in list(st.session_state.keys()):
                del st.session_state[chave]
            st.rerun()
    return pagina


# ---------------------------------------------------------------------------
# Prospeção com IA
# ---------------------------------------------------------------------------

def executar_prospecao(parametros: dict) -> None:
    """Pesquisa (Tavily) -> análise (Anthropic) -> validação -> gravação sem duplicados."""
    u = utilizador_atual()
    if not chave_api("TAVILY_API_KEY"):
        st.error("Chave API em falta no servidor: TAVILY_API_KEY. O administrador deve configurá-la "
                 "nos «Secrets» do alojamento (ou no ficheiro .env).")
        return

    # Todas as pesquisas são tratadas como urgentes: número máximo de consultas.
    consultas = gerar_consultas(parametros, 12)
    criterios = {k: v for k, v in parametros.items() if k not in ("max_resultados", "urgente")}
    criterios["prioridade"] = ("Alta. A necessidade é urgente: privilegiar profissionais com "
                               "disponibilidade imediata e contacto direto.")

    try:
        pesquisa_id = db.registar_pesquisa(u["nome"], parametros, consultas, bool(parametros.get("urgente")))
    except ErroBaseDados as exc:
        st.error(str(exc))
        return

    with st.status("A procurar profissionais…", expanded=True) as estado:
        # 1) Pesquisa em fontes públicas
        st.write(f"{len(consultas)} consultas geradas a partir dos critérios.")
        barra = st.progress(0.0, text="A pesquisar em fontes públicas…")
        try:
            resultados, avisos_pesquisa = executar_pesquisa(
                chave_api("TAVILY_API_KEY"), consultas, int(parametros.get("max_resultados", 20)),
                progresso=lambda feito, total: barra.progress(
                    feito / total, text=f"A pesquisar… {feito}/{total} consultas"),
            )
        except ErroPesquisa as exc:
            estado.update(label="A pesquisa falhou", state="error")
            st.error(f"Erro da Tavily: {exc}")
            return
        except Exception:
            estado.update(label="A pesquisa falhou", state="error")
            st.error("Ocorreu um erro inesperado durante a pesquisa. Tente novamente.")
            return
        for aviso in avisos_pesquisa:
            st.warning(f"Algumas consultas falharam: {aviso}")

        if not resultados:
            db.concluir_pesquisa(pesquisa_id, 0, 0, 0, 0, [])
            estado.update(label="Nenhum resultado encontrado", state="complete")
            st.warning("Nenhum resultado encontrado. Experimente alargar a localização, "
                       "reduzir os requisitos ou escolher outras especialidades.")
            return
        st.write(f"{len(resultados)} resultados únicos encontrados.")

        # 2) Análise: IA da Anthropic; sem chave ou em caso de falha, extração por regras.
        candidatos, descartados, avisos_ia = [], [], []
        usar_ia = bool(chave_api("ANTHROPIC_API_KEY"))
        if usar_ia:
            barra_ia = st.progress(0.0, text="A analisar perfis com IA…")
            try:
                candidatos, descartados, avisos_ia = analisar_resultados(
                    chave_api("ANTHROPIC_API_KEY"), resultados, criterios,
                    progresso=lambda feito, total: barra_ia.progress(
                        feito / total, text=f"A analisar perfis com IA… {feito}/{total} lotes"),
                )
            except ErroIA as exc:
                st.warning(f"A IA não está disponível ({exc}). Os perfis foram identificados "
                           "automaticamente por palavras-chave.")
                usar_ia = False
            except Exception:
                st.warning("A IA não respondeu. Os perfis foram identificados automaticamente por "
                           "palavras-chave.")
                usar_ia = False
        if not usar_ia:
            if not chave_api("ANTHROPIC_API_KEY"):
                st.write("Modo sem IA: perfis identificados automaticamente por palavras-chave.")
            candidatos, descartados = analisar_sem_ia(resultados, criterios)
        for aviso in avisos_ia:
            st.warning(f"Parte dos resultados não foi analisada: {aviso}")

        # 3) Gravação sem duplicados
        novos, duplicados, ids = 0, 0, []
        try:
            for candidato in candidatos:
                situacao, candidato_id = db.guardar_candidato(candidato, pesquisa_id, u["nome"])
                ids.append(candidato_id)
                novos += situacao == "novo"
                duplicados += situacao == "duplicado"
            tipo_por_url = {c.url_fonte: c.tipo_resultado for c in candidatos}
            tipo_por_url.update({d["url"]: d["tipo_resultado"] for d in descartados})
            fontes = [{**r, "tipo_resultado": tipo_por_url.get(r["url"], "")} for r in resultados]
            db.concluir_pesquisa(pesquisa_id, len(resultados), len(candidatos), novos, duplicados, fontes)
        except ErroBaseDados as exc:
            estado.update(label="Erro ao guardar os candidatos", state="error")
            st.error(str(exc))
            return

        st.session_state["ids_ultima_pesquisa"] = ids
        estado.update(label=f"Prospeção concluída — {novos} novos candidatos", state="complete",
                      expanded=False)

    if not candidatos:
        st.warning(f"Foram analisados {len(resultados)} resultados, mas nenhum corresponde a um "
                   "profissional individual (empresas, anúncios e diretórios são ignorados).")
        return
    st.success(f"{novos} novos candidatos guardados · {duplicados} já existiam (duplicados ignorados) · "
               f"{len(descartados)} resultados descartados. Consulte-os na página «Candidatos».")


# ---------------------------------------------------------------------------
# Página: Dashboard
# ---------------------------------------------------------------------------

def _grafico(fig, legenda: bool = False) -> None:
    fig.update_layout(margin=dict(l=10, r=20, t=50, b=10), paper_bgcolor="#FFFFFF",
                      plot_bgcolor="#FFFFFF", font=dict(color=AZUL_ESCURO), title_font_size=16,
                      showlegend=legenda, height=340,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.3, title_text=""))
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    # Sem barra de ferramentas do Plotly: evita sobreposição com o título em ecrãs estreitos.
    st.plotly_chart(fig, config={"displayModeBar": False}, **LARGURA)


def _barras(contagem: pd.DataFrame, categoria: str, titulo: str, cor: str) -> None:
    """Barras horizontais com o valor escrito na barra — legíveis em qualquer largura de ecrã."""
    contagem = contagem.copy()
    # Nomes compridos são encurtados para não roubarem espaço às barras.
    contagem[categoria] = contagem[categoria].astype(str).apply(lambda s: s if len(s) <= 26 else s[:25] + "…")
    fig = px.bar(contagem, x="Candidatos", y=categoria, orientation="h", text="Candidatos",
                 title=titulo, color_discrete_sequence=[cor])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(title=None)
    fig.update_layout(height=max(260, 70 + 34 * len(contagem)))
    _grafico(fig)


ETAPAS_FUNIL = [("Novos", ["Novo", "Pré-selecionado", "Contacto pendente"]),
                ("Contactados", ["Contactado", "Sem resposta"]),
                ("Responderam", ["Respondeu"]),
                ("Em entrevista", ["Entrevista marcada", "Em avaliação técnica"]),
                ("Aprovados", ["Aprovado", "Em negociação"]),
                ("Contratados", ["Contratado"])]


def _linha_candidato(c: pd.Series, prefixo: str, nota: str = "") -> None:
    """Linha compacta de candidato com ações diretas."""
    esp = lista_para_texto((c["especialidades"] or [])[:1]) or c["cargo"] or "Especialidade não identificada"
    local = c["concelho"] or c["localizacao"] or "Zona não identificada"
    contacto = " · ".join(n for n, v in (("Telefone", c["telefone"]), ("Email", c["email"])) if v) \
        or "Contacto pelo perfil"
    with st.container(border=True):
        info, acoes = st.columns([2.7, 2.3], vertical_alignment="center")
        info.markdown(
            f'<div class="ln-topo"><span class="ln-nome">{html.escape(str(c["nome"]))}</span>'
            f'<span class="ln-pont">{int(c["score"] or 0)}%</span></div>'
            f'<div class="ln-sub">{html.escape(esp)} · {html.escape(local)} · {html.escape(contacto)}</div>'
            + (f'<div class="ln-nota">{html.escape(nota)}</div>' if nota else ""),
            unsafe_allow_html=True,
        )
        a, b = acoes.columns(2)
        if a.button("Abrir", key=f"{prefixo}_{c['id']}", icon=":material/visibility:", type="primary",
                    help="Abrir a ficha para contactar e registar", **LARGURA):
            st.session_state["candidato_aberto"] = int(c["id"])
            st.rerun()
        url = url_segura(c["url_perfil"]) or url_segura(c["url_fonte"])
        if url:
            b.link_button("Perfil", url, icon=":material/open_in_new:", **LARGURA)


def pagina_painel(df: pd.DataFrame) -> None:
    """Painel de trabalho: o que precisa de ação hoje."""
    cabecalho("Painel", "O que precisa da sua atenção hoje")
    if _vista_detalhe():
        return
    if df.empty:
        st.info("Ainda não existem candidatos. Use «Procurar profissionais», na barra lateral, "
                "para encontrar os primeiros profissionais.")
        return

    # Funil do processo numa só linha.
    passos = []
    for nome, estados in ETAPAS_FUNIL:
        total = int(df["estado"].isin(estados).sum())
        passos.append(f'<div class="funil-passo"><b>{total}</b><span>{nome}</span></div>')
    st.markdown('<div class="funil">' + '<div class="funil-seta">›</div>'.join(passos) + "</div>",
                unsafe_allow_html=True)

    ativos = df[~df["estado"].isin(["Arquivado", "Rejeitado", "Contratado"])]
    hoje = date.today()
    esquerda, direita = st.columns([1.75, 1], gap="large")

    with esquerda:
        # 1) Contactar primeiro: ainda não contactados, disponíveis e com melhor pontuação.
        por_contactar = ativos[ativos["data_primeiro_contacto"].isna()]
        peso = {"Confirmada": 0, "Provável": 1, "Desconhecida": 2, "Não disponível": 3}
        por_contactar = por_contactar.assign(
            _d=por_contactar["disponibilidade_classificacao"].map(peso).fillna(2),
            _c=~(por_contactar["telefone"].astype(bool) | por_contactar["email"].astype(bool)),
        ).sort_values(["_d", "_c", "score"], ascending=[True, True, False])
        with st.container(border=True):
            st.markdown(f"**Contactar primeiro ({len(por_contactar)})**")
            st.caption("Ainda não contactados — primeiro os disponíveis, com contacto direto e melhor pontuação.")
            if por_contactar.empty:
                st.caption("Todos os candidatos ativos já foram contactados.")
            for _, c in por_contactar.head(6).iterrows():
                _linha_candidato(c, "contactar")
            if len(por_contactar) > 6:
                st.caption(f"Mais {len(por_contactar) - 6} na página «Candidatos» "
                           "(filtro «Ainda não contactados»).")

        # 2) Sem resposta: contactados há 3 dias ou mais, sem avanço.
        limite = hoje - timedelta(days=3)
        sem_resposta = ativos[ativos["estado"].isin(["Contactado", "Sem resposta"])
                              & ativos["data_ultimo_contacto"].notna()]
        sem_resposta = sem_resposta[sem_resposta["data_ultimo_contacto"] <= limite] \
            .sort_values("data_ultimo_contacto")
        with st.container(border=True):
            st.markdown(f"**Voltar a contactar ({len(sem_resposta)})**")
            st.caption("Contactados há 3 dias ou mais, ainda sem resposta.")
            if sem_resposta.empty:
                st.caption("Nenhum candidato à espera de novo contacto.")
            for _, c in sem_resposta.head(6).iterrows():
                dias = (hoje - c["data_ultimo_contacto"]).days
                _linha_candidato(c, "recontactar", f"Último contacto há {dias} dias")

    with direita:
        # 3) Tarefas em atraso e de hoje.
        try:
            tarefas = [x for x in db.listar_tarefas(apenas_pendentes=True)
                       if x["data_limite"] is None or x["data_limite"] <= hoje]
        except ErroBaseDados as exc:
            tarefas = []
            st.error(str(exc))
        with st.container(border=True):
            st.markdown(f"**Tarefas para hoje ({len(tarefas)})**")
            if tarefas:
                listar_tarefas_interativas(tarefas[:10], "painel_t", mostrar_candidato=True)
            else:
                st.caption("Sem tarefas pendentes para hoje.")

        # 4) Próximas entrevistas.
        try:
            entrevistas = [e for e in db.listar_entrevistas()
                           if e["data"] and e["data"].date() >= hoje and e["resultado"] == "Por realizar"]
        except ErroBaseDados as exc:
            entrevistas = []
            st.error(str(exc))
        entrevistas.sort(key=lambda e: e["data"])
        with st.container(border=True):
            st.markdown(f"**Próximas entrevistas ({len(entrevistas)})**")
            if not entrevistas:
                st.caption("Sem entrevistas marcadas.")
            for e in entrevistas[:6]:
                st.markdown(f"{formatar_data(e['data'])} · **{html.escape(e['candidato'])}**  \n"
                            f"<span class='ln-sub'>{html.escape(e['tipo'])} · {html.escape(e['entrevistador'])}</span>",
                            unsafe_allow_html=True)

        # 5) Pesquisas recentes.
        try:
            pesquisas = db.listar_pesquisas_df().head(4)
        except ErroBaseDados:
            pesquisas = pd.DataFrame()
        with st.container(border=True):
            st.markdown("**Pesquisas recentes**")
            if pesquisas.empty:
                st.caption("Ainda não foram feitas pesquisas.")
            for _, p in pesquisas.iterrows():
                params = p["parametros"] or {}
                esp = lista_para_texto((params.get("especialidades") or [])[:2]) or "Técnicos de AVAC em geral"
                st.markdown(f"{formatar_data(p['data'])} · {int(p['novos'] or 0)} novos  \n"
                            f"<span class='ln-sub'>{html.escape(esp)}</span>", unsafe_allow_html=True)


def _estatisticas(df: pd.DataFrame) -> None:
    """Gráficos de acompanhamento (separador Estatísticas da Administração)."""
    if df.empty:
        st.info("Ainda não existem dados para mostrar.")
        return
    ativos = df[df["estado"] != "Arquivado"]
    c1, c2 = st.columns(2)
    with c1:
        esp = ativos["especialidades"].explode().dropna()
        esp = esp[esp.astype(str).str.strip() != ""]
        if not esp.empty:
            contagem = esp.value_counts().head(12).sort_values().reset_index()
            contagem.columns = ["Especialidade", "Candidatos"]
            _barras(contagem, "Especialidade", "Candidatos por especialidade", CIANO)
    with c2:
        local = ativos["concelho"].where(ativos["concelho"].astype(bool), ativos["localizacao"])
        local = local.replace("", "Não identificada").fillna("Não identificada")
        contagem = local.value_counts().head(12).sort_values().reset_index()
        contagem.columns = ["Localização", "Candidatos"]
        _barras(contagem, "Localização", "Candidatos por localização", AZUL_ESCURO)

    c1, c2 = st.columns(2)
    with c1:
        faixas = pd.cut(df["score"], bins=[-1, 20, 40, 60, 80, 100],
                        labels=["0–20%", "21–40%", "41–60%", "61–80%", "81–100%"])
        contagem = faixas.value_counts().reindex(["81–100%", "61–80%", "41–60%", "21–40%", "0–20%"][::-1])
        contagem = contagem.fillna(0).astype(int).reset_index()
        contagem.columns = ["Pontuação", "Candidatos"]
        _barras(contagem, "Pontuação", "Distribuição das pontuações", CIANO)
    with c2:
        contagem = df["estado"].value_counts().reindex(ESTADOS[::-1]).dropna().astype(int).reset_index()
        contagem.columns = ["Estado", "Candidatos"]
        _barras(contagem, "Estado", "Candidatos por estado", AZUL_ESCURO)

    try:
        pesquisas = db.listar_pesquisas_df()
    except ErroBaseDados as exc:
        st.error(str(exc))
        return
    if not pesquisas.empty:
        pesquisas["Dia"] = pd.to_datetime(pesquisas["data"]).dt.date
        evolucao = pesquisas.groupby("Dia").agg(Pesquisas=("id", "count"),
                                                **{"Novos candidatos": ("novos", "sum")}).reset_index()
        evolucao = evolucao.melt(id_vars="Dia", var_name="Indicador", value_name="Total")
        fig = px.line(evolucao, x="Dia", y="Total", color="Indicador", markers=True,
                      title="Evolução das pesquisas ao longo do tempo",
                      color_discrete_sequence=[AZUL_ESCURO, CIANO])
        fig.update_xaxes(title=None, tickformat="%d/%m", tickangle=0, dtick=86400000)
        fig.update_yaxes(title=None)
        _grafico(fig, legenda=True)




# ---------------------------------------------------------------------------
# Detalhe do candidato
# ---------------------------------------------------------------------------

def _linhas_lista(itens, vazio: str = "Não identificado") -> None:
    if itens:
        for item in itens:
            st.markdown(f"- {html.escape(str(item))}")
    else:
        st.caption(vazio)


def mostrar_detalhe(candidato_id: int) -> None:
    """Vista detalhada de um candidato, com todas as ações do ciclo de recrutamento."""
    u = utilizador_atual()
    perfil = u["perfil"]
    gestor = perfil == "Gestor"
    try:
        c = db.obter_candidato(candidato_id)
    except ErroBaseDados as exc:
        st.error(str(exc))
        return
    if not c:
        st.warning("Este candidato já não existe.")
        st.session_state.pop("candidato_aberto", None)
        return
    k = f"c{candidato_id}"  # prefixo para chaves únicas dos componentes

    esp = lista_para_texto(c["especialidades"]) or c["cargo"] or "Especialidade não identificada"
    local = c["localizacao"] or c["concelho"] or "Localização não identificada"
    etiquetas = etiqueta(c["estado"], cor_estado(c["estado"])) + etiqueta(f"Pontuação {c['score']}%", "escura")
    etiquetas += etiqueta(c["recomendacao"], "verde" if c["recomendacao"] in RECOMENDACOES[:2] else "cinza")
    etiquetas += etiqueta(f"Disponibilidade: {c['disponibilidade_classificacao']}",
                          "verde" if c["disponibilidade_classificacao"] in ("Confirmada", "Provável") else "cinza")
    if c["certificacao_fgas"] == "Sim":
        etiquetas += etiqueta("F-Gas", "verde")
    st.markdown(
        f'<div class="cartao"><h3>{html.escape(c["nome"])}</h3>'
        f'<div class="linha">{html.escape(esp)}</div>'
        f'<div class="linha">{html.escape(local)}</div>{etiquetas}</div>',
        unsafe_allow_html=True,
    )

    nomes_abas = [":material/person: Perfil", ":material/call: Contacto", ":material/folder_open: Processo",
                  ":material/edit_note: Notas e tarefas", ":material/handshake: Entrevistas e contratação"]
    if perfil == "Administrador":
        nomes_abas.append(":material/shield: Dados e RGPD")
    abas = st.tabs(nomes_abas)

    # ----- Perfil -----
    with abas[0]:
        with st.expander("Resumo profissional", expanded=True):
            st.write(limpar_resumo(c["resumo"], 1200) or "Não informado")
        with st.expander("Pontuação e justificação", expanded=True):
            a, b = st.columns(2)
            a.progress(c["score"] / 100, text=f"Pontuação de adequação: {c['score']}%")
            b.progress(c["nivel_confianca"] / 100, text=f"Confiança na informação: {c['nivel_confianca']}%")
            st.write(c["justificacao_score"] or "Não informado")
        with st.expander("Experiência"):
            anos = c["anos_experiencia"]
            st.markdown(f"**Anos de experiência:** {anos if anos is not None else 'Não identificado'}")
            experiencias = c["experiencias"] or {}
            colunas = st.columns(3)
            for indice, (chave, rotulo) in enumerate(AREAS_EXPERIENCIA.items()):
                valor = experiencias.get(chave, "Não identificado")
                colunas[indice % 3].markdown(f"{rotulo}: **{valor}**")
        with st.expander("Competências"):
            _linhas_lista(c["competencias"])
        with st.expander("Certificações e mobilidade"):
            a, b, d = st.columns(3)
            a.markdown(f"**Certificação F-Gas:** {c['certificacao_fgas']}")
            b.markdown(f"**Carta de condução:** {c['carta_conducao']}")
            d.markdown(f"**Viatura própria:** {c['viatura_propria']}")
            _linhas_lista(c["certificacoes"], "Sem certificações identificadas")
            st.markdown(f"**Disponibilidade:** {html.escape(c['disponibilidade'] or 'Não informado')}")
            a, b, d = st.columns(3)
            a.markdown(f"**Imediata:** {c['disponibilidade_imediata']}")
            b.markdown(f"**Urgências:** {c['disponibilidade_urgencias']}")
            d.markdown(f"**Deslocações:** {c['disponibilidade_deslocacoes']}")
        with st.expander("Fontes"):
            st.markdown(f"**Fonte:** {html.escape(c['fonte'] or 'Não informado')}  \n"
                        f"**Data de recolha:** {formatar_data(c['data_recolha'])}")
            if url_segura(c["url_fonte"]):
                st.link_button("Abrir a fonte original", c["url_fonte"])
            st.caption("Dados profissionais recolhidos de fontes públicas. Confirme-os sempre "
                       "diretamente com o candidato.")

    # ----- Contacto -----
    with abas[1]:
        a, b = st.columns(2)
        with a:
            st.markdown("**Telefone** (use o ícone para copiar)")
            if c["telefone"]:
                st.code(c["telefone"], language=None)
            else:
                st.caption("Não disponível publicamente")
        with b:
            st.markdown("**Email** (use o ícone para copiar)")
            if c["email"]:
                st.code(c["email"], language=None)
            else:
                st.caption("Não disponível publicamente")

        st.markdown("**Abrir canal de contacto** — o contacto é feito diretamente por si.")
        ligacoes = [
            ("Abrir perfil original", ":material/open_in_new:",
             url_segura(c["url_perfil"]) or url_segura(c["url_fonte"])),
            ("Enviar email", ":material/mail:", link_mailto(c["email"], "Oportunidade profissional", "")),
            ("Abrir WhatsApp", ":material/chat:", link_whatsapp(c["telefone"], "")),
            ("Telefonar", ":material/call:", link_telefone(c["telefone"])),
        ]
        disponiveis = [ligacao for ligacao in ligacoes if ligacao[2]]
        if disponiveis:
            for coluna, (rotulo, icone, destino) in zip(st.columns(4), disponiveis):
                coluna.link_button(rotulo, destino, icon=icone, **LARGURA)
        else:
            st.caption("Este candidato não tem contactos nem perfil público registados.")

        if not gestor:
            st.divider()
            with st.form(f"{k}_contacto", clear_on_submit=True):
                st.markdown("**Registar contacto efetuado**")
                a, b = st.columns(2)
                meio = a.selectbox("Meio de contacto", MEIOS_CONTACTO)
                resultado = b.selectbox("Resultado", RESULTADOS_CONTACTO)
                notas = st.text_area("Notas do contacto", height=80)
                a, b = st.columns(2)
                lembrete = a.checkbox("Criar lembrete para novo contacto")
                data_lembrete = b.date_input("Data do lembrete", value=date.today() + timedelta(days=2),
                                             format="DD/MM/YYYY")
                if st.form_submit_button("Registar contacto", type="primary"):
                    try:
                        db.registar_contacto(candidato_id, u["nome"], meio, resultado, notas)
                        if lembrete:
                            db.criar_tarefa(f"Voltar a contactar {c['nome']}", u["nome"],
                                            data_lembrete, u["nome"], candidato_id)
                        avisar("Contacto registado.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))

        st.markdown("**Histórico de contactos**")
        try:
            contactos = db.listar_contactos(candidato_id)
        except ErroBaseDados as exc:
            contactos = []
            st.error(str(exc))
        if contactos:
            tabela = pd.DataFrame(contactos).rename(columns={
                "data": "Data", "meio": "Meio", "resultado": "Resultado",
                "utilizador": "Utilizador", "notas": "Notas"})
            st.dataframe(tabela, hide_index=True, **LARGURA, column_config={
                "Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})
        else:
            st.caption("Ainda não foi registado nenhum contacto.")

    # ----- Processo -----
    with abas[2]:
        with st.form(f"{k}_processo"):
            estados = ESTADOS if not gestor else list(dict.fromkeys([c["estado"], *ESTADOS_GESTOR]))
            a, b, d = st.columns(3)
            estado = a.selectbox("Estado", estados, index=estados.index(c["estado"]) if c["estado"] in estados else 0)
            responsavel = b.text_input("Responsável pelo candidato", value=c["responsavel"], disabled=gestor)
            tipos = ["", *TIPOS_CONTRATACAO]
            tipo = d.selectbox("Tipo de contrato pretendido", tipos, disabled=gestor,
                               index=tipos.index(c["tipo_contrato_pretendido"])
                               if c["tipo_contrato_pretendido"] in tipos else 0)
            a, b, d = st.columns(3)
            primeiro = a.date_input("Data do primeiro contacto", value=c["data_primeiro_contacto"],
                                    format="DD/MM/YYYY", disabled=gestor)
            ultimo = b.date_input("Data do último contacto", value=c["data_ultimo_contacto"],
                                  format="DD/MM/YYYY", disabled=gestor)
            data_proxima = d.date_input("Data da próxima ação", value=c["data_proxima_acao"],
                                        format="DD/MM/YYYY", disabled=gestor)
            proxima = st.text_input("Próxima ação", value=c["proxima_acao"], disabled=gestor)
            a, b, d = st.columns(3)
            salario = a.text_input("Expectativa salarial", value=c["expectativa_salarial"], disabled=gestor)
            inicio = b.text_input("Disponibilidade de início", value=c["disponibilidade_inicio"], disabled=gestor)
            area = d.text_input("Área geográfica pretendida", value=c["area_geografica_pretendida"],
                                disabled=gestor)
            documentos = st.text_area("Documentos recebidos", value=c["documentos_recebidos"], height=70,
                                      disabled=gestor, placeholder="Ex.: CV, certificado F-Gas, carta de condução")
            entrevista = st.text_area("Resultado da entrevista", value=c["resultado_entrevista"], height=80)
            observacoes = st.text_area("Observações do gestor", value=c["observacoes_gestor"], height=80,
                                       disabled=perfil == "Recrutador")
            if st.form_submit_button("Guardar alterações", type="primary"):
                alteracoes = {"estado": estado, "resultado_entrevista": entrevista}
                if not gestor:
                    alteracoes.update({
                        "responsavel": responsavel, "tipo_contrato_pretendido": tipo,
                        "data_primeiro_contacto": primeiro, "data_ultimo_contacto": ultimo,
                        "data_proxima_acao": data_proxima, "proxima_acao": proxima,
                        "expectativa_salarial": salario, "disponibilidade_inicio": inicio,
                        "area_geografica_pretendida": area, "documentos_recebidos": documentos,
                    })
                if perfil != "Recrutador":
                    alteracoes["observacoes_gestor"] = observacoes
                try:
                    n = db.atualizar_candidato(candidato_id, alteracoes, u["nome"])
                    avisar(f"{n} campo(s) atualizado(s)." if n else "Não havia alterações a guardar.",
                           "success" if n else "info")
                    st.rerun()
                except ErroBaseDados as exc:
                    st.error(str(exc))

        if not gestor:
            with st.expander("Corrigir dados do perfil"):
                with st.form(f"{k}_dados"):
                    a, b = st.columns(2)
                    nome = a.text_input("Nome", value=c["nome"])
                    cargo = b.text_input("Cargo", value=c["cargo"])
                    a, b = st.columns(2)
                    telefone = a.text_input("Telefone profissional", value=c["telefone"])
                    email = b.text_input("Email profissional", value=c["email"])
                    a, b, d = st.columns(3)
                    localizacao = a.text_input("Localização", value=c["localizacao"])
                    fgas = b.selectbox("Certificação F-Gas", TRI_ESTADO, index=TRI_ESTADO.index(c["certificacao_fgas"]))
                    disp = d.selectbox("Disponibilidade", CLASSIF_DISPONIBILIDADE,
                                       index=CLASSIF_DISPONIBILIDADE.index(c["disponibilidade_classificacao"]))
                    a, b = st.columns(2)
                    carta = a.selectbox("Carta de condução", TRI_ESTADO, index=TRI_ESTADO.index(c["carta_conducao"]))
                    viatura = b.selectbox("Viatura própria", TRI_ESTADO, index=TRI_ESTADO.index(c["viatura_propria"]))
                    if st.form_submit_button("Guardar dados do perfil"):
                        try:
                            db.atualizar_candidato(candidato_id, {
                                "nome": nome, "cargo": cargo, "telefone": telefone, "email": email,
                                "localizacao": localizacao, "certificacao_fgas": fgas,
                                "disponibilidade_classificacao": disp, "carta_conducao": carta,
                                "viatura_propria": viatura}, u["nome"])
                            avisar("Dados do perfil atualizados.")
                            st.rerun()
                        except ErroBaseDados as exc:
                            st.error(str(exc))

    # ----- Notas e tarefas -----
    with abas[3]:
        a, b = st.columns(2)
        with a:
            st.markdown("**Notas internas**")
            with st.form(f"{k}_nota", clear_on_submit=True):
                texto = st.text_area("Nova nota", height=90, label_visibility="collapsed",
                                     placeholder="Escreva uma nota interna…")
                if st.form_submit_button("Adicionar nota"):
                    try:
                        db.adicionar_nota(candidato_id, u["nome"], texto)
                        avisar("Nota adicionada.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))
            try:
                for nota in db.listar_notas(candidato_id):
                    with st.container(border=True):
                        st.caption(f"{formatar_data(nota['data'])} · {nota['utilizador']}")
                        st.text(nota["texto"])
            except ErroBaseDados as exc:
                st.error(str(exc))
        with b:
            st.markdown("**Próximas tarefas**")
            with st.form(f"{k}_tarefa", clear_on_submit=True):
                titulo = st.text_input("Tarefa", placeholder="Ex.: Pedir certificado F-Gas")
                data_limite = st.date_input("Data limite", value=date.today() + timedelta(days=1),
                                            format="DD/MM/YYYY")
                if st.form_submit_button("Criar tarefa"):
                    try:
                        db.criar_tarefa(titulo, u["nome"], data_limite, u["nome"], candidato_id)
                        avisar("Tarefa criada.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))
            try:
                listar_tarefas_interativas(db.listar_tarefas(candidato_id), f"{k}_t")
            except ErroBaseDados as exc:
                st.error(str(exc))

    # ----- Entrevistas e contratação -----
    with abas[4]:
        a, b = st.columns(2)
        with a:
            st.markdown("**Entrevistas**")
            if not gestor:
                with st.form(f"{k}_entrevista", clear_on_submit=True):
                    x, y = st.columns(2)
                    dia = x.date_input("Data", value=date.today() + timedelta(days=1), format="DD/MM/YYYY")
                    hora = y.time_input("Hora", value=datetime.strptime("10:00", "%H:%M").time())
                    x, y = st.columns(2)
                    tipo_e = x.selectbox("Tipo", ["Presencial", "Telefone", "Videochamada", "Avaliação técnica"])
                    entrevistador = y.text_input("Entrevistador", value=u["nome"])
                    notas_e = st.text_input("Notas")
                    if st.form_submit_button("Marcar entrevista"):
                        try:
                            db.criar_entrevista(candidato_id, datetime.combine(dia, hora), tipo_e,
                                                entrevistador, notas_e, u["nome"])
                            avisar("Entrevista marcada.")
                            st.rerun()
                        except ErroBaseDados as exc:
                            st.error(str(exc))
            try:
                entrevistas = db.listar_entrevistas(candidato_id)
            except ErroBaseDados as exc:
                entrevistas = []
                st.error(str(exc))
            opcoes_resultado = ["Por realizar", "Positivo", "Com reservas", "Negativo", "Não compareceu"]
            for e in entrevistas:
                with st.container(border=True):
                    st.markdown(f"**{formatar_data(e['data'])}** · {e['tipo']} · {html.escape(e['entrevistador'])}")
                    with st.form(f"{k}_e{e['id']}"):
                        res = st.selectbox("Resultado", opcoes_resultado,
                                           index=opcoes_resultado.index(e["resultado"])
                                           if e["resultado"] in opcoes_resultado else 0)
                        notas_r = st.text_area("Notas da entrevista", value=e["notas"], height=70)
                        if st.form_submit_button("Guardar resultado"):
                            try:
                                db.atualizar_entrevista(e["id"], res, notas_r)
                                avisar("Entrevista atualizada.")
                                st.rerun()
                            except ErroBaseDados as exc:
                                st.error(str(exc))
            if not entrevistas:
                st.caption("Sem entrevistas registadas.")
        with b:
            st.markdown("**Decisão e contratação**")
            if perfil in ("Administrador", "Gestor"):
                x, y = st.columns(2)
                if x.button("Aprovar candidato", icon=":material/check:", key=f"{k}_aprovar", **LARGURA,
                            disabled=c["estado"] in ("Aprovado", "Contratado")):
                    db.atualizar_candidato(candidato_id, {"estado": "Aprovado"}, u["nome"])
                    avisar("Candidato aprovado.")
                    st.rerun()
                if y.button("Rejeitar candidato", icon=":material/close:", key=f"{k}_rejeitar", **LARGURA,
                            disabled=c["estado"] in ("Rejeitado", "Contratado")):
                    db.atualizar_candidato(candidato_id, {"estado": "Rejeitado"}, u["nome"])
                    avisar("Candidato rejeitado.", "info")
                    st.rerun()
                with st.form(f"{k}_contratar"):
                    st.markdown("Registar contratação")
                    funcao = st.text_input("Função", value=c["cargo"])
                    x, y = st.columns(2)
                    contrato = x.selectbox("Tipo de contrato", TIPOS_CONTRATACAO[1:])
                    remuneracao = y.text_input("Remuneração acordada")
                    x, y = st.columns(2)
                    data_c = x.date_input("Data da contratação", value=date.today(), format="DD/MM/YYYY")
                    data_i = y.date_input("Data de início", value=None, format="DD/MM/YYYY")
                    obs = st.text_area("Observações", height=70)
                    if st.form_submit_button("Registar contratação", type="primary"):
                        try:
                            db.registar_contratacao(candidato_id, data_c, data_i, funcao, contrato,
                                                    remuneracao, obs, u["nome"])
                            avisar(f"Contratação de {c['nome']} registada.")
                            st.rerun()
                        except ErroBaseDados as exc:
                            st.error(str(exc))
            else:
                st.caption("A aprovação final e o registo da contratação são feitos pelo gestor "
                           "ou pelo administrador.")

    # ----- Dados e RGPD (apenas administrador) -----
    if perfil == "Administrador":
        with abas[5]:
            st.markdown(f"**Origem dos dados:** {html.escape(c['fonte'] or 'Não informado')} · "
                        f"recolhidos em {formatar_data(c['data_recolha'])}")
            try:
                historico = db.listar_historico(candidato_id)
            except ErroBaseDados as exc:
                historico = pd.DataFrame()
                st.error(str(exc))
            with st.expander("Histórico de alterações"):
                st.dataframe(_formatar_historico(historico), hide_index=True, **LARGURA)
            st.warning("As ações seguintes são definitivas.")
            confirmar = st.checkbox("Confirmo que pretendo remover os dados pessoais deste candidato",
                                    key=f"{k}_confirmar")
            a, b = st.columns(2)
            if a.button("Anonimizar candidato", key=f"{k}_anon", disabled=not confirmar, **LARGURA,
                        help="Remove nome, contactos, notas e ligações; mantém apenas dados estatísticos."):
                try:
                    db.anonimizar_candidato(candidato_id, u["nome"])
                    avisar("Candidato anonimizado.")
                    st.session_state.pop("candidato_aberto", None)
                    st.rerun()
                except ErroBaseDados as exc:
                    st.error(str(exc))
            if b.button("Eliminar definitivamente", key=f"{k}_elim", disabled=not confirmar, **LARGURA):
                try:
                    db.eliminar_candidato(candidato_id, u["nome"])
                    avisar("Candidato eliminado.")
                    st.session_state.pop("candidato_aberto", None)
                    st.rerun()
                except ErroBaseDados as exc:
                    st.error(str(exc))


def _formatar_historico(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={
        "data": "Data", "utilizador": "Utilizador", "candidato_id": "ID do candidato", "acao": "Ação",
        "campo": "Campo", "valor_anterior": "Valor anterior", "valor_novo": "Valor novo"})


def listar_tarefas_interativas(tarefas: list[dict], prefixo: str, mostrar_candidato: bool = False) -> None:
    """Lista de tarefas com caixa de verificação para concluir/reabrir."""
    if not tarefas:
        st.caption("Sem tarefas.")
        return
    for t in tarefas:
        atrasada = (not t["concluida"]) and t["data_limite"] and t["data_limite"] < date.today()
        rotulo = t["titulo"]
        if mostrar_candidato and t["candidato"]:
            rotulo += f" — {t['candidato']}"
        if t["data_limite"]:
            rotulo += f" · {formatar_data(t['data_limite'])}"
        if atrasada:
            rotulo = "Em atraso — " + rotulo
        marcada = st.checkbox(rotulo, value=t["concluida"], key=f"{prefixo}_{t['id']}")
        if marcada != t["concluida"]:
            try:
                db.marcar_tarefa(t["id"], marcada)
                st.rerun()
            except ErroBaseDados as exc:
                st.error(str(exc))


# ---------------------------------------------------------------------------
# Página: Candidatos
# ---------------------------------------------------------------------------

FILTROS_RAPIDOS = ["Com contacto direto", "Disponíveis", "Pontuação 70% ou mais", "F-Gas",
                   "Engenheiros", "Ainda não contactados"]
ORDENACOES = ["Melhor pontuação", "Mais recentes", "Disponibilidade", "Nome (A-Z)"]


def _texto_pesquisavel(linha: pd.Series) -> str:
    return normalizar_texto(" ".join([
        str(linha.get("nome") or ""), str(linha.get("cargo") or ""), str(linha.get("localizacao") or ""),
        str(linha.get("concelho") or ""), lista_para_texto(linha.get("especialidades")),
        lista_para_texto(linha.get("competencias")), lista_para_texto(linha.get("certificacoes")),
        str(linha.get("resumo") or ""),
    ]))


def _filtrar_candidatos(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Barra de pesquisa, filtros rápidos, ordenação e filtros avançados. Devolve (filtrado, vista)."""
    a, b, c = st.columns([3, 1.3, 1.1], vertical_alignment="bottom")
    termo = a.text_input("Pesquisar", placeholder="Nome, função, zona, competência… (ex.: VRV Sintra)",
                         icon=":material/search:", key="f_texto")
    ordem = b.selectbox("Ordenar por", ORDENACOES, key="f_ordem")
    vista = c.segmented_control("Vista", ["Grelha", "Tabela"], default="Grelha", key="f_vista") or "Grelha"
    rapidos = st.pills("Filtros rápidos", FILTROS_RAPIDOS, selection_mode="multi", key="f_rapidos",
                       label_visibility="collapsed") or []

    with st.expander("Mais filtros", icon=":material/tune:"):
        a, b, c, d = st.columns(4)
        especialidades = sorted({e for lista in df["especialidades"] for e in (lista or []) if e})
        f_esp = a.multiselect("Especialidade", especialidades, placeholder="Todas")
        locais = sorted({l for l in df["concelho"].where(df["concelho"].astype(bool), df["localizacao"]) if l})
        f_local = b.multiselect("Localização", locais, placeholder="Todas")
        f_estado = c.multiselect("Estado do processo", [e for e in ESTADOS if e in set(df["estado"])],
                                 placeholder="Todos")
        f_score = d.slider("Pontuação mínima", 0, 100, 0, step=5)
        a, b, c, d = st.columns(4)
        f_disp = a.multiselect("Disponibilidade", CLASSIF_DISPONIBILIDADE, placeholder="Qualquer")
        f_rec = b.multiselect("Recomendação", RECOMENDACOES, placeholder="Qualquer")
        f_fonte = c.multiselect("Fonte", sorted({f for f in df["fonte"] if f}), placeholder="Todas")
        f_carta = d.selectbox("Carta de condução", ["Qualquer", *TRI_ESTADO])
        a, b, c = st.columns([2, 1, 1])
        datas = [x for x in df["data_recolha"] if x is not None and not pd.isna(x)]
        f_datas = a.date_input("Data da pesquisa (intervalo)",
                               value=(min(datas), max(datas)) if datas else (), format="DD/MM/YYYY")
        f_ultima = bool(st.session_state.get("ids_ultima_pesquisa")) and b.checkbox("Apenas a última pesquisa")
        f_arquivados = c.checkbox("Mostrar arquivados")

    filtrado = df
    if not f_arquivados and "Arquivado" not in f_estado:
        filtrado = filtrado[filtrado["estado"] != "Arquivado"]
    if termo.strip():
        palavras = normalizar_texto(termo).split()
        textos = filtrado.apply(_texto_pesquisavel, axis=1)
        filtrado = filtrado[textos.apply(lambda tx: all(p in tx for p in palavras))]
    if "Com contacto direto" in rapidos:
        filtrado = filtrado[filtrado["telefone"].astype(bool) | filtrado["email"].astype(bool)]
    if "Disponíveis" in rapidos:
        filtrado = filtrado[filtrado["disponibilidade_classificacao"].isin(["Confirmada", "Provável"])]
    if "Pontuação 70% ou mais" in rapidos:
        filtrado = filtrado[filtrado["score"] >= 70]
    if "F-Gas" in rapidos:
        filtrado = filtrado[(filtrado["certificacao_fgas"] == "Sim") | filtrado["certificacoes"].apply(
            lambda l: any("gas" in str(x).lower() for x in (l or [])))]
    if "Engenheiros" in rapidos:
        filtrado = filtrado[filtrado.apply(lambda l: "engenheir" in normalizar_texto(
            f"{l['cargo']} {lista_para_texto(l['especialidades'])}"), axis=1)]
    if "Ainda não contactados" in rapidos:
        filtrado = filtrado[filtrado["data_primeiro_contacto"].isna()]
    if f_esp:
        filtrado = filtrado[filtrado["especialidades"].apply(lambda l: bool(set(l or []) & set(f_esp)))]
    if f_local:
        filtrado = filtrado[filtrado["concelho"].isin(f_local) | filtrado["localizacao"].isin(f_local)]
    if f_estado:
        filtrado = filtrado[filtrado["estado"].isin(f_estado)]
    if f_score:
        filtrado = filtrado[filtrado["score"] >= f_score]
    if f_disp:
        filtrado = filtrado[filtrado["disponibilidade_classificacao"].isin(f_disp)]
    if f_rec:
        filtrado = filtrado[filtrado["recomendacao"].isin(f_rec)]
    if f_fonte:
        filtrado = filtrado[filtrado["fonte"].isin(f_fonte)]
    if f_carta != "Qualquer":
        filtrado = filtrado[filtrado["carta_conducao"] == f_carta]
    if isinstance(f_datas, (tuple, list)) and len(f_datas) == 2:
        filtrado = filtrado[(filtrado["data_recolha"] >= f_datas[0]) & (filtrado["data_recolha"] <= f_datas[1])]
    if f_ultima:
        filtrado = filtrado[filtrado["id"].isin(st.session_state.get("ids_ultima_pesquisa", []))]

    if ordem == "Mais recentes":
        filtrado = filtrado.sort_values(["criado_em", "score"], ascending=[False, False])
    elif ordem == "Nome (A-Z)":
        filtrado = filtrado.sort_values("nome", key=lambda s: s.map(normalizar_texto))
    elif ordem == "Disponibilidade":
        peso = {"Confirmada": 0, "Provável": 1, "Desconhecida": 2, "Não disponível": 3}
        filtrado = filtrado.assign(_p=filtrado["disponibilidade_classificacao"].map(peso).fillna(2)) \
            .sort_values(["_p", "score"], ascending=[True, False]).drop(columns="_p")
    else:
        filtrado = filtrado.sort_values(["score", "nivel_confianca"], ascending=[False, False])
    return filtrado, vista


def _iniciais(nome: str) -> str:
    partes = [p for p in str(nome or "").split() if p[:1].isalpha()]
    if not partes or nome == "Não identificado":
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


def _cartao_candidato(c: pd.Series, prefixo: str, motivo: str = "") -> None:
    """Cartão com o resumo de um candidato, para a grelha."""
    esp = lista_para_texto((c["especialidades"] or [])[:2]) or c["cargo"] or "Especialidade não identificada"
    cargo = c["cargo"] if c["cargo"] and c["cargo"] not in esp else ""
    local = c["concelho"] or c["localizacao"] or "Zona não identificada"
    score = int(c["score"] or 0)
    contacto = " · ".join(n for n, v in (("Telefone", c["telefone"]), ("Email", c["email"])) if v)
    etiquetas = etiqueta(c["estado"], cor_estado(c["estado"]))
    disp = c["disponibilidade_classificacao"]
    etiquetas += etiqueta(f"Disponibilidade: {disp}",
                          "verde" if disp in ("Confirmada", "Provável") else "cinza")
    if c["certificacao_fgas"] == "Sim":
        etiquetas += etiqueta("F-Gas", "verde")
    etiquetas += etiqueta(contacto or "Contacto pelo perfil", "azul" if contacto else "cinza")
    linha_motivo = f'<div class="cc-motivo">{html.escape(motivo)}</div>' if motivo else ""
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="cc-topo">
              <div class="cc-avatar">{html.escape(_iniciais(c["nome"]))}</div>
              <div>
                <div class="cc-nome">{html.escape(str(c["nome"]))}</div>
                <div class="cc-cargo">{html.escape(esp)}{(" · " + html.escape(cargo)) if cargo else ""}</div>
              </div>
              <div class="cc-score"><b>{score}%</b><small>pontuação</small></div>
            </div>
            <div class="cc-barra"><div style="width:{score}%"></div></div>
            <div class="cc-info">Zona: <b>{html.escape(local)}</b> · {html.escape(c["recomendacao"])}</div>
            <div>{etiquetas}</div>
            <div class="cc-resumo">{html.escape(limpar_resumo(c["resumo"]))}</div>
            {linha_motivo}
            """,
            unsafe_allow_html=True,
        )
        url = url_segura(c["url_perfil"]) or url_segura(c["url_fonte"])
        colunas = st.columns(2) if url else [st.container()]
        if colunas[0].button("Detalhes", key=f"{prefixo}_ver_{c['id']}", icon=":material/visibility:",
                             type="primary", help="Ver ficha completa, contactar e acompanhar", **LARGURA):
            st.session_state["candidato_aberto"] = int(c["id"])
            st.rerun()
        if url:
            colunas[1].link_button("Perfil", url, icon=":material/open_in_new:",
                                   help="Abrir o perfil original do profissional", **LARGURA)


def _grelha_candidatos(df: pd.DataFrame, prefixo: str, motivos: pd.Series | None = None,
                       por_pagina: int = 12) -> None:
    """Grelha responsiva de cartões, com paginação."""
    total_paginas = max(1, -(-len(df) // por_pagina))
    pagina = 1
    if total_paginas > 1:
        pagina = st.session_state.get(f"{prefixo}_pagina", 1)
        pagina = min(max(1, pagina), total_paginas)
    inicio = (pagina - 1) * por_pagina
    bloco = df.iloc[inicio:inicio + por_pagina]
    motivos_bloco = motivos.iloc[inicio:inicio + por_pagina] if motivos is not None else None
    for linha in range(0, len(bloco), 3):
        colunas = st.columns(3, gap="medium")
        for k, coluna in enumerate(colunas):
            if linha + k < len(bloco):
                with coluna:
                    motivo = str(motivos_bloco.iloc[linha + k]) if motivos_bloco is not None else ""
                    _cartao_candidato(bloco.iloc[linha + k], prefixo, motivo)
    if total_paginas > 1:
        _, centro, _ = st.columns([2, 1.2, 2])
        centro.selectbox("Página", list(range(1, total_paginas + 1)), key=f"{prefixo}_pagina",
                         format_func=lambda p: f"Página {p} de {total_paginas}", label_visibility="collapsed")


def _tabela_candidatos(df: pd.DataFrame, chave: str, colunas_extra: dict | None = None):
    """Vista em tabela; ao selecionar uma linha abre o detalhe do candidato."""
    vista = pd.DataFrame({
        "Nome": df["nome"],
        "Especialidade": df.apply(
            lambda l: lista_para_texto((l["especialidades"] or [])[:2]) or l["cargo"], axis=1),
        "Localização": df["concelho"].where(df["concelho"].astype(bool), df["localizacao"]),
        "Pontuação": df["score"],
        "Disponibilidade": df["disponibilidade_classificacao"],
        "Estado": df["estado"],
        "Contacto": df.apply(
            lambda l: " + ".join([n for n, v in (("Telefone", l["telefone"]), ("Email", l["email"])) if v])
            or "Pelo perfil", axis=1),
        "Data de recolha": df["data_recolha"],
        "Perfil": df["url_perfil"].where(df["url_perfil"].astype(bool), df["url_fonte"]),
    })
    for titulo, serie in (colunas_extra or {}).items():
        vista.insert(1, titulo, serie.values)
    evento = st.dataframe(
        vista.reset_index(drop=True), hide_index=True, on_select="rerun", selection_mode="single-row",
        key=chave, **LARGURA,
        column_config={
            "Pontuação": st.column_config.ProgressColumn("Pontuação", min_value=0, max_value=100, format="%d%%"),
            "Data de recolha": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Perfil": st.column_config.LinkColumn("Perfil", display_text="Abrir"),
        },
    )
    linhas = evento.selection.rows if evento and evento.selection else []
    if linhas:
        st.session_state["candidato_aberto"] = int(df.iloc[linhas[0]]["id"])
        st.session_state["versao_tabela"] = st.session_state.get("versao_tabela", 0) + 1
        st.rerun()


def _botoes_exportacao(df: pd.DataFrame) -> None:
    a, b, c, _ = st.columns([1, 1, 1, 3])
    for coluna, rotulo, funcao, extensao, mime in (
        (a, "Exportar CSV", exportar_csv, "csv", "text/csv"),
        (b, "Exportar Excel", exportar_excel, "xlsx",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (c, "Exportar PDF", exportar_pdf, "pdf", "application/pdf"),
    ):
        try:
            coluna.download_button(rotulo, funcao(df), nome_ficheiro_exportacao(extensao), mime,
                                   key=f"exp_{extensao}", icon=":material/download:", **LARGURA)
        except ErroExportacao as exc:
            coluna.error(str(exc))


def _vista_detalhe() -> bool:
    """Se houver um candidato aberto, mostra o detalhe (em vez da lista) e devolve True."""
    aberto = st.session_state.get("candidato_aberto")
    if not aberto:
        return False
    if st.button("Voltar à lista", icon=":material/arrow_back:"):
        st.session_state.pop("candidato_aberto", None)
        st.rerun()
    mostrar_detalhe(aberto)
    return True


def pagina_candidatos(df: pd.DataFrame) -> None:
    u = utilizador_atual()
    cabecalho("Candidatos", "Pesquise, filtre, contacte e acompanhe cada profissional")
    if _vista_detalhe():
        return
    if u["perfil"] == "Gestor":
        df = df[df["estado"].isin(ESTADOS_GESTOR)]
        st.caption("Perfil de gestor: são apresentados os candidatos em fase de entrevista, "
                   "avaliação, aprovação e contratação.")
    if df.empty:
        st.info("Ainda não existem candidatos. Use «Procurar profissionais», na barra lateral, "
                "para encontrar os primeiros.")
        if u["perfil"] != "Gestor":
            _formulario_candidato_manual()
        return

    filtrado, vista = _filtrar_candidatos(df)
    com_contacto = int((filtrado["telefone"].astype(bool) | filtrado["email"].astype(bool)).sum())
    st.markdown(f"**{len(filtrado)} candidatos** · {com_contacto} com contacto direto")
    if filtrado.empty:
        st.warning("Nenhum candidato corresponde à pesquisa e aos filtros aplicados.")
    elif vista == "Tabela":
        _tabela_candidatos(filtrado, f"tabela_{st.session_state.get('versao_tabela', 0)}")
    else:
        _grelha_candidatos(filtrado, "lista")
    if not filtrado.empty:
        _botoes_exportacao(filtrado)
    if u["perfil"] != "Gestor":
        _formulario_candidato_manual()


def _formulario_candidato_manual() -> None:
    """Permite registar um candidato que chegou por outra via (telefone, referência…)."""
    u = utilizador_atual()
    with st.expander("Adicionar candidato manualmente", icon=":material/person_add:"):
        with st.form("candidato_manual", clear_on_submit=True):
            a, b = st.columns(2)
            nome = a.text_input("Nome completo")
            especialidades = b.multiselect("Especialidades", TODAS_ESPECIALIDADES)
            a, b, c = st.columns(3)
            localizacao = a.text_input("Localização")
            telefone = b.text_input("Telefone profissional")
            email = c.text_input("Email profissional")
            origem = st.text_input("Origem do contacto", placeholder="Ex.: Referência de um colega, candidatura espontânea")
            st.caption("Registe apenas dados profissionais fornecidos pelo próprio ou publicamente disponíveis.")
            if st.form_submit_button("Adicionar candidato"):
                if not nome.strip():
                    st.error("Indique o nome do candidato.")
                else:
                    try:
                        situacao, _ = db.guardar_candidato(CandidatoIA(
                            nome=nome, especialidades=especialidades,
                            cargo=especialidades[0] if especialidades else "",
                            localizacao=localizacao, concelho=localizacao,
                            contacto_telefone=telefone, contacto_email=email,
                            fonte=origem or "Registo manual", data_recolha=date.today().isoformat(),
                            nivel_confianca=100 if origem else 50,
                        ), None, u["nome"])
                        if situacao == "duplicado":
                            avisar("Candidato duplicado: já existe um registo com o mesmo email, "
                                   "telefone ou nome/localização/especialidade.", "warning")
                        else:
                            avisar("Candidato adicionado.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))


# ---------------------------------------------------------------------------
# Página: Pesquisa urgente
# ---------------------------------------------------------------------------

def pagina_urgente(df: pd.DataFrame) -> None:
    u = utilizador_atual()
    cabecalho("Serviço imediato", "Indique o serviço e veja quem pode começar já")
    if _vista_detalhe():
        return
    with st.form("urgente"):
        a, b, c = st.columns(3)
        especialidades = a.multiselect("Especialidade necessária", TODAS_ESPECIALIDADES,
                                       placeholder="Escolha a especialidade")
        local = b.selectbox("Localização do serviço", [l for l in LOCALIZACOES if l != "Outra localização"])
        outra = c.text_input("Outra localização (opcional)", placeholder="Ex.: Mafra")
        a, b, c, d = st.columns(4)
        inicio = a.date_input("Data de início", value=date.today(), format="DD/MM/YYYY")
        horario = b.text_input("Horário", placeholder="Ex.: 08h00–17h00")
        duracao = c.text_input("Duração prevista", placeholder="Ex.: 3 dias")
        raio = d.slider("Raio (km)", 5, 150, 40, step=5)
        a, b, c = st.columns(3)
        orcamento = a.text_input("Orçamento ou intervalo remuneratório", placeholder="Ex.: 90–120 €/dia")
        contratacao = b.selectbox("Tipo de contratação", TIPOS_CONTRATACAO, index=TIPOS_CONTRATACAO.index("Trabalho pontual"))
        maximo = c.slider("Candidatos a apresentar", 5, 30, 10)
        a, b, c = st.columns(3)
        deslocacao = a.checkbox("Exige disponibilidade para deslocação")
        viatura = b.checkbox("Exige viatura própria")
        fgas = c.checkbox("Exige certificação F-Gas")
        a, b = st.columns(2)
        ordenar = a.form_submit_button("Ver candidatos disponíveis", icon=":material/bolt:", type="primary", **LARGURA)
        procurar = b.form_submit_button("Procurar novos profissionais", icon=":material/search:", **LARGURA,
                                        disabled=u["perfil"] == "Gestor")

    local_servico = outra.strip() or local
    if ordenar or procurar:
        st.session_state["pedido_urgente"] = {
            "especialidades": especialidades, "local": local_servico, "raio": raio,
            "viatura": viatura, "fgas": fgas, "deslocacao": deslocacao, "maximo": maximo,
        }
    if procurar:
        disponibilidade = ["Disponibilidade imediata", "Assistência urgente"]
        if deslocacao:
            disponibilidade.append("Deslocações")
        st.session_state["pedido_pesquisa"] = {
            "especialidades": especialidades,
            "localizacoes": ["Outra localização"] if outra.strip() else [local],
            "outra_localizacao": outra.strip(), "raio_km": raio,
            "disponibilidade": disponibilidade, "tipo_contratacao": contratacao,
            "exige_fgas": fgas, "exige_viatura": viatura,
            "data_inicio": inicio.isoformat(), "horario": horario, "duracao_prevista": duracao,
            "orcamento": orcamento, "max_resultados": 20, "urgente": True,
        }
        st.rerun()

    pedido = st.session_state.get("pedido_urgente")
    if not pedido:
        st.info("Preencha a necessidade e escolha «Ver candidatos disponíveis» para uma resposta "
                "imediata, ou «Procurar novos profissionais» para alargar a pesquisa.")
        return

    ativos = df[~df["estado"].isin(["Arquivado", "Rejeitado", "Contratado"])]
    ordenado = ordenar_para_urgencia(ativos, pedido["especialidades"], pedido["local"], pedido["raio"],
                                     pedido["viatura"], pedido["fgas"], pedido["deslocacao"])
    ordenado = ordenado[ordenado["prioridade"] > 0].head(pedido["maximo"])
    if ordenado.empty:
        st.warning("Nenhum candidato na base de dados cumpre esta necessidade. "
                   "Use «Procurar novos profissionais».")
        return

    st.markdown(f"**{len(ordenado)} candidatos por ordem de prioridade** para {html.escape(pedido['local'])} "
                "— disponibilidade imediata, pontuação, proximidade, competências, contacto direto e experiência.")
    _grelha_candidatos(ordenado, "urgente", motivos=ordenado["motivos"])


# ---------------------------------------------------------------------------
# Página: Tarefas
# ---------------------------------------------------------------------------

def pagina_tarefas() -> None:
    u = utilizador_atual()
    cabecalho("Tarefas", "Lembretes e ações de acompanhamento")
    with st.form("nova_tarefa", clear_on_submit=True):
        a, b, c = st.columns([3, 1, 1], vertical_alignment="bottom")
        titulo = a.text_input("Nova tarefa", placeholder="Ex.: Ligar aos candidatos de Sintra")
        data_limite = b.date_input("Data limite", value=date.today(), format="DD/MM/YYYY")
        if c.form_submit_button("Criar tarefa", icon=":material/add:", type="primary", **LARGURA):
            try:
                db.criar_tarefa(titulo, u["nome"], data_limite, u["nome"])
                avisar("Tarefa criada.")
                st.rerun()
            except ErroBaseDados as exc:
                st.error(str(exc))
    try:
        tarefas = db.listar_tarefas()
    except ErroBaseDados as exc:
        st.error(str(exc))
        return
    apenas_minhas = st.checkbox("Mostrar apenas as minhas tarefas", value=u["perfil"] == "Recrutador")
    if apenas_minhas:
        tarefas = [t for t in tarefas if t["responsavel"] == u["nome"]]
    pendentes = [t for t in tarefas if not t["concluida"]]
    concluidas = [t for t in tarefas if t["concluida"]]
    a, b = st.columns(2, gap="medium")
    with a, st.container(border=True):
        st.markdown(f"**Pendentes ({len(pendentes)})**")
        listar_tarefas_interativas(pendentes, "tp", mostrar_candidato=True)
    with b, st.container(border=True):
        st.markdown(f"**Concluídas ({len(concluidas)})**")
        listar_tarefas_interativas(concluidas[:30], "tc", mostrar_candidato=True)


# ---------------------------------------------------------------------------
# Página: Contratações (gestor e administrador)
# ---------------------------------------------------------------------------

def pagina_contratacoes(df: pd.DataFrame) -> None:
    cabecalho("Contratações", "Candidatos em decisão, entrevistas e contratações concluídas")
    if _vista_detalhe():
        return
    abas = st.tabs(["Em processo de contratação", "Entrevistas", "Contratações concluídas"])
    with abas[0]:
        em_processo = df[df["estado"].isin(["Entrevista marcada", "Em avaliação técnica", "Aprovado", "Em negociação"])]
        if em_processo.empty:
            st.info("Não existem candidatos em fase de decisão.")
        else:
            st.caption("Abra um candidato para consultar notas, aprovar, rejeitar ou registar a contratação.")
            _grelha_candidatos(em_processo, "decisao")
    with abas[1]:
        try:
            entrevistas = pd.DataFrame(db.listar_entrevistas())
        except ErroBaseDados as exc:
            entrevistas = pd.DataFrame()
            st.error(str(exc))
        if entrevistas.empty:
            st.info("Sem entrevistas registadas.")
        else:
            st.dataframe(
                entrevistas[["data", "candidato", "tipo", "entrevistador", "resultado", "notas"]].rename(columns={
                    "data": "Data", "candidato": "Candidato", "tipo": "Tipo",
                    "entrevistador": "Entrevistador", "resultado": "Resultado", "notas": "Notas"}),
                hide_index=True, **LARGURA,
                column_config={"Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})
    with abas[2]:
        try:
            contratacoes = db.listar_contratacoes_df()
        except ErroBaseDados as exc:
            contratacoes = pd.DataFrame()
            st.error(str(exc))
        if contratacoes.empty:
            st.info("Ainda não foi registada nenhuma contratação.")
        else:
            st.dataframe(contratacoes.rename(columns={
                "candidato": "Candidato", "funcao": "Função", "tipo_contrato": "Tipo de contrato",
                "data_contratacao": "Data da contratação", "data_inicio": "Data de início",
                "remuneracao": "Remuneração", "aprovado_por": "Aprovado por", "observacoes": "Observações"}),
                hide_index=True, **LARGURA, column_config={
                    "Data da contratação": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Data de início": st.column_config.DateColumn(format="DD/MM/YYYY")})


# ---------------------------------------------------------------------------
# Página: Administração
# ---------------------------------------------------------------------------

NOTA_RGPD = """
**Nota interna sobre proteção de dados (RGPD)**

- **Finalidade:** os dados são tratados exclusivamente para recrutamento e contratação de técnicos.
- **Minimização:** guardam-se apenas dados profissionais (nome, especialidade, zona, experiência,
  certificações e contactos profissionais publicados pelo próprio). Não registe dados sensíveis.
- **Transparência:** cada registo guarda a fonte e a data de recolha. No primeiro contacto, informe o
  candidato de onde obteve os dados e para que fim (artigo 14.º do RGPD) e respeite um pedido de oposição.
- **Conservação limitada:** reveja periodicamente os candidatos antigos e anonimize ou elimine os que
  já não são necessários (ferramenta abaixo).
- **Direitos dos titulares:** os pedidos de acesso, retificação ou apagamento devem ser satisfeitos;
  use «Corrigir dados do perfil», «Anonimizar» ou «Eliminar» no detalhe do candidato.
- **Contactos:** a aplicação prepara as mensagens, mas o envio é sempre uma decisão individual do
  utilizador. Não são feitos envios automáticos nem em massa.
- **Segurança:** o acesso exige autenticação, as palavras-passe são guardadas com hash e as chaves API
  nunca são gravadas na base de dados.

Esta nota não substitui aconselhamento jurídico. Confirme a base de licitude do tratamento com o
responsável pela proteção de dados da empresa.
"""


def pagina_administracao() -> None:
    u = utilizador_atual()
    cabecalho("Administração", "Utilizadores, pesquisas, auditoria e proteção de dados")
    abas = st.tabs(["Utilizadores", "Estatísticas", "Pesquisas realizadas", "Fontes consultadas",
                    "Histórico de alterações", "RGPD"])

    with abas[0]:
        try:
            utilizadores = db.listar_utilizadores()
        except ErroBaseDados as exc:
            utilizadores = []
            st.error(str(exc))
        for x in utilizadores:
            with st.container(border=True):
                a, b, c, d = st.columns([3, 2, 1, 1])
                a.markdown(f"**{html.escape(x['nome'])}**  \n{html.escape(x['email'])}")
                perfil = b.selectbox("Perfil", PERFIS_UTILIZADOR, index=PERFIS_UTILIZADOR.index(x["perfil"]),
                                     key=f"u_perfil_{x['id']}", label_visibility="collapsed")
                ativo = c.checkbox("Ativo", value=x["ativo"], key=f"u_ativo_{x['id']}")
                if d.button("Guardar", key=f"u_guardar_{x['id']}", **LARGURA):
                    try:
                        db.atualizar_utilizador(x["id"], perfil, ativo)
                        avisar("Utilizador atualizado.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))
        with st.form("novo_utilizador", clear_on_submit=True):
            st.markdown("**Novo utilizador**")
            a, b = st.columns(2)
            nome = a.text_input("Nome")
            email = b.text_input("Email")
            a, b, c = st.columns([1, 1, 0.7], vertical_alignment="bottom")
            perfil = a.selectbox("Perfil", PERFIS_UTILIZADOR, index=1)
            password = b.text_input("Palavra-passe inicial", type="password",
                                    help="Mínimo de 8 caracteres, com letras e números.")
            if c.form_submit_button("Criar utilizador", icon=":material/person_add:", type="primary", **LARGURA):
                erro = validar_password(password)
                if erro:
                    st.error(erro)
                else:
                    try:
                        db.criar_utilizador(nome, email, password, perfil)
                        avisar("Utilizador criado.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))
        with st.form("alterar_password", clear_on_submit=True):
            st.markdown("**Alterar palavra-passe**")
            a, b, c = st.columns([1, 1, 0.7], vertical_alignment="bottom")
            alvo = a.selectbox("Utilizador", utilizadores, format_func=lambda x: f"{x['nome']} ({x['email']})")
            nova = b.text_input("Nova palavra-passe", type="password",
                                help="Mínimo de 8 caracteres, com letras e números.")
            if c.form_submit_button("Alterar palavra-passe", icon=":material/key:", **LARGURA):
                erro = validar_password(nova)
                if erro:
                    st.error(erro)
                elif alvo:
                    try:
                        db.alterar_password(alvo["id"], nova)
                        avisar("Palavra-passe alterada.")
                        st.rerun()
                    except ErroBaseDados as exc:
                        st.error(str(exc))

    with abas[1]:
        _estatisticas(db.listar_candidatos_df())

    with abas[2]:
        try:
            pesquisas = db.listar_pesquisas_df()
            if pesquisas.empty:
                st.info("Ainda não foram realizadas pesquisas.")
            else:
                pesquisas["Critérios"] = pesquisas["parametros"].apply(
                    lambda p: f"{lista_para_texto((p or {}).get('especialidades')) or 'Geral'} · "
                              f"{lista_para_texto((p or {}).get('localizacoes'))}")
                st.dataframe(pesquisas.drop(columns=["parametros"]).rename(columns={
                    "id": "N.º", "data": "Data", "utilizador": "Utilizador",                     "total_resultados": "Resultados", "total_candidatos": "Candidatos",
                    "novos": "Novos", "duplicados": "Duplicados"}),
                    hide_index=True, **LARGURA,
                    column_config={"Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})
        except ErroBaseDados as exc:
            st.error(str(exc))

    with abas[3]:
        try:
            fontes = db.listar_fontes_df()
            if fontes.empty:
                st.info("Ainda não foram consultadas fontes.")
            else:
                st.dataframe(fontes.rename(columns={
                    "data": "Data", "pesquisa_id": "Pesquisa", "dominio": "Domínio",
                    "tipo_resultado": "Classificação da IA", "titulo": "Título", "url": "Endereço"}),
                    hide_index=True, **LARGURA, column_config={
                        "Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                        "Endereço": st.column_config.LinkColumn(display_text="Abrir")})
        except ErroBaseDados as exc:
            st.error(str(exc))

    with abas[4]:
        try:
            st.dataframe(_formatar_historico(db.listar_historico()), hide_index=True, **LARGURA,
                         column_config={"Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})
        except ErroBaseDados as exc:
            st.error(str(exc))

    with abas[5]:
        st.markdown(NOTA_RGPD)
        st.divider()
        st.markdown("**Conservação limitada — revisão de candidatos antigos**")
        meses = st.slider("Candidatos recolhidos há mais de (meses)", 3, 36, 12)
        try:
            antigos = db.candidatos_para_revisao(meses)
        except ErroBaseDados as exc:
            antigos = pd.DataFrame()
            st.error(str(exc))
        if antigos.empty:
            st.success("Não existem candidatos não contratados com dados mais antigos do que este prazo.")
        else:
            st.dataframe(antigos.rename(columns={"id": "ID", "nome": "Nome", "estado": "Estado",
                                                 "data_recolha": "Data de recolha"}),
                         hide_index=True, **LARGURA,
                         column_config={"Data de recolha": st.column_config.DateColumn(format="DD/MM/YYYY")})
            confirmar = st.checkbox(f"Confirmo a anonimização definitiva destes {len(antigos)} candidatos")
            if st.button("Anonimizar candidatos listados", disabled=not confirmar):
                try:
                    for candidato_id in antigos["id"]:
                        db.anonimizar_candidato(int(candidato_id), u["nome"])
                    avisar(f"{len(antigos)} candidatos anonimizados.")
                    st.rerun()
                except ErroBaseDados as exc:
                    st.error(str(exc))


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    aplicar_css()
    try:
        db.inicializar_bd()
    except ErroBaseDados as exc:
        st.error(f"Erro na base de dados: {exc}")
        st.stop()

    if "utilizador" not in st.session_state:
        ecra_autenticacao()
        return

    pagina = barra_lateral()
    mostrar_avisos()

    pedido = st.session_state.pop("pedido_pesquisa", None)
    if pedido:
        executar_prospecao(pedido)

    try:
        df = db.listar_candidatos_df()
    except ErroBaseDados as exc:
        st.error(f"Erro na base de dados: {exc}")
        st.stop()

    try:
        if pagina == "Painel":
            pagina_painel(df)
        elif pagina == "Candidatos":
            pagina_candidatos(df)
        elif pagina == "Serviço imediato":
            pagina_urgente(df)
        elif pagina == "Tarefas":
            pagina_tarefas()
        elif pagina == "Contratações":
            pagina_contratacoes(df)
        elif pagina == "Administração":
            pagina_administracao()
    except ErroBaseDados as exc:
        st.error(f"Erro na base de dados: {exc}")


main()
