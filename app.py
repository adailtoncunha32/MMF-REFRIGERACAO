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
    for _nome in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "DATABASE_URL", "ANTHROPIC_MODEL"):
        if _nome in st.secrets and not os.getenv(_nome):
            os.environ[_nome] = str(st.secrets[_nome])
except Exception:  # sem ficheiro de segredos (execução local): usa-se apenas o .env
    pass

import database as db  # noqa: E402
from ai_analyzer import ErroIA, analisar_resultados  # noqa: E402
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
    URGENCIAS,
    CandidatoIA,
)
from search_engine import ErroPesquisa, executar_pesquisa, gerar_consultas  # noqa: E402
from utils import (  # noqa: E402
    formatar_data,
    link_mailto,
    link_telefone,
    link_whatsapp,
    lista_para_texto,
    nome_ficheiro_exportacao,
    normalizar_texto,
    obter_variavel,
    ordenar_para_urgencia,
    url_segura,
    validar_password,
)

st.set_page_config(page_title=NOME_APP, page_icon="❄️", layout="wide", initial_sidebar_state="expanded")

# Compatibilidade entre versões do Streamlit para "ocupar toda a largura".
_VERSAO = tuple(int(p) for p in st.__version__.split(".")[:2])
LARGURA = {"width": "stretch"} if _VERSAO >= (1, 50) else {"use_container_width": True}

AZUL_ESCURO, CIANO, VERDE, VERMELHO, CINZA = "#0B2545", "#13A8C9", "#1E9E6A", "#D64545", "#F3F6FA"
PALETA = [CIANO, AZUL_ESCURO, VERDE, "#5B7DB1", "#8ED1E0", "#F2A541", "#7A8CA3", VERMELHO]

PAGINAS_POR_PERFIL = {
    "Administrador": ["Dashboard", "Candidatos", "Pesquisa urgente", "Tarefas", "Contratações", "Administração"],
    "Recrutador": ["Dashboard", "Candidatos", "Pesquisa urgente", "Tarefas"],
    "Gestor": ["Dashboard", "Candidatos", "Contratações", "Tarefas"],
}
ICONES_PAGINA = {
    "Dashboard": "📊", "Candidatos": "👷", "Pesquisa urgente": "🚨",
    "Tarefas": "✅", "Contratações": "🤝", "Administração": "⚙️",
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
        section[data-testid="stSidebar"] button[kind="secondary"] p {{ color: {AZUL_ESCURO} !important; }}
        .logo-app {{ display:flex; align-items:center; gap:.6rem; margin-bottom:.4rem; }}
        .logo-app .icone {{ font-size: 2rem; background:{CIANO}; border-radius:12px;
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
    """Chave introduzida na sessão (não é guardada em disco) ou, em alternativa, a do .env."""
    return (st.session_state.get(f"chave_{nome}") or "").strip() or obter_variavel(nome)


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def ecra_autenticacao() -> None:
    """Primeiro acesso: cria o administrador. Acessos seguintes: início de sessão."""
    cabecalho(f"❄️ {NOME_APP}", "Plataforma interna de recrutamento de técnicos de AVAC e refrigeração")
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        try:
            primeiro_acesso = db.contar_utilizadores() == 0
        except ErroBaseDados as exc:
            st.error(str(exc))
            st.stop()

        if primeiro_acesso:
            st.info("Primeiro acesso: crie a conta de administrador da aplicação.")
            with st.form("criar_admin"):
                nome = st.text_input("Nome")
                email = st.text_input("Email")
                password = st.text_input("Palavra-passe", type="password",
                                         help="Mínimo de 8 caracteres, com letras e números.")
                confirmar = st.text_input("Confirmar palavra-passe", type="password")
                if st.form_submit_button("Criar conta de administrador", type="primary", **LARGURA):
                    erro = validar_password(password)
                    if password != confirmar:
                        st.error("As palavras-passe não coincidem.")
                    elif erro:
                        st.error(erro)
                    else:
                        try:
                            st.session_state["utilizador"] = db.criar_utilizador(
                                nome, email, password, "Administrador")
                            st.rerun()
                        except ErroBaseDados as exc:
                            st.error(str(exc))
        else:
            with st.form("iniciar_sessao"):
                st.subheader("Iniciar sessão")
                email = st.text_input("Email")
                password = st.text_input("Palavra-passe", type="password")
                if st.form_submit_button("Entrar", type="primary", **LARGURA):
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
        st.caption("🔒 Acesso reservado a colaboradores autorizados. Os dados tratados nesta "
                   "aplicação estão sujeitos ao RGPD.")


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

_OMISSOES_PESQUISA = {
    "f_especialidades": [], "f_localizacoes": ["Grande Lisboa"], "f_outra": "", "f_raio": 30,
    "f_disponibilidade": [], "f_tipo": TIPOS_CONTRATACAO[0], "f_urgencia": URGENCIAS[0],
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
        st.caption(f"👤 {u['nome']} · {u['perfil']}")
        pagina = st.radio(
            "Navegação", PAGINAS_POR_PERFIL[u["perfil"]],
            format_func=lambda p: f"{ICONES_PAGINA[p]}  {p}", key="pagina", label_visibility="collapsed",
        )
        st.divider()

        if pode_pesquisar:
            st.subheader("🔎 Prospeção")
            st.button("➕ Nova pesquisa", on_click=_nova_pesquisa, **LARGURA,
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
            st.select_slider("Urgência", URGENCIAS, key="f_urgencia")
            st.checkbox("Exigir certificação F-Gas", key="f_fgas")
            st.slider("Número máximo de resultados", 5, 50, key="f_max", step=5,
                      help="Resultados de pesquisa analisados pela IA. Mais resultados = mais tempo e custo.")

            # Com as chaves configuradas no servidor, os utilizadores não precisam de as ver.
            nomes_chaves = ("ANTHROPIC_API_KEY", "TAVILY_API_KEY")
            if not all(obter_variavel(n) for n in nomes_chaves):
                with st.expander("🔑 Chaves API", expanded=True):
                    for nome in nomes_chaves:
                        if obter_variavel(nome):
                            continue
                        st.text_input(nome, type="password", key=f"chave_{nome}", autocomplete="off",
                                      placeholder="Cole aqui a chave")
                        st.caption("✅ Chave disponível" if chave_api(nome) else "⚠️ Chave em falta")
                    st.caption("As chaves ficam apenas na memória desta sessão; nunca são mostradas "
                               "nem guardadas na base de dados.")

            if st.button("🚀 Iniciar prospeção com IA", type="primary", **LARGURA):
                st.session_state["pedido_pesquisa"] = {
                    "especialidades": st.session_state["f_especialidades"],
                    "localizacoes": st.session_state["f_localizacoes"],
                    "outra_localizacao": st.session_state.get("f_outra", ""),
                    "raio_km": st.session_state["f_raio"],
                    "disponibilidade": st.session_state["f_disponibilidade"],
                    "tipo_contratacao": st.session_state["f_tipo"],
                    "urgencia": st.session_state["f_urgencia"],
                    "exige_fgas": st.session_state["f_fgas"],
                    "max_resultados": st.session_state["f_max"],
                    "urgente": st.session_state["f_urgencia"] != "Normal",
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
    em_falta = [n for n in ("TAVILY_API_KEY", "ANTHROPIC_API_KEY") if not chave_api(n)]
    if em_falta:
        st.error("Chave API em falta: " + " e ".join(em_falta) +
                 ". Introduza-a em «🔑 Chaves API», na barra lateral, ou no ficheiro .env.")
        return

    limite_consultas = {"Normal": 6, "Urgente": 8, "Muito urgente": 10}.get(parametros.get("urgencia"), 6)
    consultas = gerar_consultas(parametros, limite_consultas)
    criterios = {k: v for k, v in parametros.items() if k not in ("max_resultados", "urgente")}

    try:
        pesquisa_id = db.registar_pesquisa(u["nome"], parametros, consultas, bool(parametros.get("urgente")))
    except ErroBaseDados as exc:
        st.error(str(exc))
        return

    with st.status("A procurar profissionais…", expanded=True) as estado:
        # 1) Pesquisa em fontes públicas
        st.write(f"🔎 {len(consultas)} consultas geradas a partir dos critérios.")
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
        st.write(f"📄 {len(resultados)} resultados únicos encontrados.")

        # 2) Análise pela IA
        barra_ia = st.progress(0.0, text="A analisar perfis com IA…")
        try:
            candidatos, descartados, avisos_ia = analisar_resultados(
                chave_api("ANTHROPIC_API_KEY"), resultados, criterios,
                progresso=lambda feito, total: barra_ia.progress(
                    feito / total, text=f"A analisar perfis com IA… {feito}/{total} lotes"),
            )
        except ErroIA as exc:
            estado.update(label="A análise por IA falhou", state="error")
            st.error(f"Erro da Anthropic: {exc}")
            return
        except Exception:
            estado.update(label="A análise por IA falhou", state="error")
            st.error("Ocorreu um erro inesperado durante a análise por IA. Tente novamente.")
            return
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
    st.success(f"✅ {novos} novos candidatos guardados · {duplicados} já existiam (duplicados ignorados) · "
               f"{len(descartados)} resultados descartados. Consulte-os na página «Candidatos».")


# ---------------------------------------------------------------------------
# Página: Dashboard
# ---------------------------------------------------------------------------

def _grafico(fig, legenda: bool = False) -> None:
    fig.update_layout(margin=dict(l=10, r=10, t=45, b=10), paper_bgcolor="#FFFFFF",
                      plot_bgcolor="#FFFFFF", font=dict(color=AZUL_ESCURO), title_font_size=16,
                      showlegend=legenda, height=340)
    st.plotly_chart(fig, **LARGURA)


def pagina_dashboard(df: pd.DataFrame) -> None:
    cabecalho("📊 Dashboard", "Visão geral da prospeção e do processo de recrutamento")
    if df.empty:
        st.info("Ainda não existem candidatos. Use «🚀 Iniciar prospeção com IA», na barra lateral, "
                "para encontrar os primeiros profissionais.")
        return

    ativos = df[df["estado"] != "Arquivado"]
    contactados = df["data_primeiro_contacto"].notna().sum()
    m = st.columns(4)
    m[0].metric("Candidatos encontrados", len(df))
    m[1].metric("Aprovados pela IA", int(df["recomendacao"].isin(RECOMENDACOES[:2]).sum()),
                help="Recomendação «Contactar» ou «Contactar imediatamente».")
    m[2].metric("Score superior a 80%", int((df["score"] > 80).sum()))
    m[3].metric("Disponíveis imediatamente", int(
        ((df["disponibilidade_imediata"] == "Sim") | (df["disponibilidade_classificacao"] == "Confirmada")).sum()))
    m = st.columns(4)
    m[0].metric("Contactados", int(contactados))
    m[1].metric("Entrevistas marcadas", int((df["estado"] == "Entrevista marcada").sum()))
    m[2].metric("Contratados", int((df["estado"] == "Contratado").sum()))
    m[3].metric("Score médio", f"{df['score'].mean():.0f}%")
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        esp = ativos["especialidades"].explode().dropna()
        esp = esp[esp.astype(str).str.strip() != ""]
        if not esp.empty:
            contagem = esp.value_counts().head(12).sort_values().reset_index()
            contagem.columns = ["Especialidade", "Candidatos"]
            _grafico(px.bar(contagem, x="Candidatos", y="Especialidade", orientation="h",
                            title="Candidatos por especialidade", color_discrete_sequence=[CIANO]))
    with c2:
        local = ativos["concelho"].where(ativos["concelho"].astype(bool), ativos["localizacao"])
        local = local.replace("", "Não identificada").fillna("Não identificada")
        contagem = local.value_counts().head(12).reset_index()
        contagem.columns = ["Localização", "Candidatos"]
        _grafico(px.bar(contagem, x="Localização", y="Candidatos", title="Candidatos por localização",
                        color_discrete_sequence=[AZUL_ESCURO]))

    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(df, x="score", nbins=10, title="Distribuição dos scores",
                           labels={"score": "Score (%)"}, color_discrete_sequence=[CIANO])
        fig.update_layout(yaxis_title="Candidatos", bargap=0.08)
        _grafico(fig)
    with c2:
        contagem = df["estado"].value_counts().reindex(ESTADOS).dropna().reset_index()
        contagem.columns = ["Estado", "Candidatos"]
        _grafico(px.bar(contagem, x="Estado", y="Candidatos", title="Candidatos por estado",
                        color="Estado", color_discrete_sequence=PALETA))

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
    etiquetas = etiqueta(c["estado"], cor_estado(c["estado"])) + etiqueta(f"Score {c['score']}%", "escura")
    etiquetas += etiqueta(c["recomendacao"], "verde" if c["recomendacao"] in RECOMENDACOES[:2] else "cinza")
    etiquetas += etiqueta(f"Disponibilidade: {c['disponibilidade_classificacao']}",
                          "verde" if c["disponibilidade_classificacao"] in ("Confirmada", "Provável") else "cinza")
    if c["certificacao_fgas"] == "Sim":
        etiquetas += etiqueta("F-Gas", "verde")
    st.markdown(
        f'<div class="cartao"><h3>{html.escape(c["nome"])}</h3>'
        f'<div class="linha">🔧 {html.escape(esp)}</div>'
        f'<div class="linha">📍 {html.escape(local)}</div>{etiquetas}</div>',
        unsafe_allow_html=True,
    )

    nomes_abas = ["👤 Perfil", "📞 Contacto", "🗂️ Processo", "📝 Notas e tarefas", "🤝 Entrevistas e contratação"]
    if perfil == "Administrador":
        nomes_abas.append("🛡️ Dados e RGPD")
    abas = st.tabs(nomes_abas)

    # ----- Perfil -----
    with abas[0]:
        with st.expander("Resumo profissional", expanded=True):
            st.write(c["resumo"] or "Não informado")
        with st.expander("Score e justificação", expanded=True):
            a, b = st.columns(2)
            a.progress(c["score"] / 100, text=f"Score de adequação: {c['score']}%")
            b.progress(c["nivel_confianca"] / 100, text=f"Confiança na informação: {c['nivel_confianca']}%")
            st.write(c["justificacao_score"] or "Não informado")
        with st.expander("Experiência"):
            anos = c["anos_experiencia"]
            st.markdown(f"**Anos de experiência:** {anos if anos is not None else 'Não identificado'}")
            experiencias = c["experiencias"] or {}
            colunas = st.columns(3)
            for indice, (chave, rotulo) in enumerate(AREAS_EXPERIENCIA.items()):
                valor = experiencias.get(chave, "Não identificado")
                simbolo = {"Sim": "✅", "Não": "❌"}.get(valor, "❔")
                colunas[indice % 3].markdown(f"{simbolo} {rotulo}")
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
            ("🔗 Perfil original", url_segura(c["url_perfil"]) or url_segura(c["url_fonte"])),
            ("✉️ Email", link_mailto(c["email"], "Oportunidade profissional", "")),
            ("💬 WhatsApp", link_whatsapp(c["telefone"], "")),
            ("📞 Telefonar", link_telefone(c["telefone"])),
        ]
        colunas = st.columns(4)
        for coluna, (rotulo, destino) in zip(colunas, ligacoes):
            if destino:
                coluna.link_button(rotulo, destino, **LARGURA)
            else:
                coluna.button(rotulo, disabled=True, key=f"{k}_{rotulo}", **LARGURA)

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
                if x.button("✅ Aprovar candidato", key=f"{k}_aprovar", **LARGURA,
                            disabled=c["estado"] in ("Aprovado", "Contratado")):
                    db.atualizar_candidato(candidato_id, {"estado": "Aprovado"}, u["nome"])
                    avisar("Candidato aprovado.")
                    st.rerun()
                if y.button("❌ Rejeitar candidato", key=f"{k}_rejeitar", **LARGURA,
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
                            avisar(f"Contratação de {c['nome']} registada. 🎉")
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
            rotulo = "🔴 " + rotulo
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

def _filtrar_candidatos(df: pd.DataFrame) -> pd.DataFrame:
    """Painel de filtros da lista de candidatos."""
    with st.expander("🔍 Filtros", expanded=True):
        a, b, c, d = st.columns(4)
        especialidades = sorted({e for lista in df["especialidades"] for e in (lista or []) if e})
        f_esp = a.multiselect("Especialidade", especialidades, placeholder="Todas")
        locais = sorted({l for l in df["concelho"].where(df["concelho"].astype(bool), df["localizacao"]) if l})
        f_local = b.multiselect("Localização", locais, placeholder="Todas")
        f_estado = c.multiselect("Estado do processo", [e for e in ESTADOS if e in set(df["estado"])],
                                 placeholder="Todos")
        f_score = d.slider("Score mínimo", 0, 100, 0, step=5)
        a, b, c, d = st.columns(4)
        f_disp = a.multiselect("Disponibilidade", CLASSIF_DISPONIBILIDADE, placeholder="Qualquer")
        f_fonte = b.multiselect("Fonte", sorted({f for f in df["fonte"] if f}), placeholder="Todas")
        f_fgas = c.selectbox("Certificação F-Gas", ["Qualquer", *TRI_ESTADO])
        f_carta = d.selectbox("Carta de condução", ["Qualquer", *TRI_ESTADO])
        a, b, c = st.columns([2, 1, 1])
        datas = [x for x in df["data_recolha"] if x is not None and not pd.isna(x)]
        f_datas = a.date_input("Data da pesquisa (intervalo)",
                               value=(min(datas), max(datas)) if datas else (),
                               format="DD/MM/YYYY")
        f_ultima = b.checkbox("Apenas a última pesquisa",
                              disabled=not st.session_state.get("ids_ultima_pesquisa"))
        f_arquivados = c.checkbox("Mostrar arquivados")

    filtrado = df
    if not f_arquivados and "Arquivado" not in f_estado:
        filtrado = filtrado[filtrado["estado"] != "Arquivado"]
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
    if f_fonte:
        filtrado = filtrado[filtrado["fonte"].isin(f_fonte)]
    if f_fgas != "Qualquer":
        filtrado = filtrado[filtrado["certificacao_fgas"] == f_fgas]
    if f_carta != "Qualquer":
        filtrado = filtrado[filtrado["carta_conducao"] == f_carta]
    if isinstance(f_datas, (tuple, list)) and len(f_datas) == 2:
        filtrado = filtrado[(filtrado["data_recolha"] >= f_datas[0]) & (filtrado["data_recolha"] <= f_datas[1])]
    if f_ultima:
        filtrado = filtrado[filtrado["id"].isin(st.session_state.get("ids_ultima_pesquisa", []))]
    return filtrado


def _tabela_candidatos(df: pd.DataFrame, chave: str, colunas_extra: dict | None = None):
    """Tabela interativa; devolve o id do candidato selecionado (ou None)."""
    vista = pd.DataFrame({
        "Nome": df["nome"],
        "Especialidade": df.apply(
            lambda l: lista_para_texto((l["especialidades"] or [])[:2]) or l["cargo"], axis=1),
        "Localização": df["localizacao"].where(df["localizacao"].astype(bool), df["concelho"]),
        "Score": df["score"],
        "Disponibilidade": df["disponibilidade_classificacao"],
        "Certificações": df.apply(
            lambda l: lista_para_texto((["F-Gas"] if l["certificacao_fgas"] == "Sim" else [])
                                       + [x for x in (l["certificacoes"] or []) if "gas" not in x.lower()][:2]),
            axis=1),
        "Estado": df["estado"],
        "Data de recolha": df["data_recolha"],
        "Contacto": df.apply(
            lambda l: " + ".join([n for n, v in (("Telefone", l["telefone"]), ("Email", l["email"])) if v]) or "—",
            axis=1),
        "Perfil": df["url_perfil"].where(df["url_perfil"].astype(bool), df["url_fonte"]),
    })
    for titulo, serie in (colunas_extra or {}).items():
        vista.insert(1, titulo, serie.values)
    evento = st.dataframe(
        vista.reset_index(drop=True), hide_index=True, on_select="rerun", selection_mode="single-row",
        key=chave, **LARGURA,
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d%%"),
            "Data de recolha": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Perfil": st.column_config.LinkColumn("Perfil", display_text="Abrir"),
        },
    )
    linhas = evento.selection.rows if evento and evento.selection else []
    return int(df.iloc[linhas[0]]["id"]) if linhas else None


def _botoes_exportacao(df: pd.DataFrame) -> None:
    a, b, c, _ = st.columns([1, 1, 1, 3])
    for coluna, rotulo, funcao, extensao, mime in (
        (a, "⬇️ CSV", exportar_csv, "csv", "text/csv"),
        (b, "⬇️ Excel", exportar_excel, "xlsx",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (c, "⬇️ PDF", exportar_pdf, "pdf", "application/pdf"),
    ):
        try:
            coluna.download_button(rotulo, funcao(df), nome_ficheiro_exportacao(extensao), mime,
                                   key=f"exp_{extensao}", **LARGURA)
        except ErroExportacao as exc:
            coluna.error(str(exc))


def _abrir_detalhe_selecionado(selecionado) -> None:
    """Mantém aberto o detalhe do candidato escolhido na tabela."""
    if selecionado:
        st.session_state["candidato_aberto"] = selecionado
    aberto = st.session_state.get("candidato_aberto")
    if aberto:
        st.divider()
        a, b = st.columns([5, 1])
        a.subheader("Detalhes do candidato")
        if b.button("✖ Fechar detalhes", **LARGURA):
            st.session_state.pop("candidato_aberto", None)
            st.session_state["versao_tabela"] = st.session_state.get("versao_tabela", 0) + 1
            st.rerun()
        mostrar_detalhe(aberto)


def pagina_candidatos(df: pd.DataFrame) -> None:
    u = utilizador_atual()
    cabecalho("👷 Candidatos", "Pesquise, filtre, contacte e acompanhe cada profissional")
    if u["perfil"] == "Gestor":
        df = df[df["estado"].isin(ESTADOS_GESTOR)]
        st.caption("Perfil de gestor: são apresentados os candidatos em fase de entrevista, "
                   "avaliação, aprovação e contratação.")
    if df.empty:
        st.info("Não existem candidatos para apresentar.")
        if u["perfil"] != "Gestor":
            _formulario_candidato_manual()
        return

    filtrado = _filtrar_candidatos(df)
    st.markdown(f"**{len(filtrado)} candidatos** · selecione uma linha para abrir os detalhes")
    if filtrado.empty:
        st.warning("Nenhum candidato corresponde aos filtros aplicados.")
    else:
        selecionado = _tabela_candidatos(filtrado, f"tabela_{st.session_state.get('versao_tabela', 0)}")
        _botoes_exportacao(filtrado)
        _abrir_detalhe_selecionado(selecionado)
    if u["perfil"] != "Gestor":
        _formulario_candidato_manual()


def _formulario_candidato_manual() -> None:
    """Permite registar um candidato que chegou por outra via (telefone, referência…)."""
    u = utilizador_atual()
    with st.expander("➕ Adicionar candidato manualmente"):
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
    cabecalho("🚨 Pesquisa urgente", "Encontre rapidamente quem pode começar já")
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
        ordenar = a.form_submit_button("⚡ Procurar na base de candidatos", type="primary", **LARGURA)
        procurar = b.form_submit_button("🚀 Procurar novos candidatos com IA", **LARGURA,
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
            "urgencia": "Muito urgente", "exige_fgas": fgas, "exige_viatura": viatura,
            "data_inicio": inicio.isoformat(), "horario": horario, "duracao_prevista": duracao,
            "orcamento": orcamento, "max_resultados": 20, "urgente": True,
        }
        st.rerun()

    pedido = st.session_state.get("pedido_urgente")
    if not pedido:
        st.info("Preencha a necessidade e escolha «Procurar na base de candidatos» para uma resposta "
                "imediata, ou «Procurar novos candidatos com IA» para alargar a pesquisa.")
        return

    ativos = df[~df["estado"].isin(["Arquivado", "Rejeitado", "Contratado"])]
    ordenado = ordenar_para_urgencia(ativos, pedido["especialidades"], pedido["local"], pedido["raio"],
                                     pedido["viatura"], pedido["fgas"], pedido["deslocacao"])
    ordenado = ordenado[ordenado["prioridade"] > 0].head(pedido["maximo"])
    if ordenado.empty:
        st.warning("Nenhum candidato na base de dados cumpre esta necessidade. "
                   "Use «Procurar novos candidatos com IA».")
        return

    st.markdown(f"**{len(ordenado)} candidatos por ordem de prioridade** para {html.escape(pedido['local'])} "
                "— disponibilidade imediata, score, proximidade, competências, contacto direto e experiência.")
    selecionado = _tabela_candidatos(
        ordenado, f"urgente_{st.session_state.get('versao_tabela', 0)}",
        {"Porquê": ordenado["motivos"], "Prioridade": ordenado["prioridade"].round(0).astype(int)},
    )
    _abrir_detalhe_selecionado(selecionado)


# ---------------------------------------------------------------------------
# Página: Tarefas
# ---------------------------------------------------------------------------

def pagina_tarefas() -> None:
    u = utilizador_atual()
    cabecalho("✅ Tarefas", "Lembretes e ações de acompanhamento")
    with st.form("nova_tarefa", clear_on_submit=True):
        a, b, c = st.columns([3, 1, 1])
        titulo = a.text_input("Nova tarefa", placeholder="Ex.: Ligar aos candidatos de Sintra")
        data_limite = b.date_input("Data limite", value=date.today(), format="DD/MM/YYYY")
        c.write("")
        c.write("")
        if c.form_submit_button("Criar tarefa", **LARGURA):
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
    a, b = st.columns(2)
    with a:
        st.subheader(f"Pendentes ({len(pendentes)})")
        listar_tarefas_interativas(pendentes, "tp", mostrar_candidato=True)
    with b:
        st.subheader(f"Concluídas ({len(concluidas)})")
        listar_tarefas_interativas(concluidas[:30], "tc", mostrar_candidato=True)


# ---------------------------------------------------------------------------
# Página: Contratações (gestor e administrador)
# ---------------------------------------------------------------------------

def pagina_contratacoes(df: pd.DataFrame) -> None:
    cabecalho("🤝 Contratações", "Candidatos em decisão, entrevistas e contratações concluídas")
    abas = st.tabs(["Em processo de contratação", "Entrevistas", "Contratações concluídas"])
    with abas[0]:
        em_processo = df[df["estado"].isin(["Entrevista marcada", "Em avaliação técnica", "Aprovado", "Em negociação"])]
        if em_processo.empty:
            st.info("Não existem candidatos em fase de decisão.")
        else:
            st.caption("Selecione um candidato para consultar notas, aprovar, rejeitar ou registar a contratação.")
            selecionado = _tabela_candidatos(em_processo, f"decisao_{st.session_state.get('versao_tabela', 0)}")
            _abrir_detalhe_selecionado(selecionado)
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
    cabecalho("⚙️ Administração", "Utilizadores, pesquisas, auditoria e proteção de dados")
    abas = st.tabs(["Utilizadores", "Pesquisas realizadas", "Fontes consultadas", "Histórico de alterações", "RGPD"])

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
        a, b = st.columns(2)
        with a, st.form("novo_utilizador", clear_on_submit=True):
            st.markdown("**Novo utilizador**")
            nome = st.text_input("Nome")
            email = st.text_input("Email")
            perfil = st.selectbox("Perfil", PERFIS_UTILIZADOR, index=1)
            password = st.text_input("Palavra-passe inicial", type="password")
            if st.form_submit_button("Criar utilizador", type="primary"):
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
        with b, st.form("alterar_password", clear_on_submit=True):
            st.markdown("**Alterar palavra-passe**")
            alvo = st.selectbox("Utilizador", utilizadores, format_func=lambda x: f"{x['nome']} ({x['email']})")
            nova = st.text_input("Nova palavra-passe", type="password")
            if st.form_submit_button("Alterar palavra-passe"):
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
        try:
            pesquisas = db.listar_pesquisas_df()
            if pesquisas.empty:
                st.info("Ainda não foram realizadas pesquisas.")
            else:
                pesquisas["Critérios"] = pesquisas["parametros"].apply(
                    lambda p: f"{lista_para_texto((p or {}).get('especialidades')) or 'Geral'} · "
                              f"{lista_para_texto((p or {}).get('localizacoes'))}")
                st.dataframe(pesquisas.drop(columns=["parametros"]).rename(columns={
                    "id": "N.º", "data": "Data", "utilizador": "Utilizador", "urgente": "Urgente",
                    "total_resultados": "Resultados", "total_candidatos": "Candidatos",
                    "novos": "Novos", "duplicados": "Duplicados"}),
                    hide_index=True, **LARGURA,
                    column_config={"Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})
        except ErroBaseDados as exc:
            st.error(str(exc))

    with abas[2]:
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

    with abas[3]:
        try:
            st.dataframe(_formatar_historico(db.listar_historico()), hide_index=True, **LARGURA,
                         column_config={"Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})
        except ErroBaseDados as exc:
            st.error(str(exc))

    with abas[4]:
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
        if pagina == "Dashboard":
            pagina_dashboard(df)
        elif pagina == "Candidatos":
            pagina_candidatos(df)
        elif pagina == "Pesquisa urgente":
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
