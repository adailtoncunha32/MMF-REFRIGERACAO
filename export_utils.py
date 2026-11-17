"""
export_utils.py — Exportação dos candidatos filtrados para CSV, Excel e PDF,
com colunas legíveis em Português de Portugal.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from models import NOME_APP
from utils import formatar_data, lista_para_texto


class ErroExportacao(Exception):
    """Falha na exportação com mensagem adequada para mostrar ao utilizador."""


# Campo interno -> título da coluna exportada (a ordem define a ordem das colunas).
COLUNAS_EXPORTACAO: dict[str, str] = {
    "nome": "Nome",
    "cargo": "Cargo",
    "especialidades": "Especialidades",
    "localizacao": "Localização",
    "concelho": "Concelho",
    "distrito": "Distrito",
    "anos_experiencia": "Anos de experiência",
    "score": "Pontuação (%)",
    "nivel_confianca": "Confiança (%)",
    "recomendacao": "Recomendação da IA",
    "disponibilidade_classificacao": "Disponibilidade",
    "disponibilidade_imediata": "Disponibilidade imediata",
    "disponibilidade_urgencias": "Disponível para urgências",
    "disponibilidade_deslocacoes": "Disponível para deslocações",
    "certificacao_fgas": "Certificação F-Gas",
    "certificacoes": "Certificações",
    "competencias": "Competências",
    "carta_conducao": "Carta de condução",
    "viatura_propria": "Viatura própria",
    "telefone": "Telefone",
    "email": "Email",
    "estado": "Estado",
    "responsavel": "Responsável",
    "data_primeiro_contacto": "Primeiro contacto",
    "data_ultimo_contacto": "Último contacto",
    "proxima_acao": "Próxima ação",
    "data_proxima_acao": "Data da próxima ação",
    "expectativa_salarial": "Expectativa salarial",
    "disponibilidade_inicio": "Disponibilidade de início",
    "tipo_contrato_pretendido": "Tipo de contrato pretendido",
    "resumo": "Resumo profissional",
    "fonte": "Fonte",
    "url_perfil": "Link do perfil",
    "url_fonte": "Link da fonte",
    "data_recolha": "Data de recolha",
}

_COLUNAS_DATA = {"data_primeiro_contacto", "data_ultimo_contacto", "data_proxima_acao", "data_recolha"}
_COLUNAS_LISTA = {"especialidades", "certificacoes", "competencias"}


def preparar_exportacao(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona, formata e renomeia as colunas para exportação."""
    colunas = [c for c in COLUNAS_EXPORTACAO if c in df.columns]
    saida = df[colunas].copy()
    for coluna in colunas:
        if coluna in _COLUNAS_LISTA:
            saida[coluna] = saida[coluna].apply(lista_para_texto)
        elif coluna in _COLUNAS_DATA:
            saida[coluna] = saida[coluna].apply(formatar_data)
    saida = saida.where(saida.notna(), "")
    return saida.rename(columns=COLUNAS_EXPORTACAO)


def _proteger_formulas(valor):
    """Evita que texto externo seja interpretado como fórmula no Excel (CSV injection)."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor
    return valor


def exportar_csv(df: pd.DataFrame) -> bytes:
    """CSV com separador ';' e BOM UTF-8 (abre corretamente no Excel em português)."""
    try:
        saida = preparar_exportacao(df).map(_proteger_formulas)
        return saida.to_csv(index=False, sep=";").encode("utf-8-sig")
    except Exception as exc:
        raise ErroExportacao("Não foi possível gerar o ficheiro CSV.") from exc


def exportar_excel(df: pd.DataFrame) -> bytes:
    """Folha de cálculo XLSX com cabeçalho formatado, filtros e larguras ajustadas."""
    try:
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        saida = preparar_exportacao(df).map(_proteger_formulas)
        memoria = io.BytesIO()
        with pd.ExcelWriter(memoria, engine="openpyxl") as escritor:
            saida.to_excel(escritor, index=False, sheet_name="Candidatos")
            folha = escritor.sheets["Candidatos"]
            for celula in folha[1]:
                celula.font = Font(bold=True, color="FFFFFF")
                celula.fill = PatternFill("solid", fgColor="0B2545")
                celula.alignment = Alignment(vertical="center", wrap_text=True)
            for indice, coluna in enumerate(saida.columns, start=1):
                maior = max([len(str(coluna))] + [len(str(v)) for v in saida[coluna].head(200)])
                folha.column_dimensions[get_column_letter(indice)].width = max(12, min(maior + 2, 60))
            folha.freeze_panes = "B2"
            folha.auto_filter.ref = folha.dimensions
        return memoria.getvalue()
    except Exception as exc:
        raise ErroExportacao("Não foi possível gerar o ficheiro Excel.") from exc


def _latin1(valor, limite: int = 0) -> str:
    """As fontes base do PDF só suportam Latin-1; substitui o que não for representável."""
    texto = "" if valor is None else str(valor)
    for origem, destino in (("—", "-"), ("–", "-"), ("…", "..."), ("“", '"'), ("”", '"'), ("’", "'"), ("•", "-")):
        texto = texto.replace(origem, destino)
    if limite and len(texto) > limite:
        texto = texto[: limite - 3] + "..."
    return texto.encode("latin-1", "replace").decode("latin-1")


def exportar_pdf(df: pd.DataFrame) -> bytes:
    """Listagem resumida em PDF (A4 horizontal)."""
    try:
        from fpdf import FPDF

        colunas = [
            ("nome", "Nome", 52, 34), ("especialidades", "Especialidade", 62, 44),
            ("localizacao", "Localização", 38, 26), ("score", "Pontuação", 18, 5),
            ("disponibilidade_classificacao", "Disponib.", 24, 16),
            ("certificacao_fgas", "F-Gas", 20, 14), ("estado", "Estado", 32, 22),
            ("contacto", "Contacto", 35, 26),
        ]
        dados = df.copy()
        dados["especialidades"] = dados["especialidades"].apply(lista_para_texto)
        dados["contacto"] = dados.apply(lambda l: l.get("telefone") or l.get("email") or "", axis=1)

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(11, 37, 69)
        pdf.cell(0, 9, _latin1(f"{NOME_APP} - Candidatos"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, _latin1(f"Exportado em {formatar_data(date.today())} - {len(dados)} candidatos. "
                               "Dados para uso interno de recrutamento (RGPD)."),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        def cabecalho():
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(11, 37, 69)
            pdf.set_text_color(255, 255, 255)
            for _, titulo, largura, _ in colunas:
                pdf.cell(largura, 7, _latin1(titulo), border=0, fill=True)
            pdf.ln()
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(30, 30, 30)

        cabecalho()
        for numero, (_, linha) in enumerate(dados.iterrows()):
            if pdf.get_y() > 190:
                pdf.add_page()
                cabecalho()
            pdf.set_fill_color(243, 246, 250)
            for campo, _, largura, limite in colunas:
                valor = linha.get(campo)
                valor = "" if valor is None or (isinstance(valor, float) and pd.isna(valor)) else valor
                pdf.cell(largura, 6, _latin1(valor, limite), border=0, fill=(numero % 2 == 0))
            pdf.ln()
        return bytes(pdf.output())
    except Exception as exc:
        raise ErroExportacao("Não foi possível gerar o ficheiro PDF.") from exc
