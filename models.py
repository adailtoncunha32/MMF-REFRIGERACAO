"""
models.py — Constantes de domínio, esquemas de validação (Pydantic) e
modelos da base de dados (SQLAlchemy) da aplicação "Técnicos AVAC Pro".

Os modelos SQLAlchemy usam apenas tipos portáveis, pelo que a migração de
SQLite para PostgreSQL se resume a alterar a variável DATABASE_URL.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

NOME_APP = "Técnicos AVAC Pro"

CATEGORIAS_ESPECIALIDADES: dict[str, list[str]] = {
    "AVAC e climatização": [
        "Técnico de AVAC",
        "Técnico de ar condicionado",
        "Técnico de climatização",
        "Técnico de manutenção AVAC",
        "Técnico de instalação AVAC",
        "Técnico de assistência técnica",
        "Técnico de manutenção preventiva e corretiva",
        "Técnico de sistemas de ar condicionado em condutas",
        "Técnico de sistemas Split",
        "Técnico de sistemas de teto",
        "Técnico de sistemas de chão",
        "Técnico de unidades rooftop",
        "Técnico de unidades de tratamento de ar",
    ],
    "Bombas de calor e aquecimento": [
        "Técnico de bombas de calor para AQS",
        "Técnico de bombas de calor para aquecimento central",
        "Técnico de aquecimento central",
        "Técnico de sistemas hidrónicos",
        "Técnico de manutenção de bombas de calor",
        "Técnico de instalação e reparação de bombas de calor",
    ],
    "Sistemas VRV e VRF": [
        "Técnico de sistemas VRV",
        "Técnico de sistemas VRF",
        "Técnico especializado em sistemas de expansão direta",
        "Técnico de diagnóstico e reparação VRV/VRF",
        "Técnico de comissionamento de sistemas VRV/VRF",
    ],
    "Refrigeração": [
        "Técnico de refrigeração comercial",
        "Técnico de refrigeração industrial",
        "Técnico de câmaras frigoríficas",
        "Técnico de chillers",
        "Técnico de arrefecedores industriais",
        "Técnico de equipamentos de frio comercial",
        "Técnico de manutenção frigorífica",
    ],
    "Gases fluorados": [
        "Técnico certificado em gases fluorados",
        "Técnico com certificação F-Gas",
        "Técnico habilitado para manuseamento de gases fluorados",
        "Técnico de deteção e reparação de fugas de refrigerante",
    ],
    "Energias solares e águas quentes": [
        "Técnico de instalação de painéis solares térmicos",
        "Técnico de reparação de painéis solares",
        "Técnico de termossifões",
        "Técnico de sistemas solares para AQS",
        "Técnico de manutenção de sistemas solares térmicos",
    ],
    "Caldeiras e aquecimento": [
        "Técnico de caldeiras elétricas",
        "Técnico de caldeiras a gasóleo",
        "Técnico de manutenção de caldeiras",
        "Técnico de sistemas de aquecimento central",
        "Técnico de queimadores e sistemas de combustão",
    ],
    "Engenharia": [
        "Engenheiro de AVAC",
        "Engenheiro mecânico (AVAC)",
        "Engenheiro de climatização",
        "Engenheiro de refrigeração",
        "Engenheiro eletrotécnico",
        "Engenheiro de energia e energias renováveis",
        "Engenheiro projetista de AVAC",
        "Engenheiro de manutenção",
        "Engenheiro de comissionamento",
        "Diretor de obra de AVAC",
        "Gestor de projeto de AVAC",
        "Orçamentista de AVAC",
        "Técnico responsável de instalações (TRE/TIM)",
        "Perito qualificado em certificação energética",
    ],
    "Outros perfis": [
        "Ajudante de AVAC",
        "Ajudante de refrigeração",
        "Estagiário de AVAC",
        "Técnico polivalente de manutenção",
        "Encarregado de equipa técnica",
        "Responsável de manutenção",
        "Supervisor de instalações técnicas",
    ],
}

TODAS_ESPECIALIDADES: list[str] = [
    esp for lista in CATEGORIAS_ESPECIALIDADES.values() for esp in lista
]

LOCALIZACOES: list[str] = [
    "Lisboa Centro",
    "Grande Lisboa",
    "Sintra",
    "Cascais",
    "Oeiras",
    "Amadora",
    "Loures",
    "Odivelas",
    "Vila Franca de Xira",
    "Almada",
    "Seixal",
    "Barreiro",
    "Setúbal",
    "Margem Sul",
    "Outra localização",
]

# Coordenadas aproximadas (latitude, longitude) usadas no cálculo de distâncias.
COORDENADAS: dict[str, tuple[float, float]] = {
    "Lisboa Centro": (38.7223, -9.1393),
    "Lisboa": (38.7223, -9.1393),
    "Grande Lisboa": (38.7500, -9.1800),
    "Sintra": (38.8029, -9.3817),
    "Cascais": (38.6979, -9.4215),
    "Oeiras": (38.6969, -9.3146),
    "Amadora": (38.7578, -9.2245),
    "Loures": (38.8309, -9.1685),
    "Odivelas": (38.7927, -9.1838),
    "Vila Franca de Xira": (38.9553, -8.9897),
    "Almada": (38.6790, -9.1569),
    "Seixal": (38.6401, -9.1014),
    "Barreiro": (38.6631, -9.0724),
    "Setúbal": (38.5244, -8.8882),
    "Margem Sul": (38.6500, -9.1000),
    "Mafra": (38.9369, -9.3276),
    "Montijo": (38.7067, -8.9739),
    "Palmela": (38.5690, -8.9013),
    "Sesimbra": (38.4445, -9.1015),
    "Moita": (38.6508, -8.9904),
    "Alcochete": (38.7553, -8.9608),
    "Torres Vedras": (39.0911, -9.2586),
    "Queluz": (38.7566, -9.2545),
    "Santarém": (39.2362, -8.6850),
    "Leiria": (39.7436, -8.8071),
    "Coimbra": (40.2033, -8.4103),
    "Porto": (41.1579, -8.6291),
    "Braga": (41.5454, -8.4265),
    "Aveiro": (40.6405, -8.6538),
    "Évora": (38.5714, -7.9135),
    "Faro": (37.0194, -7.9304),
}

DISPONIBILIDADES: list[str] = [
    "Disponibilidade imediata",
    "Deslocações",
    "Trabalho fora de Lisboa",
    "Assistência urgente",
    "Trabalho por turnos",
    "Fins de semana",
]

TIPOS_CONTRATACAO: list[str] = [
    "Ainda não definido",
    "Contrato sem termo",
    "Contrato a termo",
    "Prestação de serviços",
    "Trabalho temporário",
    "Subcontratação",
    "Trabalho pontual",
]

URGENCIAS: list[str] = ["Normal", "Urgente", "Muito urgente"]

ESTADOS: list[str] = [
    "Novo",
    "Pré-selecionado",
    "Contacto pendente",
    "Contactado",
    "Respondeu",
    "Entrevista marcada",
    "Em avaliação técnica",
    "Aprovado",
    "Em negociação",
    "Contratado",
    "Rejeitado",
    "Sem resposta",
    "Arquivado",
]

# Estados visíveis para o perfil "Gestor".
ESTADOS_GESTOR: list[str] = [
    "Entrevista marcada",
    "Em avaliação técnica",
    "Aprovado",
    "Em negociação",
    "Contratado",
    "Rejeitado",
]

MEIOS_CONTACTO: list[str] = [
    "Telefone",
    "Email",
    "WhatsApp",
    "LinkedIn",
    "Formulário do website",
    "Outro",
]

RESULTADOS_CONTACTO: list[str] = [
    "Sem resposta",
    "Respondeu positivamente",
    "Respondeu negativamente",
    "Pediu mais informações",
    "Número inválido",
    "Contacto não disponível",
]

RECOMENDACOES: list[str] = [
    "Contactar imediatamente",
    "Contactar",
    "Guardar para mais tarde",
    "Não recomendado",
]

CLASSIF_DISPONIBILIDADE: list[str] = [
    "Confirmada",
    "Provável",
    "Desconhecida",
    "Não disponível",
]

TRI_ESTADO: list[str] = ["Sim", "Não", "Desconhecida"]
TRI_EXPERIENCIA: list[str] = ["Sim", "Não", "Não identificado"]

TIPOS_RESULTADO: list[str] = [
    "pessoa",
    "curriculo",
    "perfil_profissional",
    "empresa",
    "anuncio_emprego",
    "diretorio",
    "irrelevante",
]
# Tipos de resultado que correspondem a um candidato individual.
TIPOS_CANDIDATO: set[str] = {"pessoa", "curriculo", "perfil_profissional"}

PERFIS_UTILIZADOR: list[str] = ["Administrador", "Recrutador", "Gestor"]

# Áreas de experiência avaliadas pela IA (chave técnica -> rótulo legível).
AREAS_EXPERIENCIA: dict[str, str] = {
    "avac": "AVAC",
    "refrigeracao": "Refrigeração",
    "bombas_calor": "Bombas de calor",
    "vrv_vrf": "Sistemas VRV/VRF",
    "ac_condutas": "Ar condicionado — condutas",
    "ac_splits": "Ar condicionado — splits",
    "ac_teto": "Ar condicionado — teto",
    "ac_chao": "Ar condicionado — chão",
    "paineis_solares": "Painéis solares",
    "termossifoes": "Termossifões",
    "caldeiras_eletricas": "Caldeiras elétricas",
    "caldeiras_gasoleo": "Caldeiras a gasóleo",
}

NAO_IDENTIFICADO = "Não identificado"


# ---------------------------------------------------------------------------
# Esquemas Pydantic — validação da resposta da IA
# ---------------------------------------------------------------------------

def _texto(valor) -> str:
    """Converte qualquer valor recebido da IA numa string limpa."""
    if valor is None:
        return ""
    return str(valor).strip()


def _lista(valor) -> list[str]:
    """Garante uma lista de strings, mesmo que a IA devolva outro formato."""
    if valor is None:
        return []
    if isinstance(valor, str):
        return [p.strip() for p in valor.split(",") if p.strip()]
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor if str(v).strip()]
    return []


class CandidatoIA(BaseModel):
    """Candidato extraído e avaliado pela IA a partir de um resultado de pesquisa."""

    indice_resultado: int = -1
    tipo_resultado: str = "pessoa"
    nome: str = NAO_IDENTIFICADO
    cargo: str = ""
    especialidades: list[str] = Field(default_factory=list)
    localizacao: str = ""
    distrito: str = ""
    concelho: str = ""
    anos_experiencia: Optional[int] = None
    certificacoes: list[str] = Field(default_factory=list)
    competencias: list[str] = Field(default_factory=list)
    experiencias: dict[str, str] = Field(default_factory=dict)
    certificacao_fgas: str = "Desconhecida"
    carta_conducao: str = "Desconhecida"
    viatura_propria: str = "Desconhecida"
    disponibilidade: str = ""
    disponibilidade_classificacao: str = "Desconhecida"
    disponibilidade_imediata: str = "Desconhecida"
    disponibilidade_urgencias: str = "Desconhecida"
    disponibilidade_deslocacoes: str = "Desconhecida"
    contacto_telefone: str = ""
    contacto_email: str = ""
    url_perfil: str = ""
    url_fonte: str = ""
    fonte: str = ""
    score_adequacao: int = 0
    nivel_confianca: int = 0
    justificacao_score: str = ""
    resumo: str = ""
    pontos_fortes: list[str] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    perguntas_validacao: list[str] = Field(default_factory=list)
    mensagem_abordagem: str = ""
    recomendacao: str = "Guardar para mais tarde"
    data_recolha: str = ""

    @field_validator(
        "nome", "cargo", "localizacao", "distrito", "concelho", "disponibilidade",
        "contacto_telefone", "contacto_email", "url_perfil", "url_fonte", "fonte",
        "justificacao_score", "resumo", "mensagem_abordagem", "data_recolha",
        "tipo_resultado", mode="before",
    )
    @classmethod
    def _validar_texto(cls, v):
        return _texto(v)

    @field_validator(
        "especialidades", "certificacoes", "competencias", "pontos_fortes",
        "lacunas", "perguntas_validacao", mode="before",
    )
    @classmethod
    def _validar_lista(cls, v):
        return _lista(v)

    @field_validator("score_adequacao", "nivel_confianca", mode="before")
    @classmethod
    def _validar_percentagem(cls, v):
        try:
            numero = int(round(float(v)))
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, numero))

    @field_validator("anos_experiencia", mode="before")
    @classmethod
    def _validar_anos(cls, v):
        if v in (None, "", "null"):
            return None
        try:
            numero = int(round(float(v)))
        except (TypeError, ValueError):
            return None
        return numero if 0 <= numero <= 60 else None

    @field_validator(
        "certificacao_fgas", "carta_conducao", "viatura_propria",
        "disponibilidade_imediata", "disponibilidade_urgencias",
        "disponibilidade_deslocacoes", mode="before",
    )
    @classmethod
    def _validar_tri_estado(cls, v):
        v = _texto(v)
        return v if v in TRI_ESTADO else "Desconhecida"

    @field_validator("disponibilidade_classificacao", mode="before")
    @classmethod
    def _validar_classificacao(cls, v):
        v = _texto(v)
        return v if v in CLASSIF_DISPONIBILIDADE else "Desconhecida"

    @field_validator("recomendacao", mode="before")
    @classmethod
    def _validar_recomendacao(cls, v):
        v = _texto(v)
        return v if v in RECOMENDACOES else "Guardar para mais tarde"

    @field_validator("experiencias", mode="before")
    @classmethod
    def _validar_experiencias(cls, v):
        origem = v if isinstance(v, dict) else {}
        resultado = {}
        for chave in AREAS_EXPERIENCIA:
            valor = _texto(origem.get(chave))
            resultado[chave] = valor if valor in TRI_EXPERIENCIA else NAO_IDENTIFICADO
        return resultado

    @field_validator("nome", mode="after")
    @classmethod
    def _nome_por_defeito(cls, v):
        return v or NAO_IDENTIFICADO


class ResultadoDescartado(BaseModel):
    """Resultado de pesquisa que a IA classificou como não sendo um candidato."""

    indice_resultado: int = -1
    tipo_resultado: str = "irrelevante"
    motivo: str = ""


class RespostaIA(BaseModel):
    """Estrutura completa devolvida pela IA para um lote de resultados."""

    candidatos: list[CandidatoIA] = Field(default_factory=list)
    descartados: list[ResultadoDescartado] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Modelos SQLAlchemy — tabelas da base de dados
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


candidato_especialidade = Table(
    "candidato_especialidade",
    Base.metadata,
    Column("candidato_id", ForeignKey("candidatos.id", ondelete="CASCADE"), primary_key=True),
    Column("especialidade_id", ForeignKey("especialidades.id", ondelete="CASCADE"), primary_key=True),
)


class Utilizador(Base):
    __tablename__ = "utilizadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    perfil: Mapped[str] = mapped_column(String(30), default="Recrutador")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Especialidade(Base):
    __tablename__ = "especialidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    categoria: Mapped[str] = mapped_column(String(100), default="Outros perfis")


class Candidato(Base):
    __tablename__ = "candidatos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- Dados profissionais recolhidos ---
    nome: Mapped[str] = mapped_column(String(200), default=NAO_IDENTIFICADO)
    cargo: Mapped[str] = mapped_column(String(250), default="")
    especialidades: Mapped[list] = mapped_column(JSON, default=list)
    localizacao: Mapped[str] = mapped_column(String(200), default="")
    distrito: Mapped[str] = mapped_column(String(100), default="")
    concelho: Mapped[str] = mapped_column(String(100), default="")
    anos_experiencia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    certificacoes: Mapped[list] = mapped_column(JSON, default=list)
    competencias: Mapped[list] = mapped_column(JSON, default=list)
    experiencias: Mapped[dict] = mapped_column(JSON, default=dict)
    certificacao_fgas: Mapped[str] = mapped_column(String(20), default="Desconhecida")
    carta_conducao: Mapped[str] = mapped_column(String(20), default="Desconhecida")
    viatura_propria: Mapped[str] = mapped_column(String(20), default="Desconhecida")
    disponibilidade: Mapped[str] = mapped_column(String(300), default="")
    disponibilidade_classificacao: Mapped[str] = mapped_column(String(30), default="Desconhecida")
    disponibilidade_imediata: Mapped[str] = mapped_column(String(20), default="Desconhecida")
    disponibilidade_urgencias: Mapped[str] = mapped_column(String(20), default="Desconhecida")
    disponibilidade_deslocacoes: Mapped[str] = mapped_column(String(20), default="Desconhecida")

    # --- Contactos profissionais públicos ---
    telefone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    telefone_norm: Mapped[str] = mapped_column(String(30), default="", index=True)
    email_norm: Mapped[str] = mapped_column(String(200), default="", index=True)

    # --- Origem dos dados (transparência / RGPD) ---
    url_perfil: Mapped[str] = mapped_column(String(600), default="")
    url_norm: Mapped[str] = mapped_column(String(600), default="", index=True)
    url_fonte: Mapped[str] = mapped_column(String(600), default="")
    fonte: Mapped[str] = mapped_column(String(200), default="")
    data_recolha: Mapped[date] = mapped_column(Date, default=date.today)
    chave_dedup: Mapped[str] = mapped_column(String(400), default="", index=True)
    pesquisa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pesquisas.id"), nullable=True)

    # --- Avaliação da IA ---
    score: Mapped[int] = mapped_column(Integer, default=0)
    nivel_confianca: Mapped[int] = mapped_column(Integer, default=0)
    justificacao_score: Mapped[str] = mapped_column(Text, default="")
    resumo: Mapped[str] = mapped_column(Text, default="")
    pontos_fortes: Mapped[list] = mapped_column(JSON, default=list)
    lacunas: Mapped[list] = mapped_column(JSON, default=list)
    perguntas_validacao: Mapped[list] = mapped_column(JSON, default=list)
    mensagem_abordagem: Mapped[str] = mapped_column(Text, default="")
    recomendacao: Mapped[str] = mapped_column(String(50), default="Guardar para mais tarde")

    # --- Ciclo de recrutamento ---
    estado: Mapped[str] = mapped_column(String(40), default="Novo", index=True)
    data_primeiro_contacto: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    data_ultimo_contacto: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    proxima_acao: Mapped[str] = mapped_column(String(300), default="")
    data_proxima_acao: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    responsavel: Mapped[str] = mapped_column(String(150), default="")
    resultado_entrevista: Mapped[str] = mapped_column(Text, default="")
    expectativa_salarial: Mapped[str] = mapped_column(String(150), default="")
    disponibilidade_inicio: Mapped[str] = mapped_column(String(150), default="")
    tipo_contrato_pretendido: Mapped[str] = mapped_column(String(60), default="")
    area_geografica_pretendida: Mapped[str] = mapped_column(String(200), default="")
    documentos_recebidos: Mapped[str] = mapped_column(Text, default="")
    observacoes_gestor: Mapped[str] = mapped_column(Text, default="")

    anonimizado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    especialidades_rel = relationship("Especialidade", secondary=candidato_especialidade, lazy="selectin")
    contactos = relationship("Contacto", cascade="all, delete-orphan", back_populates="candidato")
    notas = relationship("Nota", cascade="all, delete-orphan", back_populates="candidato")
    tarefas = relationship("Tarefa", cascade="all, delete-orphan", back_populates="candidato")
    entrevistas = relationship("Entrevista", cascade="all, delete-orphan", back_populates="candidato")
    contratacoes = relationship("Contratacao", cascade="all, delete-orphan", back_populates="candidato")


class Contacto(Base):
    __tablename__ = "contactos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id", ondelete="CASCADE"), index=True)
    utilizador: Mapped[str] = mapped_column(String(150), default="")
    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    meio: Mapped[str] = mapped_column(String(40), default="Telefone")
    resultado: Mapped[str] = mapped_column(String(60), default="Sem resposta")
    notas: Mapped[str] = mapped_column(Text, default="")

    candidato = relationship("Candidato", back_populates="contactos")


class Nota(Base):
    __tablename__ = "notas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id", ondelete="CASCADE"), index=True)
    utilizador: Mapped[str] = mapped_column(String(150), default="")
    texto: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    candidato = relationship("Candidato", back_populates="notas")


class Tarefa(Base):
    __tablename__ = "tarefas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidato_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("candidatos.id", ondelete="CASCADE"), nullable=True, index=True
    )
    titulo: Mapped[str] = mapped_column(String(300))
    responsavel: Mapped[str] = mapped_column(String(150), default="")
    data_limite: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    concluida: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_por: Mapped[str] = mapped_column(String(150), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    candidato = relationship("Candidato", back_populates="tarefas")


class Entrevista(Base):
    __tablename__ = "entrevistas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id", ondelete="CASCADE"), index=True)
    data: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tipo: Mapped[str] = mapped_column(String(60), default="Presencial")
    entrevistador: Mapped[str] = mapped_column(String(150), default="")
    resultado: Mapped[str] = mapped_column(String(60), default="Por realizar")
    notas: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    candidato = relationship("Candidato", back_populates="entrevistas")


class Pesquisa(Base):
    __tablename__ = "pesquisas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilizador: Mapped[str] = mapped_column(String(150), default="")
    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    urgente: Mapped[bool] = mapped_column(Boolean, default=False)
    parametros: Mapped[dict] = mapped_column(JSON, default=dict)
    consultas: Mapped[list] = mapped_column(JSON, default=list)
    total_resultados: Mapped[int] = mapped_column(Integer, default=0)
    total_candidatos: Mapped[int] = mapped_column(Integer, default=0)
    novos: Mapped[int] = mapped_column(Integer, default=0)
    duplicados: Mapped[int] = mapped_column(Integer, default=0)

    fontes = relationship("Fonte", cascade="all, delete-orphan", back_populates="pesquisa")


class GrupoFacebook(Base):
    """Grupos públicos de Facebook de AVAC descobertos nas pesquisas (lidos em todas as seguintes)."""
    __tablename__ = "grupos_facebook"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(300), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    descoberto_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pessoas_encontradas: Mapped[int] = mapped_column(Integer, default=0)


class Fonte(Base):
    __tablename__ = "fontes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pesquisa_id: Mapped[int] = mapped_column(ForeignKey("pesquisas.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(600), default="")
    titulo: Mapped[str] = mapped_column(String(400), default="")
    dominio: Mapped[str] = mapped_column(String(200), default="")
    tipo_resultado: Mapped[str] = mapped_column(String(40), default="")
    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    pesquisa = relationship("Pesquisa", back_populates="fontes")


class Historico(Base):
    __tablename__ = "historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidato_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    utilizador: Mapped[str] = mapped_column(String(150), default="")
    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    acao: Mapped[str] = mapped_column(String(80), default="")
    campo: Mapped[str] = mapped_column(String(80), default="")
    valor_anterior: Mapped[str] = mapped_column(Text, default="")
    valor_novo: Mapped[str] = mapped_column(Text, default="")


class Contratacao(Base):
    __tablename__ = "contratacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id", ondelete="CASCADE"), index=True)
    data_contratacao: Mapped[date] = mapped_column(Date, default=date.today)
    data_inicio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    funcao: Mapped[str] = mapped_column(String(200), default="")
    tipo_contrato: Mapped[str] = mapped_column(String(60), default="")
    remuneracao: Mapped[str] = mapped_column(String(150), default="")
    aprovado_por: Mapped[str] = mapped_column(String(150), default="")
    observacoes: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    candidato = relationship("Candidato", back_populates="contratacoes")
