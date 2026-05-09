"""
relatorio/gerador_word.py
=========================

Gera o relatório técnico .docx a partir dos dados de um projeto persistido
no banco. Usa python-docx + OMML para equações nativas do Word.

Estrutura do documento:
    - Capa (logo BK, identificação)
    - 1. Objetivo
    - 2. Metodologia (subseções 2.1 a 2.7 com EQUAÇÕES OMML NATIVAS)
    - 3. Dados de entrada (tabelas)
    - 4. Resultados (tabelas + gráficos PNG)
    - 5. Conclusão
    - 6. Referências

Equações: marcadores [[EQ:nome]] no texto são substituídos por
parágrafos OMML inseridos no documento (renderizados pelo Word como
equações editáveis, não como imagens).

Imagens: passar via dict `imagens` com chaves 'wenner', 'planta',
'verif', 'mapa3d' e valores em bytes (PNG).
"""

from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml
from docx.shared import Cm, Pt, RGBColor

from data.models import Projeto
from relatorio.equacoes import EQUACOES_OMML
from relatorio.textos import (
    CONCLUSAO_ATENDE, CONCLUSAO_NAO_ATENDE,
    METODOLOGIA_CONDUTOR, METODOLOGIA_CORRENTE,
    METODOLOGIA_DETALHES_PROJETO, METODOLOGIA_EM_ES, METODOLOGIA_INTRO,
    METODOLOGIA_RG, METODOLOGIA_SOLO, METODOLOGIA_TENSOES_ADM,
    OBJETIVO_TEMPLATE, REFERENCIAS,
)

# Cores BK
COR_AZUL_BK = RGBColor(0x1F, 0x4E, 0x79)
COR_VERDE_BK = RGBColor(0x3F, 0xAE, 0x2A)
COR_VERMELHO = RGBColor(0xC0, 0x39, 0x2B)
COR_CINZA_CLARO = "F0F0F0"
COR_AZUL_CLARO = "D5E8F0"

# Regex para detectar marcadores de equação
RE_EQUACAO = re.compile(r"\[\[EQ:([a-zA-Z0-9_]+)\]\]")


# ============================================================
# UTILITÁRIOS DE ESTILO
# ============================================================

def _set_cell_shading(cell, color_hex: str):
    """Aplica cor de fundo a uma célula de tabela."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def _add_page_number(paragraph):
    """Adiciona campo de numeração de página."""
    run = paragraph.add_run()
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    run._r.append(fldChar1)
    instrText = OxmlElement("w:instrText")
    instrText.text = "PAGE"
    run._r.append(instrText)
    fldChar2 = OxmlElement("w:fldChar")
    fldChar2.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar2)


def _config_estilos(doc: Document):
    """Configura estilos de heading e parágrafo padrão."""
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    h1 = doc.styles["Heading 1"]
    h1.font.name = "Calibri"
    h1.font.size = Pt(16)
    h1.font.bold = True
    h1.font.color.rgb = COR_AZUL_BK

    h2 = doc.styles["Heading 2"]
    h2.font.name = "Calibri"
    h2.font.size = Pt(13)
    h2.font.bold = True
    h2.font.color.rgb = COR_AZUL_BK

    h3 = doc.styles["Heading 3"]
    h3.font.name = "Calibri"
    h3.font.size = Pt(11)
    h3.font.bold = True
    h3.font.color.rgb = COR_AZUL_BK


def _config_pagina(doc: Document):
    """Configura tamanho A4 e margens."""
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.0)

    header = section.header
    p = header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("BK Engenharia · Memória de Cálculo - Malha de Aterramento")
    run.font.size = Pt(9)
    run.font.color.rgb = COR_AZUL_BK
    run.italic = True

    footer = section.footer
    pf = footer.paragraphs[0]
    pf.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = pf.add_run("Página ")
    run.font.size = Pt(9)
    _add_page_number(pf)


# ============================================================
# INSERÇÃO DE EQUAÇÕES OMML
# ============================================================

def _insere_equacao_omml(doc: Document, identificador: str):
    """
    Insere equação OMML como parágrafo centralizado no documento.

    A equação é renderizada nativamente pelo Word (não é imagem),
    permitindo edição posterior pelo usuário.

    Implementação: cria um <w:p> normal e injeta o <m:oMathPara> dentro.
    Isso é exigido pelo schema OOXML — todo elemento direto do body deve
    ser <w:p>, <w:tbl> ou <w:sectPr>.

    Args:
        doc          : documento python-docx
        identificador: chave em EQUACOES_OMML
    """
    if identificador not in EQUACOES_OMML:
        # Fallback: insere como texto plano destacado, em vez de quebrar
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = par.add_run(f"[Equação '{identificador}' não encontrada]")
        run.italic = True
        run.font.color.rgb = COR_VERMELHO
        return

    # Cria um parágrafo normal centralizado
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Pega o XML da equação e injeta DENTRO do <w:p> recém-criado
    xml = EQUACOES_OMML[identificador].strip()
    omath_element = parse_xml(xml)
    par._p.append(omath_element)


# ============================================================
# RENDERIZAÇÃO DE TEXTO COM EQUAÇÕES
# ============================================================

def _renderiza_texto_com_equacoes(doc: Document, texto: str):
    """
    Renderiza um bloco de texto da metodologia processando:
        - **Subtítulos** em negrito → Heading 3
        - [[EQ:nome]] → equação OMML centralizada
        - **negrito** inline → run negrito
        - parágrafos separados por linha em branco

    Args:
        doc  : documento python-docx
        texto: texto bruto da metodologia
    """
    blocos = texto.strip().split("\n\n")
    for bloco in blocos:
        linhas = [l.strip() for l in bloco.strip().split("\n") if l.strip()]
        if not linhas:
            continue

        primeira = linhas[0]
        texto_completo = " ".join(linhas)

        # Subtítulo: linha completa começa e termina com **
        if (primeira.startswith("**") and primeira.endswith("**")
                and len(linhas) == 1):
            doc.add_heading(primeira.strip("*").strip(), level=3)
            continue

        # Múltiplas linhas onde a primeira é subtítulo em negrito
        if (primeira.startswith("**") and primeira.endswith("**")
                and len(linhas) > 1):
            doc.add_heading(primeira.strip("*").strip(), level=3)
            texto_completo = " ".join(linhas[1:])

        # Verifica se o bloco É APENAS uma equação
        match_solo = RE_EQUACAO.fullmatch(texto_completo)
        if match_solo:
            _insere_equacao_omml(doc, match_solo.group(1))
            continue

        # Bloco com equações inline misturadas com texto:
        # quebra em segmentos texto/equação e renderiza
        partes = RE_EQUACAO.split(texto_completo)
        # split com 1 grupo retorna: [texto1, id_eq1, texto2, id_eq2, ...]
        i = 0
        par_atual = None
        while i < len(partes):
            segmento = partes[i]
            if i % 2 == 0:
                # Texto normal
                if segmento.strip():
                    par_atual = doc.add_paragraph()
                    _adiciona_runs_com_negrito(par_atual, segmento.strip())
            else:
                # Identificador de equação
                _insere_equacao_omml(doc, segmento)
                par_atual = None
            i += 1


def _adiciona_runs_com_negrito(paragrafo, texto: str):
    """Processa **negrito** inline e adiciona runs apropriados."""
    partes = texto.split("**")
    for idx, parte in enumerate(partes):
        run = paragrafo.add_run(parte)
        run.font.size = Pt(11)
        if idx % 2 == 1:
            run.font.bold = True


def _adiciona_paragrafo_simples(doc: Document, texto: str):
    """Adiciona texto multi-parágrafo SEM processamento de equações."""
    for bloco in texto.strip().split("\n\n"):
        linhas = [l.strip() for l in bloco.strip().split("\n") if l.strip()]
        if not linhas:
            continue
        texto_completo = " ".join(linhas)
        par = doc.add_paragraph()
        _adiciona_runs_com_negrito(par, texto_completo)


# ============================================================
# CAPA E SEÇÕES PRINCIPAIS
# ============================================================

def _adiciona_capa(doc: Document, p: Projeto, logo_path: Optional[str] = None):
    """Capa do documento."""
    if logo_path and Path(logo_path).exists():
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_logo = p_logo.add_run()
        try:
            run_logo.add_picture(logo_path, width=Cm(6))
        except Exception:
            pass

    for _ in range(3):
        doc.add_paragraph()

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("MEMÓRIA DE CÁLCULO")
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = COR_AZUL_BK

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("MALHA DE ATERRAMENTO DE SUBESTAÇÃO")
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = COR_AZUL_BK

    for _ in range(2):
        doc.add_paragraph()

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run(p.nome_projeto)
    run.font.size = Pt(16)
    run.font.bold = True

    for _ in range(4):
        doc.add_paragraph()

    tabela = doc.add_table(rows=6, cols=2)
    tabela.alignment = WD_TABLE_ALIGNMENT.CENTER
    tabela.style = "Light Grid Accent 1"
    tabela.autofit = False
    tabela.columns[0].width = Cm(5)
    tabela.columns[1].width = Cm(10)

    rows_data = [
        ("Cliente", p.cliente),
        ("Concessionária", p.concessionaria or "—"),
        ("Número do projeto", p.numero_projeto),
        ("Revisão", f"R{p.revisao}"),
        ("Data do cálculo", p.data_calculo.strftime("%d/%m/%Y")),
        ("Responsável técnico",
         f"{p.responsavel_tecnico or '—'}"
         + (f"  ·  CREA {p.crea_responsavel}" if p.crea_responsavel else "")),
    ]
    for i, (label, value) in enumerate(rows_data):
        c1, c2 = tabela.rows[i].cells
        c1.text = label
        c2.text = str(value)
        for cell in (c1, c2):
            for par_c in cell.paragraphs:
                for run in par_c.runs:
                    run.font.size = Pt(11)
        for run in c1.paragraphs[0].runs:
            run.font.bold = True
        _set_cell_shading(c1, COR_AZUL_CLARO)

    doc.add_page_break()


def _adiciona_secao_objetivo(doc: Document, p: Projeto):
    doc.add_heading("1. Objetivo", level=1)
    texto = OBJETIVO_TEMPLATE.format(
        cliente=p.cliente,
        nome_projeto=p.nome_projeto,
        numero_projeto=p.numero_projeto,
        revisao=p.revisao,
        concessionaria=p.concessionaria or "(a definir)",
        responsavel=p.responsavel_tecnico or "(a definir)",
        crea_responsavel=p.crea_responsavel or "—",
        data_calculo=p.data_calculo.strftime("%d/%m/%Y"),
    )
    _adiciona_paragrafo_simples(doc, texto)


def _adiciona_secao_metodologia(doc: Document):
    """Renderiza metodologia completa com EQUAÇÕES OMML inline."""
    doc.add_heading("2. Metodologia", level=1)
    _adiciona_paragrafo_simples(doc, METODOLOGIA_INTRO)

    for texto in [
        METODOLOGIA_SOLO,
        METODOLOGIA_CORRENTE,
        METODOLOGIA_CONDUTOR,
        METODOLOGIA_TENSOES_ADM,
        METODOLOGIA_RG,
        METODOLOGIA_EM_ES,
        METODOLOGIA_DETALHES_PROJETO,
    ]:
        _renderiza_texto_com_equacoes(doc, texto)


def _adiciona_tabela_par(doc: Document, dados: list[tuple[str, str]]):
    """Tabela de 2 colunas (parâmetro, valor)."""
    tab = doc.add_table(rows=len(dados), cols=2)
    tab.style = "Light Grid Accent 1"
    tab.autofit = False
    tab.columns[0].width = Cm(8)
    tab.columns[1].width = Cm(7)
    for i, (label, valor) in enumerate(dados):
        c1, c2 = tab.rows[i].cells
        c1.text = label
        c2.text = valor
        for run in c1.paragraphs[0].runs:
            run.font.bold = True
        _set_cell_shading(c1, COR_CINZA_CLARO)


def _adiciona_secao_dados_entrada(doc: Document, p: Projeto):
    doc.add_heading("3. Dados de Entrada", level=1)
    de = p.dados_entrada

    doc.add_heading("3.1. Medições de resistividade do solo (Wenner)", level=2)
    if p.medicoes_wenner:
        tab = doc.add_table(rows=1 + len(p.medicoes_wenner), cols=4)
        tab.style = "Light Grid Accent 1"
        headers = ["Ponto", "a [m]", "R [Ω]", "ρ aparente [Ω·m]"]
        for i, h in enumerate(headers):
            c = tab.rows[0].cells[i]
            c.text = h
            for par in c.paragraphs:
                for run in par.runs:
                    run.font.bold = True
            _set_cell_shading(c, COR_AZUL_CLARO)
        for i, m in enumerate(p.medicoes_wenner, start=1):
            row = tab.rows[i]
            row.cells[0].text = str(m.ponto)
            row.cells[1].text = f"{float(m.espacamento_m):.2f}"
            row.cells[2].text = f"{float(m.resistencia_ohm):.4f}"
            row.cells[3].text = f"{float(m.rho_aparente):.1f}" if m.rho_aparente else "—"

    doc.add_heading("3.2. Geometria da subestação", level=2)
    _adiciona_tabela_par(doc, [
        ("Largura W", f"{float(de.largura_m):.2f} m"),
        ("Comprimento L", f"{float(de.comprimento_m):.2f} m"),
        ("Área A", f"{float(de.largura_m) * float(de.comprimento_m):.1f} m²"),
        ("Profundidade da malha h", f"{float(de.profundidade_malha_m):.2f} m"),
        ("Espaçamento da malha principal D",
         f"{float(de.espac_malha_principal_m):.2f} m"),
        ("Espaçamento da malha de junção (bordas)",
         f"{float(de.espac_malha_juncao_m or 0):.2f} m"),
    ])

    doc.add_heading("3.3. Brita superficial", level=2)
    _adiciona_tabela_par(doc, [
        ("Espessura hs", f"{float(de.brita_espessura_m):.3f} m"),
        ("Resistividade ρs", f"{float(de.brita_resistividade_ohm):.0f} Ω·m"),
    ])

    doc.add_heading("3.4. Hastes copperweld", level=2)
    _adiciona_tabela_par(doc, [
        ("Comprimento Lr", f"{float(de.haste_comprimento_m):.2f} m"),
        ("Diâmetro d", f"{float(de.haste_diametro_mm):.3f} mm"),
    ])

    doc.add_heading("3.5. Dados elétricos do curto-circuito", level=2)
    _adiciona_tabela_par(doc, [
        ("Corrente simétrica de falta 3I₀",
         f"{float(de.i_falta_3i0_ka):.3f} kA"),
        ("Tempo de eliminação tc",
         f"{float(de.tempo_eliminacao_s):.3f} s"),
        ("Fator de divisão Sf", f"{float(de.sf_div_corrente):.2f}"),
        ("Relação X/R", f"{float(de.xr_ratio or 0):.1f}"),
        ("Peso da pessoa (Dalziel)", f"{int(de.peso_pessoa_kg)} kg"),
    ])


def _adiciona_imagem(doc: Document, image_bytes: bytes, legenda: str):
    """Adiciona imagem centralizada com legenda em itálico."""
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run()
    try:
        run.add_picture(io.BytesIO(image_bytes), width=Cm(15))
    except Exception as e:
        par.add_run(f"[Erro ao inserir imagem: {e}]")
        return

    par_leg = doc.add_paragraph()
    par_leg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par_leg.add_run(legenda)
    run.italic = True
    run.font.size = Pt(9)


def _adiciona_aviso_imagem_faltando(doc: Document, legenda: str):
    """Quando a imagem não foi gerada, deixa marcação visível em vermelho."""
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run(f"[Figura ausente: {legenda}]")
    run.italic = True
    run.font.color.rgb = COR_VERMELHO


def _adiciona_secao_resultados(doc: Document, p: Projeto, imagens: dict):
    doc.add_heading("4. Resultados", level=1)
    r = p.resultado

    doc.add_heading("4.1. Estratificação do solo", level=2)
    _adiciona_tabela_par(doc, [
        ("ρ₁ (camada superior)", f"{float(r.rho1_ohm_m or 0):.1f} Ω·m"),
        ("ρ₂ (camada inferior)", f"{float(r.rho2_ohm_m or 0):.1f} Ω·m"),
        ("h₁ (espessura camada 1)", f"{float(r.h1_m or 0):.2f} m"),
        ("ρ_equivalente (Sverak/Schwarz)",
         f"{float(r.rho_equivalente or 0):.1f} Ω·m"),
    ])
    if "wenner" in imagens:
        _adiciona_imagem(
            doc, imagens["wenner"],
            "Figura 1 — Curva de Wenner e ajuste do modelo de 2 camadas"
        )
    else:
        _adiciona_aviso_imagem_faltando(
            doc, "Curva de Wenner e ajuste"
        )

    doc.add_heading("4.2. Corrente de malha", level=2)
    _adiciona_tabela_par(doc, [
        ("Fator de decremento Df", f"{float(r.df_decremento or 1):.4f}"),
        ("IG (corrente máxima de malha)",
         f"{float(r.ig_corrente_malha_a or 0):.0f} A"),
    ])

    doc.add_heading("4.3. Condutor da malha (Sverak)", level=2)
    _adiciona_tabela_par(doc, [
        ("Bitola calculada",
         f"{float(r.bitola_calculada_mm2 or 0):.2f} mm²"),
        ("Bitola adotada",
         f"{float(r.bitola_adotada_mm2 or 0):.0f} mm²"),
    ])

    doc.add_heading("4.4. Tensões admissíveis pelo corpo humano", level=2)
    _adiciona_tabela_par(doc, [
        ("Cs (fator de redução brita)", f"{float(r.cs_brita or 0):.3f}"),
        ("E_toque admissível", f"{float(r.etoque_admissivel_v or 0):.1f} V"),
        ("E_passo admissível", f"{float(r.epasso_admissivel_v or 0):.1f} V"),
    ])

    doc.add_heading("4.5. Resistência da malha", level=2)
    _adiciona_tabela_par(doc, [
        ("Rg por Sverak", f"{float(r.rg_sverak_ohm or 0):.4f} Ω"),
        ("Rg por Schwarz (adotado)",
         f"{float(r.rg_schwarz_ohm or 0):.4f} Ω"),
        ("GPR (Ground Potential Rise)",
         f"{float(r.gpr_v or 0):.1f} V"),
    ])

    doc.add_heading("4.6. Geometria final adotada", level=2)
    _adiciona_tabela_par(doc, [
        ("Número de hastes", f"{r.num_hastes}"),
        ("Comprimento total de cabo enterrado",
         f"{float(r.comprimento_total_cabo_m or 0):.1f} m"),
    ])
    if "planta" in imagens:
        _adiciona_imagem(
            doc, imagens["planta"],
            "Figura 2 — Planta da malha de aterramento com posicionamento das hastes"
        )
    else:
        _adiciona_aviso_imagem_faltando(
            doc, "Planta da malha de aterramento"
        )

    doc.add_heading("4.7. Verificação dos critérios IEEE 80", level=2)
    _adiciona_tabela_par(doc, [
        ("Em (tensão de malha calculada)",
         f"{float(r.em_tensao_malha_v or 0):.1f} V"),
        ("E_toque admissível",
         f"{float(r.etoque_admissivel_v or 0):.1f} V"),
        ("Atende critério de toque",
         "✓ SIM" if r.atende_toque else "✗ NÃO"),
        ("Margem de toque",
         f"{float(r.margem_toque_pct or 0):+.1f}%"),
        ("Es (tensão de passo calculada)",
         f"{float(r.es_tensao_passo_v or 0):.1f} V"),
        ("E_passo admissível",
         f"{float(r.epasso_admissivel_v or 0):.1f} V"),
        ("Atende critério de passo",
         "✓ SIM" if r.atende_passo else "✗ NÃO"),
        ("Margem de passo",
         f"{float(r.margem_passo_pct or 0):+.1f}%"),
    ])
    if "verif" in imagens:
        _adiciona_imagem(
            doc, imagens["verif"],
            "Figura 3 — Comparação entre tensões calculadas e admissíveis"
        )
    else:
        _adiciona_aviso_imagem_faltando(
            doc, "Comparação tensões calculadas vs admissíveis"
        )

    if "mapa3d" in imagens:
        _adiciona_imagem(
            doc, imagens["mapa3d"],
            "Figura 4 — Distribuição aproximada da tensão de toque sobre a SE"
        )
    else:
        _adiciona_aviso_imagem_faltando(
            doc, "Distribuição 3D da tensão de toque"
        )


def _adiciona_secao_conclusao(doc: Document, p: Projeto):
    doc.add_heading("5. Conclusão", level=1)
    r = p.resultado
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
            tempo=float(p.dados_entrada.tempo_eliminacao_s or 0),
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
    _adiciona_paragrafo_simples(doc, texto)


def _adiciona_secao_referencias(doc: Document):
    doc.add_heading("6. Referências Bibliográficas", level=1)
    for i, ref in enumerate(REFERENCIAS, start=1):
        par = doc.add_paragraph()
        run = par.add_run(f"[{i}] ")
        run.font.bold = True
        par.add_run(ref)


# ============================================================
# FUNÇÃO PÚBLICA PRINCIPAL
# ============================================================

def gera_relatorio_word(
    projeto: Projeto,
    imagens: dict[str, bytes],
    logo_path: Optional[str] = None,
) -> bytes:
    """
    Gera o relatório Word completo com equações OMML e gráficos.

    Args:
        projeto  : objeto Projeto com filhos eager-loaded.
        imagens  : dict com chaves 'wenner', 'planta', 'verif', 'mapa3d'
                    e valores em bytes (PNG). Chaves ausentes geram
                    marcação "[Figura ausente]" em vermelho no relatório.
        logo_path: caminho opcional do logo BK (PNG).

    Returns:
        Bytes do arquivo .docx pronto para download.
    """
    if not projeto.dados_entrada or not projeto.resultado:
        raise ValueError(
            "Projeto sem dados de entrada ou resultados. "
            "Execute o cálculo primeiro."
        )

    doc = Document()
    _config_pagina(doc)
    _config_estilos(doc)

    _adiciona_capa(doc, projeto, logo_path)
    _adiciona_secao_objetivo(doc, projeto)
    _adiciona_secao_metodologia(doc)
    _adiciona_secao_dados_entrada(doc, projeto)
    _adiciona_secao_resultados(doc, projeto, imagens)
    _adiciona_secao_conclusao(doc, projeto)
    _adiciona_secao_referencias(doc)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def nome_arquivo_padrao(projeto: Projeto) -> str:
    """Gera nome padrão: MC_MALHA_{NUMERO}_R{REV}_{CLIENTE}.docx"""
    cliente_clean = "".join(
        c if c.isalnum() else "_" for c in (projeto.cliente or "Cliente")
    )[:30]
    numero_clean = "".join(
        c if c.isalnum() else "_" for c in (projeto.numero_projeto or "PRJ")
    )
    return f"MC_MALHA_{numero_clean}_R{projeto.revisao}_{cliente_clean}.docx"
