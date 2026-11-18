"""
database.py — Camada de acesso à base de dados (SQLAlchemy).

Por omissão é usada uma base de dados SQLite em data/tecnicos_avac.db.
Para migrar para PostgreSQL basta definir DATABASE_URL, por exemplo:
    DATABASE_URL=postgresql+psycopg://utilizador:password@servidor:5432/avac

Todas as funções devolvem dicionários ou DataFrames (nunca objetos ORM), para
que a interface não dependa de sessões abertas.
"""

from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, event, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from models import (
    CATEGORIAS_ESPECIALIDADES,
    NAO_IDENTIFICADO,
    Base,
    Candidato,
    CandidatoIA,
    Contacto,
    Contratacao,
    Entrevista,
    Especialidade,
    Fonte,
    Historico,
    Nota,
    Pesquisa,
    Tarefa,
    Utilizador,
)
from utils import (
    gerar_chave_dedup,
    hash_password,
    limpar_texto,
    normalizar_email,
    normalizar_telefone,
    normalizar_url,
    url_segura,
    verificar_password,
)

PASTA_DADOS = Path(__file__).resolve().parent / "data"


class ErroBaseDados(Exception):
    """Erro de base de dados com mensagem adequada para mostrar ao utilizador."""


# ---------------------------------------------------------------------------
# Ligação
# ---------------------------------------------------------------------------

_engine = None
_Sessao = None


def _obter_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        # Aceita o formato copiado do Supabase/Neon ("postgresql://…") e usa o controlador psycopg 3.
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url[len(prefixo):]
        return url
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(PASTA_DADOS / 'tecnicos_avac.db').as_posix()}"


def inicializar_bd() -> None:
    """Cria a ligação, as tabelas e o catálogo de especialidades (idempotente)."""
    global _engine, _Sessao
    if _engine is not None:
        return
    url = _obter_url()
    argumentos = {"check_same_thread": False} if url.startswith("sqlite") else {}
    try:
        if url.startswith("postgresql"):
            # Compatível com o "pooler" do Supabase (não suporta prepared statements).
            argumentos = {"prepare_threshold": None}
        _engine = create_engine(url, connect_args=argumentos, pool_pre_ping=True, pool_recycle=300)

        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _ativar_chaves_estrangeiras(ligacao, _registo):
                cursor = ligacao.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        Base.metadata.create_all(_engine)
        _Sessao = sessionmaker(bind=_engine, expire_on_commit=False)
        _semear_especialidades()
    except SQLAlchemyError as exc:
        _engine = None
        raise ErroBaseDados(
            "Não foi possível abrir a base de dados. Verifique a pasta 'data' "
            "ou a variável DATABASE_URL."
        ) from exc


@contextmanager
def sessao():
    """Sessão transacional: confirma no fim ou reverte em caso de erro."""
    if _Sessao is None:
        inicializar_bd()
    s = _Sessao()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _protegido(funcao):
    """Converte erros técnicos do SQLAlchemy numa mensagem amigável."""

    @functools.wraps(funcao)
    def envolvida(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except ErroBaseDados:
            raise
        except SQLAlchemyError as exc:
            raise ErroBaseDados(
                "Ocorreu um erro ao aceder à base de dados. A operação não foi concluída."
            ) from exc

    return envolvida


def _semear_especialidades() -> None:
    with sessao() as s:
        existentes = set(s.scalars(select(Especialidade.nome)).all())
        for categoria, nomes in CATEGORIAS_ESPECIALIDADES.items():
            for nome in nomes:
                if nome not in existentes:
                    s.add(Especialidade(nome=nome, categoria=categoria))


def _registar_historico(s, candidato_id, utilizador, acao, campo="", anterior="", novo="") -> None:
    s.add(
        Historico(
            candidato_id=candidato_id,
            utilizador=utilizador or "",
            acao=acao,
            campo=campo,
            valor_anterior=str(anterior if anterior is not None else "")[:2000],
            valor_novo=str(novo if novo is not None else "")[:2000],
        )
    )


# ---------------------------------------------------------------------------
# Utilizadores
# ---------------------------------------------------------------------------

def _utilizador_dict(u: Utilizador) -> dict:
    return {
        "id": u.id,
        "nome": u.nome,
        "email": u.email,
        "perfil": u.perfil,
        "ativo": u.ativo,
        "criado_em": u.criado_em,
    }


@_protegido
def contar_utilizadores() -> int:
    with sessao() as s:
        return s.scalar(select(func.count(Utilizador.id))) or 0


@_protegido
def criar_utilizador(nome: str, email: str, password: str, perfil: str) -> dict:
    email_n = normalizar_email(email)
    if not email_n:
        raise ErroBaseDados("O endereço de email não é válido.")
    if not (nome or "").strip():
        raise ErroBaseDados("Indique o nome do utilizador.")
    try:
        with sessao() as s:
            u = Utilizador(
                nome=nome.strip(), email=email_n,
                password_hash=hash_password(password), perfil=perfil,
            )
            s.add(u)
            s.flush()
            return _utilizador_dict(u)
    except IntegrityError as exc:
        raise ErroBaseDados("Já existe um utilizador com esse email.") from exc


@_protegido
def autenticar(email: str, password: str) -> Optional[dict]:
    """Devolve o utilizador se as credenciais estiverem corretas e a conta ativa."""
    with sessao() as s:
        u = s.scalar(select(Utilizador).where(Utilizador.email == normalizar_email(email)))
        if u and u.ativo and verificar_password(password, u.password_hash):
            return _utilizador_dict(u)
    return None


@_protegido
def listar_utilizadores() -> list[dict]:
    with sessao() as s:
        return [_utilizador_dict(u) for u in s.scalars(select(Utilizador).order_by(Utilizador.nome))]


@_protegido
def atualizar_utilizador(utilizador_id: int, perfil: str, ativo: bool) -> None:
    with sessao() as s:
        u = s.get(Utilizador, utilizador_id)
        if not u:
            raise ErroBaseDados("Utilizador não encontrado.")
        # Impede que a aplicação fique sem nenhum administrador ativo.
        if u.perfil == "Administrador" and (perfil != "Administrador" or not ativo):
            outros = s.scalar(
                select(func.count(Utilizador.id)).where(
                    Utilizador.perfil == "Administrador",
                    Utilizador.ativo.is_(True),
                    Utilizador.id != u.id,
                )
            )
            if not outros:
                raise ErroBaseDados("Tem de existir pelo menos um administrador ativo.")
        u.perfil, u.ativo = perfil, ativo


@_protegido
def alterar_password(utilizador_id: int, nova_password: str) -> None:
    with sessao() as s:
        u = s.get(Utilizador, utilizador_id)
        if not u:
            raise ErroBaseDados("Utilizador não encontrado.")
        u.password_hash = hash_password(nova_password)


# ---------------------------------------------------------------------------
# Candidatos
# ---------------------------------------------------------------------------

_CAMPOS_CANDIDATO = [c.name for c in Candidato.__table__.columns]


def _candidato_dict(c: Candidato) -> dict:
    return {campo: getattr(c, campo) for campo in _CAMPOS_CANDIDATO}


def _procurar_duplicado(s, email_n: str, tel_n: str, url_n: str, chave: str) -> Optional[Candidato]:
    condicoes = []
    if email_n:
        condicoes.append(Candidato.email_norm == email_n)
    if tel_n:
        condicoes.append(Candidato.telefone_norm == tel_n)
    if url_n:
        condicoes.append(Candidato.url_norm == url_n)
    if chave:
        condicoes.append(Candidato.chave_dedup == chave)
    if not condicoes:
        return None
    return s.scalars(select(Candidato).where(or_(*condicoes))).first()


def _associar_especialidades(s, candidato: Candidato, nomes: list[str]) -> None:
    """Liga o candidato ao catálogo de especialidades, criando as que faltarem."""
    ligadas = []
    for nome in dict.fromkeys(n.strip() for n in nomes if n and n.strip()):
        esp = s.scalar(select(Especialidade).where(func.lower(Especialidade.nome) == nome.lower()))
        if not esp:
            esp = Especialidade(nome=nome[:200], categoria="Outros perfis")
            s.add(esp)
            s.flush()
        ligadas.append(esp)
    candidato.especialidades_rel = ligadas


@_protegido
def guardar_candidato(dados: CandidatoIA, pesquisa_id: Optional[int], utilizador: str) -> tuple[str, int]:
    """
    Guarda um candidato validado. Devolve ("novo" | "duplicado", id).
    Duplicados são detetados por email, telefone, URL do perfil ou pela
    combinação nome + localização + especialidade.
    """
    email_n = normalizar_email(dados.contacto_email)
    tel_n = normalizar_telefone(dados.contacto_telefone)
    url_perfil = url_segura(dados.url_perfil) or url_segura(dados.url_fonte)
    url_n = normalizar_url(url_perfil)
    primeira_esp = dados.especialidades[0] if dados.especialidades else dados.cargo
    chave = gerar_chave_dedup(dados.nome, dados.concelho or dados.localizacao, primeira_esp)

    with sessao() as s:
        existente = _procurar_duplicado(s, email_n, tel_n, url_n, chave)
        if existente:
            # Completa apenas contactos em falta; não sobrepõe o trabalho já feito.
            if email_n and not existente.email_norm:
                existente.email, existente.email_norm = dados.contacto_email, email_n
            if tel_n and not existente.telefone_norm:
                existente.telefone, existente.telefone_norm = dados.contacto_telefone, tel_n
            return "duplicado", existente.id

        try:
            data_recolha = date.fromisoformat(dados.data_recolha[:10])
        except ValueError:
            data_recolha = date.today()

        c = Candidato(
            nome=limpar_texto(dados.nome, 200) or NAO_IDENTIFICADO,
            cargo=limpar_texto(dados.cargo, 250),
            especialidades=[limpar_texto(e, 150) for e in dados.especialidades],
            localizacao=limpar_texto(dados.localizacao, 200),
            distrito=limpar_texto(dados.distrito, 100),
            concelho=limpar_texto(dados.concelho, 100),
            anos_experiencia=dados.anos_experiencia,
            certificacoes=[limpar_texto(e, 150) for e in dados.certificacoes],
            competencias=[limpar_texto(e, 150) for e in dados.competencias],
            experiencias=dados.experiencias,
            certificacao_fgas=dados.certificacao_fgas,
            carta_conducao=dados.carta_conducao,
            viatura_propria=dados.viatura_propria,
            disponibilidade=limpar_texto(dados.disponibilidade, 300),
            disponibilidade_classificacao=dados.disponibilidade_classificacao,
            disponibilidade_imediata=dados.disponibilidade_imediata,
            disponibilidade_urgencias=dados.disponibilidade_urgencias,
            disponibilidade_deslocacoes=dados.disponibilidade_deslocacoes,
            telefone=limpar_texto(dados.contacto_telefone, 50) if tel_n else "",
            email=email_n,
            telefone_norm=tel_n,
            email_norm=email_n,
            url_perfil=url_perfil[:600],
            url_norm=url_n[:600],
            url_fonte=url_segura(dados.url_fonte)[:600],
            fonte=limpar_texto(dados.fonte, 200),
            data_recolha=data_recolha,
            chave_dedup=chave[:400],
            pesquisa_id=pesquisa_id,
            score=dados.score_adequacao,
            nivel_confianca=dados.nivel_confianca,
            justificacao_score=limpar_texto(dados.justificacao_score),
            resumo=limpar_texto(dados.resumo),
            pontos_fortes=[limpar_texto(e) for e in dados.pontos_fortes],
            lacunas=[limpar_texto(e) for e in dados.lacunas],
            perguntas_validacao=[limpar_texto(e) for e in dados.perguntas_validacao],
            mensagem_abordagem=dados.mensagem_abordagem.strip(),
            recomendacao=dados.recomendacao,
            estado="Novo",
        )
        s.add(c)
        s.flush()
        _associar_especialidades(s, c, c.especialidades)
        _registar_historico(s, c.id, utilizador, "Candidato criado", novo=c.nome)
        return "novo", c.id


@_protegido
def listar_candidatos_df(incluir_arquivados: bool = True) -> pd.DataFrame:
    """Todos os candidatos num DataFrame (os filtros são aplicados na interface)."""
    with sessao() as s:
        consulta = select(Candidato).order_by(Candidato.score.desc(), Candidato.id.desc())
        if not incluir_arquivados:
            consulta = consulta.where(Candidato.estado != "Arquivado")
        linhas = [_candidato_dict(c) for c in s.scalars(consulta)]
    return pd.DataFrame(linhas, columns=_CAMPOS_CANDIDATO)


@_protegido
def obter_candidato(candidato_id: int) -> Optional[dict]:
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        return _candidato_dict(c) if c else None


# Campos que a interface pode alterar diretamente.
CAMPOS_EDITAVEIS = {
    "nome", "cargo", "especialidades", "localizacao", "concelho", "distrito",
    "anos_experiencia", "certificacao_fgas", "carta_conducao", "viatura_propria",
    "disponibilidade", "disponibilidade_classificacao", "disponibilidade_imediata",
    "disponibilidade_urgencias", "disponibilidade_deslocacoes",
    "telefone", "email", "mensagem_abordagem", "estado",
    "data_primeiro_contacto", "data_ultimo_contacto", "proxima_acao",
    "data_proxima_acao", "responsavel", "resultado_entrevista",
    "expectativa_salarial", "disponibilidade_inicio", "tipo_contrato_pretendido",
    "area_geografica_pretendida", "documentos_recebidos", "observacoes_gestor",
}


@_protegido
def atualizar_candidato(candidato_id: int, alteracoes: dict, utilizador: str) -> int:
    """Aplica alterações e regista cada uma no histórico. Devolve o n.º de campos alterados."""
    alterados = 0
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        if not c:
            raise ErroBaseDados("Candidato não encontrado.")
        for campo, novo in alteracoes.items():
            if campo not in CAMPOS_EDITAVEIS:
                continue
            if isinstance(novo, str):
                novo = novo.strip()
            anterior = getattr(c, campo)
            if anterior == novo:
                continue
            setattr(c, campo, novo)
            if campo == "email":
                c.email_norm = normalizar_email(novo)
            elif campo == "telefone":
                c.telefone_norm = normalizar_telefone(novo)
            elif campo == "especialidades":
                _associar_especialidades(s, c, novo or [])
            _registar_historico(s, c.id, utilizador, "Alteração", campo, anterior, novo)
            alterados += 1
    return alterados


@_protegido
def eliminar_candidato(candidato_id: int, utilizador: str) -> None:
    """Elimina definitivamente o candidato e todos os registos associados."""
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        if not c:
            raise ErroBaseDados("Candidato não encontrado.")
        s.delete(c)
        # O histórico deixa de conter dados pessoais deste candidato.
        for h in s.scalars(select(Historico).where(Historico.candidato_id == candidato_id)):
            s.delete(h)
        _registar_historico(s, None, utilizador, "Candidato eliminado", novo=f"ID {candidato_id}")


@_protegido
def anonimizar_candidato(candidato_id: int, utilizador: str) -> None:
    """Remove os dados pessoais mantendo apenas informação estatística."""
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        if not c:
            raise ErroBaseDados("Candidato não encontrado.")
        c.nome = f"Candidato anonimizado #{c.id}"
        c.telefone = c.email = c.telefone_norm = c.email_norm = ""
        c.url_perfil = c.url_norm = c.url_fonte = c.chave_dedup = ""
        c.resumo = c.justificacao_score = c.mensagem_abordagem = ""
        c.pontos_fortes, c.lacunas, c.perguntas_validacao = [], [], []
        c.resultado_entrevista = c.observacoes_gestor = c.documentos_recebidos = ""
        c.expectativa_salarial = c.proxima_acao = ""
        c.anonimizado = True
        c.estado = "Arquivado"
        for colecao in (c.notas, c.contactos, c.tarefas, c.entrevistas):
            for registo in list(colecao):
                s.delete(registo)
        for h in s.scalars(select(Historico).where(Historico.candidato_id == candidato_id)):
            s.delete(h)
        _registar_historico(s, c.id, utilizador, "Candidato anonimizado")


@_protegido
def candidatos_para_revisao(meses: int) -> pd.DataFrame:
    """Candidatos recolhidos há mais de N meses e não contratados (conservação limitada)."""
    limite = date.today() - timedelta(days=30 * meses)
    with sessao() as s:
        consulta = select(Candidato).where(
            Candidato.data_recolha < limite,
            Candidato.estado != "Contratado",
            Candidato.anonimizado.is_(False),
        )
        linhas = [
            {"id": c.id, "nome": c.nome, "estado": c.estado, "data_recolha": c.data_recolha}
            for c in s.scalars(consulta)
        ]
    return pd.DataFrame(linhas, columns=["id", "nome", "estado", "data_recolha"])


# ---------------------------------------------------------------------------
# Contactos, notas, tarefas e entrevistas
# ---------------------------------------------------------------------------

@_protegido
def registar_contacto(candidato_id: int, utilizador: str, meio: str, resultado: str, notas: str) -> None:
    """Regista um contacto e atualiza datas e estado do candidato."""
    hoje = date.today()
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        if not c:
            raise ErroBaseDados("Candidato não encontrado.")
        s.add(Contacto(candidato_id=candidato_id, utilizador=utilizador, meio=meio,
                       resultado=resultado, notas=(notas or "").strip()))
        if not c.data_primeiro_contacto:
            c.data_primeiro_contacto = hoje
        c.data_ultimo_contacto = hoje

        estado_anterior = c.estado
        iniciais = {"Novo", "Pré-selecionado", "Contacto pendente", "Contactado", "Sem resposta"}
        if c.estado in iniciais:
            if resultado in ("Respondeu positivamente", "Pediu mais informações"):
                c.estado = "Respondeu"
            elif resultado == "Sem resposta" and c.estado == "Contactado":
                c.estado = "Sem resposta"
            elif resultado == "Respondeu negativamente":
                c.estado = "Rejeitado"
            elif c.estado != "Sem resposta" or resultado != "Sem resposta":
                c.estado = "Contactado"
        if c.estado != estado_anterior:
            _registar_historico(s, c.id, utilizador, "Alteração", "estado", estado_anterior, c.estado)
        _registar_historico(s, c.id, utilizador, "Contacto registado", meio, "", resultado)


@_protegido
def listar_contactos(candidato_id: int) -> list[dict]:
    with sessao() as s:
        consulta = select(Contacto).where(Contacto.candidato_id == candidato_id).order_by(Contacto.data.desc())
        return [
            {"data": x.data, "meio": x.meio, "resultado": x.resultado,
             "utilizador": x.utilizador, "notas": x.notas}
            for x in s.scalars(consulta)
        ]


@_protegido
def adicionar_nota(candidato_id: int, utilizador: str, texto: str) -> None:
    if not (texto or "").strip():
        raise ErroBaseDados("A nota está vazia.")
    with sessao() as s:
        s.add(Nota(candidato_id=candidato_id, utilizador=utilizador, texto=texto.strip()))


@_protegido
def listar_notas(candidato_id: int) -> list[dict]:
    with sessao() as s:
        consulta = select(Nota).where(Nota.candidato_id == candidato_id).order_by(Nota.criado_em.desc())
        return [{"data": n.criado_em, "utilizador": n.utilizador, "texto": n.texto} for n in s.scalars(consulta)]


@_protegido
def criar_tarefa(titulo: str, responsavel: str, data_limite: Optional[date],
                 criado_por: str, candidato_id: Optional[int] = None) -> None:
    if not (titulo or "").strip():
        raise ErroBaseDados("Indique a descrição da tarefa.")
    with sessao() as s:
        s.add(Tarefa(candidato_id=candidato_id, titulo=titulo.strip()[:300],
                     responsavel=responsavel, data_limite=data_limite, criado_por=criado_por))
        if candidato_id:
            c = s.get(Candidato, candidato_id)
            if c:
                c.proxima_acao, c.data_proxima_acao = titulo.strip()[:300], data_limite


@_protegido
def listar_tarefas(candidato_id: Optional[int] = None, apenas_pendentes: bool = False) -> list[dict]:
    with sessao() as s:
        consulta = select(Tarefa, Candidato.nome).outerjoin(Candidato, Tarefa.candidato_id == Candidato.id)
        if candidato_id is not None:
            consulta = consulta.where(Tarefa.candidato_id == candidato_id)
        if apenas_pendentes:
            consulta = consulta.where(Tarefa.concluida.is_(False))
        consulta = consulta.order_by(Tarefa.concluida, Tarefa.data_limite.is_(None), Tarefa.data_limite)
        return [
            {"id": t.id, "titulo": t.titulo, "responsavel": t.responsavel,
             "data_limite": t.data_limite, "concluida": t.concluida,
             "candidato_id": t.candidato_id, "candidato": nome or ""}
            for t, nome in s.execute(consulta)
        ]


@_protegido
def marcar_tarefa(tarefa_id: int, concluida: bool) -> None:
    with sessao() as s:
        t = s.get(Tarefa, tarefa_id)
        if t:
            t.concluida = concluida


@_protegido
def criar_entrevista(candidato_id: int, data: Optional[datetime], tipo: str,
                     entrevistador: str, notas: str, utilizador: str) -> None:
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        if not c:
            raise ErroBaseDados("Candidato não encontrado.")
        s.add(Entrevista(candidato_id=candidato_id, data=data, tipo=tipo,
                         entrevistador=entrevistador, notas=(notas or "").strip()))
        if c.estado not in ("Aprovado", "Em negociação", "Contratado", "Em avaliação técnica"):
            _registar_historico(s, c.id, utilizador, "Alteração", "estado", c.estado, "Entrevista marcada")
            c.estado = "Entrevista marcada"
        _registar_historico(s, c.id, utilizador, "Entrevista marcada", novo=str(data or ""))


@_protegido
def atualizar_entrevista(entrevista_id: int, resultado: str, notas: str) -> None:
    with sessao() as s:
        e = s.get(Entrevista, entrevista_id)
        if e:
            e.resultado, e.notas = resultado, (notas or "").strip()


@_protegido
def listar_entrevistas(candidato_id: Optional[int] = None) -> list[dict]:
    with sessao() as s:
        consulta = select(Entrevista, Candidato.nome).join(Candidato, Entrevista.candidato_id == Candidato.id)
        if candidato_id is not None:
            consulta = consulta.where(Entrevista.candidato_id == candidato_id)
        consulta = consulta.order_by(Entrevista.data.desc())
        return [
            {"id": e.id, "candidato_id": e.candidato_id, "candidato": nome, "data": e.data,
             "tipo": e.tipo, "entrevistador": e.entrevistador, "resultado": e.resultado, "notas": e.notas}
            for e, nome in s.execute(consulta)
        ]


# ---------------------------------------------------------------------------
# Pesquisas e fontes
# ---------------------------------------------------------------------------

@_protegido
def registar_pesquisa(utilizador: str, parametros: dict, consultas: list[str], urgente: bool) -> int:
    with sessao() as s:
        p = Pesquisa(utilizador=utilizador, parametros=parametros, consultas=consultas, urgente=urgente)
        s.add(p)
        s.flush()
        return p.id


@_protegido
def concluir_pesquisa(pesquisa_id: int, total_resultados: int, total_candidatos: int,
                      novos: int, duplicados: int, fontes: list[dict],
                      candidato_ids: Optional[list[int]] = None) -> None:
    with sessao() as s:
        p = s.get(Pesquisa, pesquisa_id)
        if not p:
            return
        p.total_resultados, p.total_candidatos = total_resultados, total_candidatos
        p.novos, p.duplicados = novos, duplicados
        if candidato_ids is not None:
            # Todos os candidatos encontrados nesta pesquisa (novos e já existentes).
            p.parametros = {**(p.parametros or {}), "candidatos_ids": list(dict.fromkeys(candidato_ids))}
        for f in fontes:
            s.add(Fonte(pesquisa_id=pesquisa_id, url=(f.get("url") or "")[:600],
                        titulo=limpar_texto(f.get("titulo"), 400),
                        dominio=(f.get("dominio") or "")[:200],
                        tipo_resultado=(f.get("tipo_resultado") or "")[:40]))


@_protegido
def listar_pesquisas_df() -> pd.DataFrame:
    colunas = ["id", "data", "utilizador", "urgente", "total_resultados",
               "total_candidatos", "novos", "duplicados", "parametros"]
    with sessao() as s:
        linhas = [{c: getattr(p, c) for c in colunas}
                  for p in s.scalars(select(Pesquisa).order_by(Pesquisa.data.desc()))]
    return pd.DataFrame(linhas, columns=colunas)


@_protegido
def candidatos_por_pesquisa() -> dict[int, list[int]]:
    """{id da pesquisa: ids dos candidatos encontrados nela}, incluindo os que já existiam."""
    with sessao() as s:
        pesquisas = list(s.scalars(select(Pesquisa)))
        candidatos = list(s.execute(select(Candidato.id, Candidato.pesquisa_id, Candidato.url_fonte,
                                           Candidato.url_perfil)))
        resultado: dict[int, list[int]] = {}
        for p in pesquisas:
            guardados = (p.parametros or {}).get("candidatos_ids")
            if guardados is not None:
                resultado[p.id] = [int(i) for i in guardados]
                continue
            # Pesquisas antigas: os candidatos criados nela e os que vieram das mesmas páginas.
            urls = set(s.scalars(select(Fonte.url).where(Fonte.pesquisa_id == p.id)))
            resultado[p.id] = [c.id for c in candidatos
                               if c.pesquisa_id == p.id or c.url_fonte in urls or c.url_perfil in urls]
    return resultado


@_protegido
def listar_fontes_df(limite: int = 500) -> pd.DataFrame:
    colunas = ["data", "pesquisa_id", "dominio", "tipo_resultado", "titulo", "url"]
    with sessao() as s:
        linhas = [{c: getattr(f, c) for c in colunas}
                  for f in s.scalars(select(Fonte).order_by(Fonte.data.desc()).limit(limite))]
    return pd.DataFrame(linhas, columns=colunas)


# ---------------------------------------------------------------------------
# Histórico e contratações
# ---------------------------------------------------------------------------

@_protegido
def listar_historico(candidato_id: Optional[int] = None, limite: int = 300) -> pd.DataFrame:
    colunas = ["data", "utilizador", "candidato_id", "acao", "campo", "valor_anterior", "valor_novo"]
    with sessao() as s:
        consulta = select(Historico).order_by(Historico.data.desc()).limit(limite)
        if candidato_id is not None:
            consulta = consulta.where(Historico.candidato_id == candidato_id)
        linhas = [{c: getattr(h, c) for c in colunas} for h in s.scalars(consulta)]
    return pd.DataFrame(linhas, columns=colunas)


@_protegido
def registar_contratacao(candidato_id: int, data_contratacao: date, data_inicio: Optional[date],
                         funcao: str, tipo_contrato: str, remuneracao: str,
                         observacoes: str, aprovado_por: str) -> None:
    with sessao() as s:
        c = s.get(Candidato, candidato_id)
        if not c:
            raise ErroBaseDados("Candidato não encontrado.")
        s.add(Contratacao(candidato_id=candidato_id, data_contratacao=data_contratacao,
                          data_inicio=data_inicio, funcao=funcao.strip(), tipo_contrato=tipo_contrato,
                          remuneracao=remuneracao.strip(), observacoes=observacoes.strip(),
                          aprovado_por=aprovado_por))
        _registar_historico(s, c.id, aprovado_por, "Alteração", "estado", c.estado, "Contratado")
        _registar_historico(s, c.id, aprovado_por, "Contratação registada", novo=funcao)
        c.estado = "Contratado"


@_protegido
def listar_contratacoes_df() -> pd.DataFrame:
    colunas = ["candidato", "funcao", "tipo_contrato", "data_contratacao",
               "data_inicio", "remuneracao", "aprovado_por", "observacoes"]
    with sessao() as s:
        consulta = (
            select(Contratacao, Candidato.nome)
            .join(Candidato, Contratacao.candidato_id == Candidato.id)
            .order_by(Contratacao.data_contratacao.desc())
        )
        linhas = [
            {"candidato": nome, **{c: getattr(k, c) for c in colunas if c != "candidato"}}
            for k, nome in s.execute(consulta)
        ]
    return pd.DataFrame(linhas, columns=colunas)
