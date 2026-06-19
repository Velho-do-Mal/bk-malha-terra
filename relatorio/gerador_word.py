# -*- coding: utf-8 -*-
"""
relatorio/gerador_word.py  —  BK Malha de Terra v2.1
======================================================

Gera o relatório técnico completo .docx para aprovação em concessionária.

Estrutura do documento:
    Capa
    Controle de revisões
    1. Objetivo e Normas Aplicáveis
    2. Dados do Sistema Elétrico
       2.1  Configuração geral da SE
       2.2  Dados dos transformadores
       2.3  Impedâncias de sequência por barra
       2.4  Correntes de curto-circuito por barra
    3. Sistema de Proteção e Tempo de Eliminação
       3.1  Relés cadastrados
       3.2  Justificativa do tc adotado
    4. Metodologia (com equações OMML e explicações)
       4.1  Solo — Wenner e estratificação
       4.2  Corrente de malha IG
       4.3  Dimensionamento do condutor
       4.4  Tensões admissíveis pelo corpo humano
       4.5  Resistência da malha — Sverak e Schwarz
       4.6  Tensões de malha (Em) e de passo (Es)
       4.7  Critérios de verificação
       4.8  Considerações construtivas
    5. Dados de Entrada
       5.1  Medições Wenner
       5.2  Geometria
       5.3  Brita e hastes
       5.4  Dados elétricos do curto
    6. Memorial de Cálculo (passo a passo com valores reais)
       6.1  Estratificação do solo
       6.2  Corrente de malha
       6.3  Dimensionamento do condutor
       6.4  Tensões admissíveis
       6.5  Resistência da malha
       6.6  Fatores geométricos e tensões Em / Es
    7. Resultados e Verificação
       7.1  Tabela consolidada
       7.2  Geometria final adotada
       7.3  Comparação de tensões (figuras)
    8. Conclusão
    9. Referências Bibliográficas

Equações: marcadores [[EQ:nome]] → equações OMML nativas do Word.
Memorial de cálculo: texto com valores reais substituídos nas fórmulas.
"""

from __future__ import annotations

import io
import math
import re
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
from docx import Document
from docx.enum.table import WD_ALIGN_TEXT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from data.models import Projeto

# Importar textos e equações existentes
from relatorio.equacoes import EQUACOES_OMML
from relatorio.textos import (
    CONCLUSAO_ATENDE, CONCLUSAO_NAO_ATENDE,
    METODOLOGIA_CONDUTOR, METODOLOGIA_CORRENTE,
    METODOLOGIA_DETALHES_PROJETO, METODOLOGIA_EM_ES, METODOLOGIA_INTRO,
    METODOLOGIA_RG, METODOLOGIA_SOLO, METODOLOGIA_TENSOES_ADM,
    OBJETIVO_TEMPLATE, REFERENCIAS,
)

# ── Paleta de cores BK ────────────────────────────────────────────────────────
COR_AZUL_BK      = RGBColor(0x1F, 0x4E, 0x79)   # Azul escuro
COR_AZUL_MEDIO   = RGBColor(0x2E, 0x74, 0xB5)   # Azul médio
COR_AZUL_CLARO   = RGBColor(0xBD, 0xD7, 0xEE)   # Azul claro (fundo cabeçalho)
COR_VERDE_BK     = RGBColor(0x37, 0x86, 0x10)   # Verde
COR_VERMELHO     = RGBColor(0xC0, 0x39, 0x2B)   # Vermelho
COR_CINZA_ESCURO = RGBColor(0x40, 0x40, 0x40)   # Texto escuro
HEX_AZUL_TAB    = "BDD7EE"   # Fundo cabeçalho de tabela
HEX_CINZA_ALT   = "F2F2F2"   # Fundo linha alternada
HEX_VERDE_OK    = "E2EFDA"   # Fundo célula verde (aprovado)
HEX_VERMELHO_NOK = "FCE4D6"  # Fundo célula vermelho (reprovado)
HEX_AMARELO_ADV = "FFEB9C"   # Fundo célula amarelo (atenção)

# Regex marcadores de equação
RE_EQUACAO = re.compile(r"\[\[EQ:([a-zA-Z0-9_]+)\]\]")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DO DOCUMENTO
# ══════════════════════════════════════════════════════════════════════════════

def _config_pagina(doc: Document, projeto: Projeto):
    """A4, margens, cabeçalho e rodapé com identificação do projeto."""
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width  = Cm(21.0)
    section.top_margin    = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin   = Cm(3.0)
    section.right_margin  = Cm(2.0)

    # Cabeçalho
    header = section.header
    hdr_tab = header.add_table(1, 2, width=Cm(16))
    hdr_tab.style = "Table Grid"
    hdr_tab.allow_autofit = False
    # Coluna esquerda: nome do projeto
    c_esq = hdr_tab.rows[0].cells[0]
    c_esq.width = Cm(11)
    p_esq = c_esq.paragraphs[0]
    p_esq.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p_esq.add_run(f"BK Engenharia  ·  Malha de Aterramento  ·  {projeto.numero_projeto} R{projeto.revisao}")
    run.font.size = Pt(8)
    run.font.color.rgb = COR_AZUL_BK
    run.italic = True
    # Coluna direita: logo texto
    c_dir = hdr_tab.rows[0].cells[1]
    c_dir.width = Cm(5)
    p_dir = c_dir.paragraphs[0]
    p_dir.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run2 = p_dir.add_run("IEEE Std 80-2013  ·  NBR 15751")
    run2.font.size = Pt(8)
    run2.font.color.rgb = COR_AZUL_MEDIO
    # Borda inferior
    for cell in hdr_tab.rows[0].cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        bdr = OxmlElement("w:tcBorders")
        bot = OxmlElement("w:bottom")
        bot.set(qn("w:val"), "single")
        bot.set(qn("w:sz"), "4")
        bot.set(qn("w:color"), "1F4E79")
        bdr.append(bot)
        tc_pr.append(bdr)

    # Rodapé
    footer = section.footer
    p_rod = footer.paragraphs[0]
    p_rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_r = p_rod.add_run(f"{projeto.cliente}  ·  {projeto.nome_projeto}  ·  Pág. ")
    run_r.font.size = Pt(8)
    run_r.font.color.rgb = COR_CINZA_ESCURO
    _add_page_number(p_rod)
    run_r2 = p_rod.add_run(f"  ·  {date.today().strftime('%d/%m/%Y')}")
    run_r2.font.size = Pt(8)
    run_r2.font.color.rgb = COR_CINZA_ESCURO


def _config_estilos(doc: Document):
    """Configura fonte, tamanho e cor dos estilos de heading."""
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)

    for level, size, bold in [(1, 16, True), (2, 13, True), (3, 11, True)]:
        h = doc.styles[f"Heading {level}"]
        h.font.name = "Calibri"
        h.font.size = Pt(size)
        h.font.bold = bold
        h.font.color.rgb = COR_AZUL_BK
        h.paragraph_format.space_before = Pt(12 if level == 1 else 6)
        h.paragraph_format.space_after  = Pt(6)


def _add_page_number(paragraph):
    """Insere campo PAGE no parágrafo."""
    run = paragraph.add_run()
    for tag, text in [("begin", ""), ("instrText", "PAGE"), ("end", "")]:
        el = OxmlElement("w:fldChar" if tag != "instrText" else "w:instrText")
        if tag == "instrText":
            el.text = text
        else:
            el.set(qn("w:fldCharType"), tag)
        run._r.append(el)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS DE TABELA E TEXTO
# ══════════════════════════════════════════════════════════════════════════════

def _cell_shade(cell, hex_color: str):
    tcp = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcp.append(shd)


def _cell_text(cell, text: str, bold=False, size_pt=11,
               color: Optional[RGBColor] = None,
               align=WD_ALIGN_PARAGRAPH.LEFT):
    par = cell.paragraphs[0]
    par.alignment = align
    par.paragraph_format.space_after = Pt(2)
    run = par.add_run(str(text))
    run.font.name = "Calibri"
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color


def _tabela_2col(doc: Document, dados: list[tuple[str, str]],
                 largura_col1_cm=7.5, largura_col2_cm=8.5):
    """Tabela 2 colunas: parâmetro (negrito) | valor."""
    tab = doc.add_table(rows=len(dados), cols=2)
    tab.style = "Table Grid"
    tab.allow_autofit = False
    tab.columns[0].width = Cm(largura_col1_cm)
    tab.columns[1].width = Cm(largura_col2_cm)
    for i, (label, valor) in enumerate(dados):
        c1, c2 = tab.rows[i].cells
        _cell_text(c1, label, bold=True, size_pt=10)
        _cell_text(c2, valor, size_pt=10)
        _cell_shade(c1, HEX_CINZA_ALT if i % 2 == 0 else "FFFFFF")
    return tab


def _tabela_cabecalho(doc: Document, headers: list[str],
                      dados: list[list[str]],
                      larguras_cm: Optional[list[float]] = None,
                      hex_header=HEX_AZUL_TAB):
    """Tabela com cabeçalho colorido e linhas alternadas."""
    n_cols = len(headers)
    tab = doc.add_table(rows=1 + len(dados), cols=n_cols)
    tab.style = "Table Grid"
    tab.allow_autofit = False

    if larguras_cm:
        for j, larg in enumerate(larguras_cm):
            tab.columns[j].width = Cm(larg)

    # Cabeçalho
    hdr_row = tab.rows[0]
    for j, h in enumerate(headers):
        cell = hdr_row.cells[j]
        _cell_shade(cell, hex_header)
        _cell_text(cell, h, bold=True, size_pt=10,
                   color=COR_AZUL_BK, align=WD_ALIGN_PARAGRAPH.CENTER)

    # Dados
    for i, linha in enumerate(dados):
        row = tab.rows[i + 1]
        hex_fundo = HEX_CINZA_ALT if i % 2 == 0 else "FFFFFF"
        for j, val in enumerate(linha):
            cell = row.cells[j]
            _cell_shade(cell, hex_fundo)
            _cell_text(cell, val, size_pt=10)

    return tab


def _par_destaque(doc: Document, texto: str,
                  hex_fundo=HEX_AMARELO_ADV, italic=False):
    """Parágrafo destacado (caixa colorida)."""
    tab = doc.add_table(1, 1)
    tab.style = "Table Grid"
    cell = tab.rows[0].cells[0]
    _cell_shade(cell, hex_fundo)
    par = cell.paragraphs[0]
    par.paragraph_format.space_before = Pt(2)
    par.paragraph_format.space_after  = Pt(2)
    run = par.add_run(texto)
    run.font.name = "Calibri"
    run.font.size = Pt(10)
    run.italic = italic


def _par(doc: Document, texto: str, size_pt=11, bold=False,
         italic=False, color: Optional[RGBColor] = None,
         align=WD_ALIGN_PARAGRAPH.LEFT) -> None:
    par = doc.add_paragraph()
    par.alignment = align
    run = par.add_run(texto)
    run.font.name = "Calibri"
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color


def _adiciona_imagem(doc: Document, image_bytes: bytes, legenda: str, largura_cm=15.0):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run()
    try:
        run.add_picture(io.BytesIO(image_bytes), width=Cm(largura_cm))
    except Exception as e:
        par.add_run(f"[Erro ao inserir figura: {e}]")
    pleg = doc.add_paragraph()
    pleg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = pleg.add_run(legenda)
    run2.italic = True
    run2.font.size = Pt(9)
    run2.font.color.rgb = COR_CINZA_ESCURO


def _aviso_figura(doc: Document, legenda: str):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run(f"[ Figura ausente — execute o cálculo nesta sessão: {legenda} ]")
    run.italic = True
    run.font.color.rgb = COR_VERMELHO
    run.font.size = Pt(10)


# ── Equações OMML ─────────────────────────────────────────────────────────────

def _insere_equacao(doc: Document, ident: str):
    if ident not in EQUACOES_OMML:
        _par(doc, f"[Equação '{ident}' não disponível]",
             italic=True, color=COR_VERMELHO, align=WD_ALIGN_PARAGRAPH.CENTER)
        return
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par._p.append(parse_xml(EQUACOES_OMML[ident].strip()))


def _renderiza_bloco(doc: Document, texto: str):
    """Renderiza bloco de metodologia: subtítulos, equações e texto em negrito."""
    for bloco in texto.strip().split("\n\n"):
        linhas = [l.strip() for l in bloco.strip().split("\n") if l.strip()]
        if not linhas:
            continue
        primeira = linhas[0]
        txt = " ".join(linhas)

        if primeira.startswith("**") and primeira.endswith("**") and len(linhas) == 1:
            doc.add_heading(primeira.strip("*").strip(), level=3)
            continue
        if primeira.startswith("**") and primeira.endswith("**") and len(linhas) > 1:
            doc.add_heading(primeira.strip("*").strip(), level=3)
            txt = " ".join(linhas[1:])

        m = RE_EQUACAO.fullmatch(txt)
        if m:
            _insere_equacao(doc, m.group(1))
            continue

        partes = RE_EQUACAO.split(txt)
        for i, seg in enumerate(partes):
            if i % 2 == 0:
                if seg.strip():
                    _par_com_negrito(doc, seg.strip())
            else:
                _insere_equacao(doc, seg)


def _par_com_negrito(doc: Document, texto: str):
    par = doc.add_paragraph()
    for idx, parte in enumerate(texto.split("**")):
        run = par.add_run(parte)
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        if idx % 2 == 1:
            run.font.bold = True


# ══════════════════════════════════════════════════════════════════════════════
# CAPA
# ══════════════════════════════════════════════════════════════════════════════

def _capa(doc: Document, projeto: Projeto, logo_path: Optional[str]):
    if logo_path and Path(logo_path).exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        try:
            p.add_run().add_picture(logo_path, width=Cm(5))
        except Exception:
            pass

    for _ in range(2):
        doc.add_paragraph()

    # Linha decorativa superior
    tab_linha = doc.add_table(1, 1)
    tab_linha.style = "Table Grid"
    _cell_shade(tab_linha.rows[0].cells[0], "1F4E79")
    tab_linha.rows[0].cells[0].paragraphs[0].add_run("").font.size = Pt(4)
    doc.add_paragraph()

    # Título principal
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("MEMÓRIA DE CÁLCULO")
    run.font.name = "Calibri"
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = COR_AZUL_BK

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run("MALHA DE ATERRAMENTO DE SUBESTAÇÃO")
    run2.font.name = "Calibri"
    run2.font.size = Pt(18)
    run2.font.bold = True
    run2.font.color.rgb = COR_AZUL_MEDIO

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run3 = p3.add_run("IEEE Std 80-2013  ·  ABNT NBR 15751:2013  ·  NBR 7117:2020")
    run3.font.name = "Calibri"
    run3.font.size = Pt(11)
    run3.italic = True
    run3.font.color.rgb = COR_AZUL_MEDIO

    for _ in range(2):
        doc.add_paragraph()

    # Caixa de identificação
    tab = doc.add_table(rows=8, cols=2)
    tab.alignment = WD_TABLE_ALIGNMENT.CENTER
    tab.style = "Table Grid"
    tab.allow_autofit = False
    tab.columns[0].width = Cm(5)
    tab.columns[1].width = Cm(11)

    dados_capa = [
        ("Cliente",              projeto.cliente),
        ("Subestação / Projeto", projeto.nome_projeto),
        ("Concessionária",       projeto.concessionaria or "—"),
        ("Nº do Projeto",        projeto.numero_projeto),
        ("Revisão",              f"R{projeto.revisao}"),
        ("Data do cálculo",      projeto.data_calculo.strftime("%d/%m/%Y")),
        ("Responsável técnico",  projeto.responsavel_tecnico or "—"),
        ("CREA",                 projeto.crea_responsavel or "—"),
    ]
    for i, (label, val) in enumerate(dados_capa):
        c1, c2 = tab.rows[i].cells
        _cell_shade(c1, HEX_AZUL_TAB)
        _cell_text(c1, label, bold=True, size_pt=10, color=COR_AZUL_BK)
        _cell_text(c2, val, size_pt=11, bold=(i in (1, 3)))

    doc.add_paragraph()
    # Linha decorativa inferior
    tab_linha2 = doc.add_table(1, 1)
    tab_linha2.style = "Table Grid"
    _cell_shade(tab_linha2.rows[0].cells[0], "1F4E79")
    tab_linha2.rows[0].cells[0].paragraphs[0].add_run("").font.size = Pt(4)

    doc.add_page_break()


# ── Controle de revisões ──────────────────────────────────────────────────────

def _revisoes(doc: Document, projeto: Projeto):
    doc.add_heading("Controle de Revisões", level=1)
    headers = ["Rev.", "Data", "Descrição", "Elaborado", "Verificado", "Aprovado"]
    larguras = [1.5, 2.5, 5.5, 2.0, 2.0, 2.0]
    dados = [
        [f"R{projeto.revisao}",
         projeto.data_calculo.strftime("%d/%m/%Y"),
         "Emissão inicial",
         projeto.responsavel_tecnico or "—", "—", "—"],
    ]
    _tabela_cabecalho(doc, headers, dados, larguras)
    doc.add_paragraph()
    doc.add_page_break()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 1: OBJETIVO
# ══════════════════════════════════════════════════════════════════════════════

def _sec_objetivo(doc: Document, projeto: Projeto):
    doc.add_heading("1. Objetivo e Normas Aplicáveis", level=1)
    texto = OBJETIVO_TEMPLATE.format(
        cliente=projeto.cliente,
        nome_projeto=projeto.nome_projeto,
        numero_projeto=projeto.numero_projeto,
        revisao=projeto.revisao,
        concessionaria=projeto.concessionaria or "(a definir)",
        responsavel=projeto.responsavel_tecnico or "(a definir)",
        crea_responsavel=projeto.crea_responsavel or "—",
        data_calculo=projeto.data_calculo.strftime("%d/%m/%Y"),
    )
    for bloco in texto.strip().split("\n\n"):
        _par_com_negrito(doc, " ".join(bloco.strip().split("\n")))


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 2: DADOS DO SISTEMA ELÉTRICO
# ══════════════════════════════════════════════════════════════════════════════

def _sec_sistema_eletrico(doc: Document, projeto: Projeto):
    doc.add_heading("2. Dados do Sistema Elétrico", level=1)

    _par(doc,
         "Os dados a seguir descrevem a configuração da subestação e os resultados "
         "do estudo de curto-circuito que originaram os parâmetros elétricos utilizados "
         "no dimensionamento da malha de aterramento.")

    # 2.1 Configuração geral
    doc.add_heading("2.1. Configuração geral da subestação", level=2)
    de = projeto.dados_entrada
    if de:
        dados_se = [
            ("Concessionária / área", projeto.concessionaria or "—"),
            ("Tensão AT nominal", f"{_fmt_kv(de)} — Barra AT"),
            ("Corrente simétrica de falta 3I₀", f"{float(de.i_falta_3i0_ka):.3f} kA"),
            ("Fator de divisão de corrente Sf", f"{float(de.sf_div_corrente):.2f}"),
            ("Relação X/R adotada", f"{float(de.xr_ratio or 10):.1f}"),
            ("Tempo de eliminação da falta tc", f"{float(de.tempo_eliminacao_s):.3f} s"),
        ]
        _tabela_2col(doc, dados_se)
    else:
        _par(doc, "[INSERIR DADOS DE ENTRADA — execute a aba 4 antes de gerar o relatório]",
             italic=True, color=COR_VERMELHO)

    doc.add_paragraph()

    # 2.2 Transformadores
    doc.add_heading("2.2. Dados dos transformadores", level=2)
    trafos = getattr(projeto, "transformadores", [])
    if trafos:
        headers = ["Tag", "Potência [MVA]", "Tensão AT [kV]", "Tensão MT [kV]",
                   "Grupo", "Zcc [%]", "In AT [A]", "In MT [A]"]
        dados_tab = [
            [
                t.tag or "—",
                f"{float(t.potencia_mva):.2f}" if t.potencia_mva else "—",
                f"{float(t.tensao_at_kv):.3f}" if t.tensao_at_kv else "—",
                f"{float(t.tensao_mt_kv):.3f}" if t.tensao_mt_kv else "—",
                t.grupo_ligacao or "—",
                f"{float(t.zcc_pct):.3f}" if t.zcc_pct else "—",
                f"{float(t.corrente_nom_at_a):.1f}" if t.corrente_nom_at_a else "—",
                f"{float(t.corrente_nom_mt_a):.1f}" if t.corrente_nom_mt_a else "—",
            ]
            for t in trafos
        ]
        _tabela_cabecalho(doc, headers, dados_tab,
                          [1.5, 2.0, 2.0, 2.0, 1.8, 1.5, 2.0, 2.0])
    else:
        _par(doc, "[INSERIR DADOS DOS TRANSFORMADORES — aba 5 → Transformadores]",
             italic=True, color=COR_VERMELHO)
    doc.add_paragraph()

    # 2.3 Impedâncias por barra
    doc.add_heading("2.3. Impedâncias de sequência por barra", level=2)
    _par(doc,
         "As impedâncias de sequência positiva (Z1), negativa (Z2) e zero (Z0) "
         "representam a impedância equivalente do sistema elétrico vista do ponto de falta "
         "em cada barra. Valores extraídos do estudo de curto-circuito.", size_pt=10)
    doc.add_paragraph()

    barras = getattr(projeto, "barras", [])
    if barras:
        headers = ["Barra", "Tensão [kV]", "Z1 (R+jX) [Ω]", "|Z1| [Ω]",
                   "Z0 (R+jX) [Ω]", "|Z0| [Ω]", "X/R"]
        dados_tab = []
        for b in barras:
            z1 = _fmt_z(b.z1_r_ohm, b.z1_x_ohm)
            z1m = f"{math.sqrt(float(b.z1_r_ohm)**2 + float(b.z1_x_ohm)**2):.4f}" \
                  if b.z1_r_ohm and b.z1_x_ohm else "—"
            z0 = _fmt_z(b.z0_r_ohm, b.z0_x_ohm)
            z0m = f"{math.sqrt(float(b.z0_r_ohm)**2 + float(b.z0_x_ohm)**2):.4f}" \
                  if b.z0_r_ohm and b.z0_x_ohm else "—"
            marca = " ★" if b.e_barra_projeto else ""
            dados_tab.append([
                f"{b.nome}{marca}",
                f"{float(b.tensao_kv):.3f}",
                z1, z1m, z0, z0m,
                f"{float(b.xr_ratio):.2f}" if b.xr_ratio else "—",
            ])
        _tabela_cabecalho(doc, headers, dados_tab,
                          [3.5, 1.8, 3.0, 1.6, 3.0, 1.6, 1.2])
        _par(doc, "★ Barra adotada como ponto de falta para o cálculo da malha de aterramento.",
             size_pt=9, italic=True)
    else:
        _par(doc, "[INSERIR IMPEDÂNCIAS POR BARRA — aba 5 → Barras e Curto-Circuito]",
             italic=True, color=COR_VERMELHO)
    doc.add_paragraph()

    # 2.4 Correntes de curto-circuito
    doc.add_heading("2.4. Correntes de curto-circuito por barra", level=2)
    _par(doc,
         "Valores de pico e eficazes das correntes de curto-circuito "
         "para os diferentes tipos de falta.", size_pt=10)
    doc.add_paragraph()

    if barras:
        headers = ["Barra", "Tensão [kV]", "Icc 3F [kA]", "Icc 2F [kA]",
                   "Icc 1F = 3I₀ [kA]", "Ip [kA]", "X/R", "κ"]
        dados_tab = []
        for b in barras:
            xr = float(b.xr_ratio) if b.xr_ratio else 10.0
            kappa = 1.02 + 0.98 * math.exp(-3.0 / xr) if xr > 0 else 1.41
            marca = " ★" if b.e_barra_projeto else ""
            dados_tab.append([
                f"{b.nome}{marca}",
                f"{float(b.tensao_kv):.3f}",
                f"{float(b.icc_3f_ka):.4f}" if b.icc_3f_ka else "—",
                f"{float(b.icc_2f_ka):.4f}" if b.icc_2f_ka else "—",
                f"{float(b.icc_1f_ka):.4f}" if b.icc_1f_ka else "—",
                f"{float(b.ip_pico_ka):.4f}" if b.ip_pico_ka else "—",
                f"{xr:.2f}",
                f"{kappa:.4f}",
            ])
        tab = _tabela_cabecalho(doc, headers, dados_tab,
                                 [3.0, 1.6, 1.8, 1.8, 2.2, 1.8, 1.2, 1.2])
        # Destaca coluna Icc1F (3I₀)
        _par(doc, "★ Icc 1F = corrente de falta fase-terra (3I₀) — valor adotado no dimensionamento da malha.",
             size_pt=9, italic=True)
    else:
        _par(doc, "[INSERIR CORRENTES DE FALTA — aba 5 → Barras e Curto-Circuito]",
             italic=True, color=COR_VERMELHO)

    doc.add_paragraph()
    doc.add_page_break()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 3: SISTEMA DE PROTEÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def _sec_protecao(doc: Document, projeto: Projeto):
    doc.add_heading("3. Sistema de Proteção e Tempo de Eliminação", level=1)

    _par(doc,
         "O tempo de eliminação da falta (tc) é um dos parâmetros mais críticos "
         "do estudo de malha de aterramento, pois determina tanto a seção mínima "
         "do condutor (Sverak) quanto as tensões admissíveis pelo corpo humano (Dalziel). "
         "Esta seção documenta os relés instalados na SE e a justificativa do tc adotado.")

    doc.add_heading("3.1. Relés de proteção cadastrados", level=2)

    reles = getattr(projeto, "reles", [])
    if reles:
        headers = ["Barra", "Relé / Função", "Fabricante", "Modelo",
                   "Funções ANSI", "Tipo", "t relé [s]", "t DJ [s]", "tc [s]", "Adotado"]
        dados_tab = [
            [
                r.barra_nome or "—",
                r.nome,
                r.fabricante or "—",
                r.modelo or "—",
                r.funcoes_ansi or "—",
                r.tipo_protecao or "—",
                f"{float(r.tempo_rele_s):.4f}" if r.tempo_rele_s else "—",
                f"{float(r.tempo_abertura_dj_s):.4f}",
                f"{float(r.tempo_total_tc_s):.4f}" if r.tempo_total_tc_s else "—",
                "✅" if r.e_tc_adotado else "",
            ]
            for r in reles
        ]
        _tabela_cabecalho(doc, headers, dados_tab,
                          [2.0, 3.0, 1.5, 1.5, 1.8, 1.5, 1.5, 1.2, 1.2, 1.2])
    else:
        _par(doc, "[INSERIR DADOS DOS RELÉS — aba 5 → Relés e Proteção]",
             italic=True, color=COR_VERMELHO)

    doc.add_paragraph()
    doc.add_heading("3.2. Justificativa do tc adotado", level=2)

    de = projeto.dados_entrada
    tc_adotado = float(de.tempo_eliminacao_s) if de else None

    rele_adotado = next((r for r in reles if r.e_tc_adotado), None) if reles else None

    if rele_adotado and tc_adotado:
        texto_tc = (
            f"O tempo de eliminação adotado no estudo de malha é tc = {tc_adotado:.3f} s, "
            f"correspondente à atuação da proteção {rele_adotado.tipo_protecao or 'primária'} "
            f"({rele_adotado.nome}, funções {rele_adotado.funcoes_ansi or '—'}), "
            f"composto por: tempo de atuação do relé = {float(rele_adotado.tempo_rele_s):.4f} s + "
            f"tempo de abertura do disjuntor = {float(rele_adotado.tempo_abertura_dj_s):.4f} s.\n\n"
            f"Conforme IEEE Std 80-2013 §15.1, o tc deve ser o maior tempo possível "
            f"de escoamento da corrente de falta — ou seja, o tempo de atuação da "
            f"proteção de backup (reserva) quando a proteção primária falha. "
            f"O valor adotado é conservador e atende a esse critério."
        )
    elif tc_adotado:
        texto_tc = (
            f"O tempo de eliminação adotado é tc = {tc_adotado:.3f} s, "
            f"conforme definição do sistema de proteção da SE. "
            f"[COMPLEMENTAR: identificar o relé e nível de proteção correspondente.]"
        )
    else:
        texto_tc = "[INSERIR: justificativa do tc adotado — aba 4 e aba 5.]"

    _par_com_negrito(doc, texto_tc)

    if tc_adotado:
        _par_destaque(doc,
                      f"tc adotado no estudo de malha: {tc_adotado:.3f} s",
                      hex_fundo=HEX_AMARELO_ADV)

    doc.add_paragraph()
    doc.add_page_break()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 4: METODOLOGIA
# ══════════════════════════════════════════════════════════════════════════════

def _sec_metodologia(doc: Document):
    doc.add_heading("4. Metodologia", level=1)
    _par_com_negrito(doc, METODOLOGIA_INTRO)
    for bloco in [METODOLOGIA_SOLO, METODOLOGIA_CORRENTE, METODOLOGIA_CONDUTOR,
                  METODOLOGIA_TENSOES_ADM, METODOLOGIA_RG, METODOLOGIA_EM_ES,
                  METODOLOGIA_DETALHES_PROJETO]:
        _renderiza_bloco(doc, bloco)
    doc.add_page_break()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 5: DADOS DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def _sec_dados_entrada(doc: Document, projeto: Projeto):
    doc.add_heading("5. Dados de Entrada", level=1)
    de = projeto.dados_entrada
    if not de:
        _par(doc, "[DADOS DE ENTRADA NÃO DISPONÍVEIS]", italic=True, color=COR_VERMELHO)
        return

    # 5.1 Solo
    doc.add_heading("5.1. Medições de resistividade do solo (Wenner)", level=2)
    if projeto.medicoes_wenner:
        headers = ["Ponto", "Espaçamento a [m]", "Resistência R [Ω]", "ρ aparente [Ω·m]"]
        dados = [
            [str(m.ponto), f"{float(m.espacamento_m):.2f}",
             f"{float(m.resistencia_ohm):.4f}",
             f"{float(m.rho_aparente):.1f}" if m.rho_aparente else "—"]
            for m in projeto.medicoes_wenner
        ]
        _tabela_cabecalho(doc, headers, dados, [1.5, 3.5, 3.5, 3.5])
    else:
        _par(doc, "[MEDIÇÕES WENNER NÃO CADASTRADAS]", italic=True, color=COR_VERMELHO)
    doc.add_paragraph()

    # 5.2 Geometria
    doc.add_heading("5.2. Geometria da subestação e da malha", level=2)
    _tabela_2col(doc, [
        ("Largura W",                             f"{float(de.largura_m):.2f} m"),
        ("Comprimento L",                         f"{float(de.comprimento_m):.2f} m"),
        ("Área A = W × L",                        f"{float(de.largura_m)*float(de.comprimento_m):.1f} m²"),
        ("Profundidade da malha h",               f"{float(de.profundidade_malha_m):.2f} m"),
        ("Espaçamento da malha principal D",      f"{float(de.espac_malha_principal_m):.2f} m"),
        ("Espaçamento da malha de junção",        f"{float(de.espac_malha_juncao_m or 0):.2f} m"),
    ])
    doc.add_paragraph()

    # 5.3 Brita e hastes
    doc.add_heading("5.3. Brita superficial e hastes de aterramento", level=2)
    _tabela_2col(doc, [
        ("Espessura da camada de brita hs",       f"{float(de.brita_espessura_m):.3f} m"),
        ("Resistividade da brita ρs",             f"{float(de.brita_resistividade_ohm):.0f} Ω·m"),
        ("Comprimento das hastes Lr",             f"{float(de.haste_comprimento_m):.2f} m"),
        ("Diâmetro das hastes d",                 f"{float(de.haste_diametro_mm):.3f} mm"),
        ("Material do condutor",                  _label_material(de.condutor_material)),
        ("Bitola adotada do condutor",            f"{float(de.condutor_bitola_mm2 or 0):.0f} mm²"),
    ])
    doc.add_paragraph()

    # 5.4 Dados elétricos
    doc.add_heading("5.4. Dados elétricos do curto-circuito", level=2)
    _tabela_2col(doc, [
        ("Corrente simétrica de falta 3I₀",      f"{float(de.i_falta_3i0_ka):.3f} kA"),
        ("Tempo de eliminação da falta tc",       f"{float(de.tempo_eliminacao_s):.3f} s"),
        ("Fator de divisão de corrente Sf",       f"{float(de.sf_div_corrente):.2f}  "
                                                   "(Tabela 10 — IEEE 80-2013)"),
        ("Relação X/R no ponto de falta",         f"{float(de.xr_ratio or 10):.1f}"),
        ("Fator de crescimento Cp",               f"{float(de.cp_crescimento or 1):.2f}"),
        ("Peso da pessoa (Dalziel)",              f"{int(de.peso_pessoa_kg)} kg"),
    ])
    doc.add_paragraph()
    doc.add_page_break()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 6: MEMORIAL DE CÁLCULO (passo a passo com valores reais)
# ══════════════════════════════════════════════════════════════════════════════

def _sec_memorial(doc: Document, projeto: Projeto):
    """
    Memorial de cálculo com todas as equações e os valores numéricos reais
    substituídos, permitindo que qualquer engenheiro verifique cada passo.
    """
    doc.add_heading("6. Memorial de Cálculo", level=1)
    _par(doc,
         "Esta seção apresenta o desenvolvimento numérico completo, com os valores "
         "de projeto substituídos em cada equação. Os resultados podem ser verificados "
         "independentemente, conferindo rastreabilidade ao estudo.")

    de = projeto.dados_entrada
    res = projeto.resultado
    if not de or not res:
        _par(doc, "[EXECUTE O CÁLCULO NA ABA 5 ANTES DE GERAR O RELATÓRIO]",
             italic=True, color=COR_VERMELHO, size_pt=12)
        return

    # Extrai valores
    rho1      = float(res.rho1_ohm_m or 0)
    rho2      = float(res.rho2_ohm_m or 0)
    h1        = float(res.h1_m or 0)
    rho_eq    = float(res.rho_equivalente or 0)
    df        = float(res.df_decremento or 1)
    sf        = float(de.sf_div_corrente)
    cp        = float(de.cp_crescimento or 1)
    i3i0_a    = float(de.i_falta_3i0_ka) * 1000.0
    ig        = float(res.ig_corrente_malha_a or 0)
    tc        = float(de.tempo_eliminacao_s)
    xr        = float(de.xr_ratio or 10)
    bit_calc  = float(res.bitola_calculada_mm2 or 0)
    bit_adot  = float(res.bitola_adotada_mm2 or 0)
    cs        = float(res.cs_brita or 1)
    rho_s     = float(de.brita_resistividade_ohm)
    h_s       = float(de.brita_espessura_m)
    e_tq_adm  = float(res.etoque_admissivel_v or 0)
    e_ps_adm  = float(res.epasso_admissivel_v or 0)
    peso      = int(de.peso_pessoa_kg)
    k_dalz    = 0.116 if peso == 50 else 0.157
    rg_sv     = float(res.rg_sverak_ohm or 0)
    rg_sw     = float(res.rg_schwarz_ohm or 0)
    rg        = float(res.rg_adotado_ohm or 0)
    gpr       = float(res.gpr_v or 0)
    em        = float(res.em_tensao_malha_v or 0)
    es        = float(res.es_tensao_passo_v or 0)
    n_hastes  = int(res.num_hastes or 0)
    Lc        = float(res.comprimento_total_cabo_m or 0)
    W         = float(de.largura_m)
    L         = float(de.comprimento_m)
    A         = W * L
    h_m       = float(de.profundidade_malha_m)
    D         = float(de.espac_malha_principal_m)
    Lr        = float(de.haste_comprimento_m)
    d_mm      = float(de.haste_diametro_mm)

    # ── 6.1 Estratificação do solo ───────────────────────────────────────────
    doc.add_heading("6.1. Estratificação do solo (modelo de 2 camadas — Sunde)", level=2)
    _par(doc,
         "Ajuste por mínimos quadrados da função de Sunde aos dados de campo (Wenner). "
         "Parâmetros obtidos:")
    _tabela_2col(doc, [
        ("Resistividade da camada superior ρ₁", f"{rho1:.1f} Ω·m"),
        ("Resistividade da camada inferior ρ₂", f"{rho2:.1f} Ω·m"),
        ("Espessura da camada superior h₁",     f"{h1:.2f} m"),
        ("Resistividade equivalente ρ_eq (Sverak/Schwarz)", f"{rho_eq:.1f} Ω·m"),
    ])
    doc.add_paragraph()

    # ── 6.2 Fator de decremento Df ───────────────────────────────────────────
    doc.add_heading("6.2. Fator de decremento Df e corrente de malha IG", level=2)
    Ta = xr / (2 * math.pi * 60.0)  # constante de tempo DC (60 Hz)
    _par(doc, "Constante de tempo DC (IEEE 80 eq. 79):", bold=True)
    _bloco_calculo(doc, [
        "Ta = X / (ω × R) = (X/R) / (2π × f)",
        f"Ta = {xr:.1f} / (2π × 60) = {Ta:.6f} s",
    ])

    _par(doc, "Fator de decremento Df (IEEE 80 eq. 79):", bold=True)
    _bloco_calculo(doc, [
        "Df = √[ 1 + (Ta / tc) × (1 − e^(−2tc/Ta)) ]",
        f"Df = √[ 1 + ({Ta:.6f} / {tc:.3f}) × (1 − e^(−2×{tc:.3f}/{Ta:.6f})) ]",
        f"Df = {df:.4f}",
    ])

    _par(doc, "Corrente máxima de malha IG (IEEE 80 eq. 70):", bold=True)
    _bloco_calculo(doc, [
        "IG = Df × Sf × Cp × 3I₀",
        f"IG = {df:.4f} × {sf:.2f} × {cp:.2f} × {i3i0_a:,.0f} A",
        f"IG = {ig:,.0f} A  = {ig/1000:.3f} kA",
    ])
    doc.add_paragraph()

    # ── 6.3 Dimensionamento do condutor ──────────────────────────────────────
    doc.add_heading("6.3. Dimensionamento térmico do condutor (Sverak — IEEE 80 eq. 37)", level=2)
    mat_label = _label_material(de.condutor_material)
    # Constantes do material (cobre nu)
    TCAP, alpha_r, rho_r, K0, Tm = _const_material(de.condutor_material)
    Ta_amb = 40.0
    _par(doc, f"Material: {mat_label}", bold=True)
    _tabela_2col(doc, [
        ("TCAP (capacidade térmica)",           f"{TCAP:.3f} J/(cm³·°C)"),
        ("αr (coef. temp. resistividade)",      f"{alpha_r:.5f} °C⁻¹"),
        ("ρr (resistividade 20 °C)",            f"{rho_r:.3f} μΩ·cm"),
        ("K₀ = 1/αr − 20",                     f"{K0:.1f} °C"),
        ("Tm (temp. máx. admissível)",          f"{Tm:.0f} °C"),
        ("Ta (temperatura ambiente)",           f"{Ta_amb:.0f} °C"),
    ], largura_col1_cm=6.5, largura_col2_cm=9.5)
    doc.add_paragraph()

    Amm2 = ig * math.sqrt(tc / (TCAP * 1e4 * math.log((Tm + K0) / (Ta_amb + K0))
                                / (alpha_r * rho_r))) / 1e4
    _par(doc, "Seção mínima do condutor:", bold=True)
    _bloco_calculo(doc, [
        "A = I × √[ tc / (TCAP × ln((Tm + K₀) / (Ta + K₀)) / (αr × ρr)) ]",
        f"A = {ig:,.0f} × √[ {tc:.3f} / (TCAP × ln(({Tm:.0f} + {K0:.1f}) / ({Ta_amb:.0f} + {K0:.1f})) / (αr × ρr)) ]",
        f"A calculada = {bit_calc:.2f} mm²",
        f"A adotada   = {bit_adot:.0f} mm²  ({'✅ OK — bitola adotada ≥ calculada' if bit_adot >= bit_calc else '❌ ATENÇÃO — bitola adotada < calculada'})",
    ])
    doc.add_paragraph()

    # ── 6.4 Tensões admissíveis ───────────────────────────────────────────────
    doc.add_heading("6.4. Tensões admissíveis pelo corpo humano (Dalziel)", level=2)
    _par(doc, "Fator de redução da camada superficial Cs (IEEE 80 eq. 27):", bold=True)
    K_ref = (rho1 - rho_s) / (rho1 + rho_s) if (rho1 + rho_s) > 0 else 0
    _bloco_calculo(doc, [
        "Cs = 1 − [0,09 × (1 − ρs/ρ₁)] / (2hs + 0,09)",
        f"Cs = 1 − [0,09 × (1 − {rho_s:.0f}/{rho1:.1f})] / (2×{h_s:.3f} + 0,09)",
        f"Cs = {cs:.4f}",
    ])

    _par(doc, f"Corrente máxima admissível (Dalziel, {peso} kg):", bold=True)
    ib = k_dalz / math.sqrt(tc) if tc > 0 else 0
    _bloco_calculo(doc, [
        f"Ib = k / √tc  (k = {k_dalz:.3f} √A·s para {peso} kg)",
        f"Ib = {k_dalz:.3f} / √{tc:.3f} = {ib:.4f} A",
    ])

    _par(doc, "Tensão de toque admissível (IEEE 80 eq. 32):", bold=True)
    _bloco_calculo(doc, [
        "Etoque = (Rb + 1,5 × Cs × ρs) × Ib",
        f"Etoque = (1000 + 1,5 × {cs:.4f} × {rho_s:.0f}) × {ib:.4f}",
        f"Etoque = {e_tq_adm:.1f} V",
    ])

    _par(doc, "Tensão de passo admissível (IEEE 80 eq. 30):", bold=True)
    _bloco_calculo(doc, [
        "Epasso = (Rb + 6 × Cs × ρs) × Ib",
        f"Epasso = (1000 + 6 × {cs:.4f} × {rho_s:.0f}) × {ib:.4f}",
        f"Epasso = {e_ps_adm:.1f} V",
    ])
    doc.add_paragraph()

    # ── 6.5 Resistência da malha ─────────────────────────────────────────────
    doc.add_heading("6.5. Resistência da malha (Sverak e Schwarz)", level=2)

    nx  = int(math.ceil(L / D)) + 1
    ny  = int(math.ceil(W / D)) + 1
    Lc_cabos = nx * W + ny * L
    Lt  = Lc_cabos + Lr * n_hastes

    _par(doc, "Comprimento total dos condutores:", bold=True)
    _bloco_calculo(doc, [
        f"nx = ⌈L/D⌉ + 1 = ⌈{L}/{D}⌉ + 1 = {nx}",
        f"ny = ⌈W/D⌉ + 1 = ⌈{W}/{D}⌉ + 1 = {ny}",
        f"Lc (cabos) = nx×W + ny×L = {nx}×{W} + {ny}×{L} = {Lc_cabos:.1f} m",
        f"Lt = Lc + n×Lr = {Lc_cabos:.1f} + {n_hastes}×{Lr:.2f} = {Lt:.1f} m",
    ])

    _par(doc, "Rg por Sverak (IEEE 80 eq. 52):", bold=True)
    _bloco_calculo(doc, [
        "Rg = ρ × [ 1/Lt + (1/√(20A)) × (1 + 1/(1 + h√(20/A))) ]",
        f"Rg = {rho_eq:.1f} × [ 1/{Lt:.1f} + (1/√(20×{A:.1f})) × (1 + 1/(1 + {h_m:.2f}×√(20/{A:.1f}))) ]",
        f"Rg_Sverak = {rg_sv:.4f} Ω",
    ])

    _par(doc, "Rg por Schwarz (IEEE 80 §14.3 — adotado por ser mais preciso):", bold=True)
    _bloco_calculo(doc, [
        "R1 = ρ/(π·Lc) × [ ln(2Lc/a') + k1·Lc/√A − k2 ]    (cabos)",
        "R2 = ρ/(2π·n·Lr) × [ ln(8Lr/d) − 1 + 2k1·Lr·(√n−1)²/√A ]    (hastes)",
        "Rm = ρ/(π·Lc) × [ ln(2Lc/Lr) + k1·Lc/√A − k2 + 1 ]    (mútua)",
        "Rg = (R1·R2 − Rm²) / (R1 + R2 − 2·Rm)",
        f"Rg_Schwarz = {rg_sw:.4f} Ω",
        f"Rg adotado = {rg:.4f} Ω  (Schwarz)",
    ])
    doc.add_paragraph()

    # ── 6.6 Fatores geométricos e tensões Em / Es ────────────────────────────
    doc.add_heading("6.6. Fatores geométricos, tensões de malha (Em) e de passo (Es)", level=2)

    # n geométrico (estimativa simplificada)
    Lp  = 2 * (L + W)
    na  = 2 * Lc_cabos / Lp
    nb  = math.sqrt(Lp / (4 * math.sqrt(A)))
    n_g = na * nb

    _par(doc, "Fator geométrico n (IEEE 80 eq. 85):", bold=True)
    _bloco_calculo(doc, [
        "na = 2·Lc / Lp = 2·Lc / [2(L+W)]",
        f"na = 2×{Lc_cabos:.1f} / [2×({L}+{W})] = {na:.3f}",
        f"nb = √(Lp / [4√A]) = √({Lp:.1f} / [4√{A:.1f}]) = {nb:.3f}",
        f"n = na × nb = {na:.3f} × {nb:.3f} = {n_g:.3f}",
    ])

    Ki = 0.644 + 0.148 * n_g
    _par(doc, "Fator de irregularidade Ki (eq. 89):", bold=True)
    _bloco_calculo(doc, [
        "Ki = 0,644 + 0,148 × n",
        f"Ki = 0,644 + 0,148 × {n_g:.3f} = {Ki:.4f}",
    ])

    # Km estimativo (sem recompute completo — usa resultado armazenado)
    Lm_est = Lc_cabos + (1.55 + 1.22 * (Lr / math.sqrt(L**2 + W**2))) * n_hastes * Lr
    Ls_est = 0.75 * Lc_cabos + 0.85 * n_hastes * Lr
    Km_est = em * Lm_est / (rho_eq * Ki * ig) if (rho_eq * Ki * ig) > 0 else 0
    Ks_est = es * Ls_est / (rho_eq * Ki * ig) if (rho_eq * Ki * ig) > 0 else 0

    _par(doc, "Comprimentos efetivos (eqs. 88 e 93):", bold=True)
    _bloco_calculo(doc, [
        f"Lm = Lc + (1,55 + 1,22·Lr/√(L²+W²)) × n × Lr",
        f"Lm = {Lc_cabos:.1f} + (1,55 + 1,22×{Lr:.2f}/√({L}²+{W}²)) × {n_hastes} × {Lr:.2f}",
        f"Lm = {Lm_est:.2f} m",
        f"Ls = 0,75·Lc + 0,85·n·Lr = 0,75×{Lc_cabos:.1f} + 0,85×{n_hastes}×{Lr:.2f} = {Ls_est:.2f} m",
    ])

    _par(doc, "Tensão de malha Em (IEEE 80 eq. 80):", bold=True)
    _bloco_calculo(doc, [
        "Em = ρ_eq × Km × Ki × IG / Lm",
        f"Em = {rho_eq:.1f} × {Km_est:.4f} × {Ki:.4f} × {ig:,.0f} / {Lm_est:.2f}",
        f"Em = {em:.1f} V",
        f"Etoque adm = {e_tq_adm:.1f} V  →  {'✅ APROVADO' if em <= e_tq_adm else '❌ REPROVADO'}"
        f"  (margem {100*(e_tq_adm-em)/e_tq_adm:+.1f}%)",
    ], hex_fundo=HEX_VERDE_OK if em <= e_tq_adm else HEX_VERMELHO_NOK)

    _par(doc, "Tensão de passo Es (IEEE 80 eq. 92):", bold=True)
    _bloco_calculo(doc, [
        "Es = ρ_eq × Ks × Ki × IG / Ls",
        f"Es = {rho_eq:.1f} × {Ks_est:.4f} × {Ki:.4f} × {ig:,.0f} / {Ls_est:.2f}",
        f"Es = {es:.1f} V",
        f"Epasso adm = {e_ps_adm:.1f} V  →  {'✅ APROVADO' if es <= e_ps_adm else '❌ REPROVADO'}"
        f"  (margem {100*(e_ps_adm-es)/e_ps_adm:+.1f}%)",
    ], hex_fundo=HEX_VERDE_OK if es <= e_ps_adm else HEX_VERMELHO_NOK)

    _par(doc, "Elevação de potencial da malha GPR:", bold=True)
    _bloco_calculo(doc, [
        "GPR = Rg × IG",
        f"GPR = {rg:.4f} × {ig:,.0f} = {gpr:.1f} V",
    ])

    doc.add_paragraph()
    doc.add_page_break()


def _bloco_calculo(doc: Document, linhas: list[str], hex_fundo=HEX_CINZA_ALT):
    """Caixa com fundo cinza para apresentar passos de cálculo."""
    tab = doc.add_table(1, 1)
    tab.style = "Table Grid"
    cell = tab.rows[0].cells[0]
    _cell_shade(cell, hex_fundo)
    # Remove o parágrafo vazio padrão
    for p in cell.paragraphs:
        p._element.getparent().remove(p._element)
    for linha in linhas:
        p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(1)
        run = p.add_run(linha)
        run.font.name = "Courier New"
        run.font.size = Pt(10)
    doc.add_paragraph()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 7: RESULTADOS E VERIFICAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def _sec_resultados(doc: Document, projeto: Projeto, imagens: dict):
    doc.add_heading("7. Resultados e Verificação", level=1)
    r = projeto.resultado
    de = projeto.dados_entrada
    if not r or not de:
        return

    # 7.1 Tabela consolidada
    doc.add_heading("7.1. Tabela consolidada de resultados", level=2)

    atende_t  = bool(r.atende_toque)
    atende_p  = bool(r.atende_passo)
    atende_c  = bool(r.atende_condutor)
    atende_g  = bool(r.atende_geral)

    em   = float(r.em_tensao_malha_v or 0)
    es   = float(r.es_tensao_passo_v or 0)
    etq  = float(r.etoque_admissivel_v or 0)
    eps  = float(r.epasso_admissivel_v or 0)
    mt   = float(r.margem_toque_pct or 0)
    mp   = float(r.margem_passo_pct or 0)

    headers = ["Parâmetro", "Valor calculado", "Valor admissível", "Situação", "Margem"]
    dados = [
        ["Resistência da malha Rg",
         f"{float(r.rg_adotado_ohm or 0):.4f} Ω", "—", "—", "—"],
        ["GPR (elevação de potencial)",
         f"{float(r.gpr_v or 0):.1f} V", "—", "—", "—"],
        ["Tensão de malha Em",
         f"{em:.1f} V", f"{etq:.1f} V",
         "✅ APROVADO" if atende_t else "❌ REPROVADO",
         f"{mt:+.1f}%"],
        ["Tensão de passo Es",
         f"{es:.1f} V", f"{eps:.1f} V",
         "✅ APROVADO" if atende_p else "❌ REPROVADO",
         f"{mp:+.1f}%"],
        ["Condutor — bitola calculada / adotada",
         f"{float(r.bitola_calculada_mm2 or 0):.1f} / {float(r.bitola_adotada_mm2 or 0):.0f} mm²",
         "Adotada ≥ calculada",
         "✅ OK" if atende_c else "❌ SUBDIMENSIONADO",
         "—"],
    ]

    tab = doc.add_table(rows=1 + len(dados), cols=5)
    tab.style = "Table Grid"
    tab.allow_autofit = False
    larguras = [4.5, 3.0, 3.0, 3.0, 1.8]
    for j, larg in enumerate(larguras):
        tab.columns[j].width = Cm(larg)

    hdr = tab.rows[0]
    for j, h in enumerate(headers):
        _cell_shade(hdr.cells[j], HEX_AZUL_TAB)
        _cell_text(hdr.cells[j], h, bold=True, size_pt=10, color=COR_AZUL_BK,
                   align=WD_ALIGN_PARAGRAPH.CENTER)

    for i, linha in enumerate(dados):
        row = tab.rows[i + 1]
        # Cor da linha de situação
        situacao_hex = HEX_CINZA_ALT
        if "✅" in linha[3]:
            situacao_hex = HEX_VERDE_OK
        elif "❌" in linha[3]:
            situacao_hex = HEX_VERMELHO_NOK
        for j, val in enumerate(linha):
            cell = row.cells[j]
            if j == 3:
                _cell_shade(cell, situacao_hex)
            else:
                _cell_shade(cell, HEX_CINZA_ALT if i % 2 == 0 else "FFFFFF")
            _cell_text(cell, val, size_pt=10,
                       bold=(j == 3),
                       align=WD_ALIGN_PARAGRAPH.CENTER if j > 0 else WD_ALIGN_PARAGRAPH.LEFT)

    doc.add_paragraph()

    # Banner de resultado geral
    if atende_g:
        _par_destaque(doc,
                      "✅  MALHA DE ATERRAMENTO APROVADA — atende integralmente IEEE Std 80-2013 e NBR 15751",
                      hex_fundo=HEX_VERDE_OK)
    else:
        _par_destaque(doc,
                      "❌  MALHA DE ATERRAMENTO REPROVADA — revisar geometria / proteção / brita",
                      hex_fundo=HEX_VERMELHO_NOK)

    doc.add_paragraph()

    # 7.2 Geometria final
    doc.add_heading("7.2. Geometria final adotada", level=2)
    _tabela_2col(doc, [
        ("Número de hastes",               f"{r.num_hastes}"),
        ("Comprimento total de cabo",      f"{float(r.comprimento_total_cabo_m or 0):.1f} m"),
        ("Rg por Sverak",                  f"{float(r.rg_sverak_ohm or 0):.4f} Ω"),
        ("Rg por Schwarz (adotado)",       f"{float(r.rg_schwarz_ohm or 0):.4f} Ω"),
        ("Corrente de malha IG",           f"{float(r.ig_corrente_malha_a or 0):,.0f} A"),
        ("Fator de decremento Df",         f"{float(r.df_decremento or 1):.4f}"),
        ("Fator de crescimento Cp",        f"{float(r.cp_crescimento or 1):.2f}"),
        ("GPR",                            f"{float(r.gpr_v or 0):.1f} V"),
    ])
    doc.add_paragraph()

    # 7.3 Figuras
    doc.add_heading("7.3. Figuras técnicas", level=2)

    if "wenner" in imagens:
        _adiciona_imagem(doc, imagens["wenner"],
                         "Figura 1 — Curva de Wenner e ajuste do modelo de 2 camadas (Sunde)")
    else:
        _aviso_figura(doc, "Curva de Wenner")

    if "planta" in imagens:
        _adiciona_imagem(doc, imagens["planta"],
                         f"Figura 2 — Planta da malha de aterramento "
                         f"({r.num_hastes} hastes — distribuição conforme IEEE 80-2013 §16.6)")
    else:
        _aviso_figura(doc, "Planta da malha")

    if "verif" in imagens:
        _adiciona_imagem(doc, imagens["verif"],
                         "Figura 3 — Comparação entre tensões calculadas e admissíveis (IEEE 80)")
    else:
        _aviso_figura(doc, "Verificação de tensões")

    if "mapa3d" in imagens:
        _adiciona_imagem(doc, imagens["mapa3d"],
                         "Figura 4 — Distribuição aproximada da tensão de toque sobre a SE")
    else:
        _aviso_figura(doc, "Mapa de tensão 3D")

    doc.add_paragraph()
    doc.add_page_break()


# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 8: CONCLUSÃO
# ══════════════════════════════════════════════════════════════════════════════

def _sec_conclusao(doc: Document, projeto: Projeto):
    doc.add_heading("8. Conclusão", level=1)
    r = projeto.resultado
    de = projeto.dados_entrada
    if not r or not de:
        return
    if r.atende_geral:
        texto = CONCLUSAO_ATENDE.format(
            em=float(r.em_tensao_malha_v or 0),
            es=float(r.es_tensao_passo_v or 0),
            etoque_adm=float(r.etoque_admissivel_v or 0),
            epasso_adm=float(r.epasso_admissivel_v or 0),
            margem_toque=float(r.margem_toque_pct or 0),
            margem_passo=float(r.margem_passo_pct or 0),
            rg=float(r.rg_adotado_ohm or 0),
            bitola_adotada=float(r.bitola_adotada_mm2 or 0),
            ig=float(r.ig_corrente_malha_a or 0),
            tempo=float(de.tempo_eliminacao_s),
        )
    else:
        texto = CONCLUSAO_NAO_ATENDE.format(
            em=float(r.em_tensao_malha_v or 0),
            es=float(r.es_tensao_passo_v or 0),
            etoque_adm=float(r.etoque_admissivel_v or 0),
            epasso_adm=float(r.epasso_admissivel_v or 0),
            margem_toque=float(r.margem_toque_pct or 0),
            margem_passo=float(r.margem_passo_pct or 0),
        )
    for bloco in texto.strip().split("\n\n"):
        _par_com_negrito(doc, " ".join(bloco.strip().split("\n")))


# ── Referências ───────────────────────────────────────────────────────────────

def _sec_referencias(doc: Document):
    doc.add_heading("9. Referências Bibliográficas", level=1)
    for i, ref in enumerate(REFERENCIAS, start=1):
        p = doc.add_paragraph()
        run = p.add_run(f"[{i}]  ")
        run.font.bold = True
        run.font.size = Pt(10)
        p.add_run(ref).font.size = Pt(10)


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_z(r, x) -> str:
    if r is not None and x is not None:
        return f"{float(r):.4f} + j{float(x):.4f}"
    return "—"


def _fmt_kv(de) -> str:
    """Tenta inferir tensão AT a partir dos dados elétricos."""
    return "—"


def _label_material(mat: str) -> str:
    return {
        "cobre_nu":        "Cobre nu (100% IACS)",
        "cobre_comercial": "Cobre comercial (97% IACS)",
        "copperweld_40":   "Copperweld 40% IACS",
        "copperweld_30":   "Copperweld 30% IACS",
        "aluminio_5005":   "Alumínio liga 5005",
        "aco_galvanizado": "Aço galvanizado",
    }.get(mat, mat)


def _const_material(mat: str):
    """
    Constantes IEEE 80 Tabela 1:
    Returns: (TCAP, alpha_r, rho_r, K0, Tm)
    """
    # (TCAP J/cm³°C, αr /°C, ρr μΩ·cm, K0 °C, Tm °C)
    tabela = {
        "cobre_nu":        (3.422, 0.003930, 1.7241, 234.0, 1084.0),
        "cobre_comercial": (3.422, 0.003810, 1.7770, 242.0, 1084.0),
        "copperweld_40":   (3.422, 0.003800, 4.4000, 242.7, 1084.0),
        "copperweld_30":   (3.422, 0.003800, 5.8600, 242.7, 1084.0),
        "aluminio_5005":   (2.560, 0.003600, 3.2200, 228.1,  657.0),
        "aco_galvanizado": (3.931, 0.003280, 15.900, 285.0, 1510.0),
    }
    return tabela.get(mat, tabela["cobre_nu"])


# ══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

def gera_relatorio_word(
    projeto: Projeto,
    imagens: dict[str, bytes],
    logo_path: Optional[str] = None,
) -> bytes:
    """
    Gera o relatório técnico completo .docx para aprovação em concessionária.

    Args:
        projeto  : objeto Projeto com filhos eager-loaded (dados_entrada, resultado,
                   medicoes_wenner, barras, reles, transformadores).
        imagens  : dict com chaves 'wenner', 'planta', 'verif', 'mapa3d'
                   e valores em bytes (PNG). Chaves ausentes geram aviso no relatório.
        logo_path: caminho opcional do logo BK (PNG/JPG).

    Returns:
        Bytes do arquivo .docx.
    """
    if not projeto.dados_entrada or not projeto.resultado:
        raise ValueError(
            "Projeto sem dados de entrada ou resultados. "
            "Execute o cálculo (aba 5) antes de gerar o relatório."
        )

    doc = Document()
    _config_pagina(doc, projeto)
    _config_estilos(doc)

    _capa(doc, projeto, logo_path)
    _revisoes(doc, projeto)
    _sec_objetivo(doc, projeto)
    _sec_sistema_eletrico(doc, projeto)
    _sec_protecao(doc, projeto)
    _sec_metodologia(doc)
    _sec_dados_entrada(doc, projeto)
    _sec_memorial(doc, projeto)
    _sec_resultados(doc, projeto, imagens)
    _sec_conclusao(doc, projeto)
    _sec_referencias(doc)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def nome_arquivo_padrao(projeto: Projeto) -> str:
    """MC_MALHA_{NUM}_R{REV}_{CLIENTE}.docx"""
    def limpa(s: str) -> str:
        return "".join(c if c.isalnum() else "_" for c in (s or ""))
    return f"MC_MALHA_{limpa(projeto.numero_projeto)}_R{projeto.revisao}_{limpa(projeto.cliente)[:25]}.docx"
