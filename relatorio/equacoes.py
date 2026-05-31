"""
relatorio/equacoes.py
=====================

Equações OMML (Office Math Markup Language) prontas para inserção
em documentos Word via python-docx.

Cada equação é um XML string que, quando inserido como elemento OMML
dentro de um parágrafo, é renderizado pelo Word como equação matemática
nativa (não imagem, não texto plano).

Uso:
    from relatorio.equacoes import EQUACOES_OMML, insere_equacao

    insere_equacao(paragrafo, "wenner")

Estrutura do OMML simplificada utilizada:
    <m:oMath>          - bloco de equação inline
    <m:r><m:t>...</m:t></m:r>  - run com texto matemático
    <m:f>              - fração: <m:num>numerador</m:num><m:den>denominador</m:den>
    <m:rad>            - radical: <m:deg>grau</m:deg><m:e>radicando</m:e>
    <m:sSub>           - subscrito: <m:e>base</m:e><m:sub>sub</m:sub>
    <m:sSup>           - sobrescrito: <m:e>base</m:e><m:sup>sup</m:sup>
    <m:sSubSup>        - sub e sobrescrito juntos
    <m:nary>           - operador grande (Σ, ∫): <m:naryPr>...</m:naryPr><m:sub><m:sup><m:e>
    <m:d>              - delimitadores (parênteses): <m:dPr>...</m:dPr><m:e>
    <m:func>           - função (sin, cos, ln): <m:fName>nome</m:fName><m:e>arg</m:e>

Para clareza, escrevi cada equação manualmente em XML.
"""

from copy import deepcopy
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsmap, qn


# Namespace OMML (incluído em todo Word)
M_NS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


# ============================================================
# Equações OMML
# ============================================================
# Cada equação é uma string XML completa que será wrapped em <m:oMathPara>
# para inserção como parágrafo de equação centralizado.

EQUACOES_OMML: dict[str, str] = {

    # ρ_a = 2 · π · a · R                                   (Wenner)
    "wenner": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr>
            <m:jc m:val="center"/>
        </m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                <m:sub><m:r><m:t>a</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = 2π·a·R</m:t></m:r>
        </m:oMath>
    </m:oMathPara>""",

    # K = (ρ₂ - ρ₁) / (ρ₂ + ρ₁)
    "k_reflexao": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr>
            <m:jc m:val="center"/>
        </m:oMathParaPr>
        <m:oMath>
            <m:r><m:t>K = </m:t></m:r>
            <m:f>
                <m:num>
                    <m:sSub>
                        <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>2</m:t></m:r></m:sub>
                    </m:sSub>
                    <m:r><m:t> − </m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
                    </m:sSub>
                </m:num>
                <m:den>
                    <m:sSub>
                        <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>2</m:t></m:r></m:sub>
                    </m:sSub>
                    <m:r><m:t> + </m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
                    </m:sSub>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # ρ_a(a) = ρ₁ · [1 + 4·Σ_{n=1}^∞ (...)]    (Sunde)
    "sunde": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr>
            <m:jc m:val="center"/>
        </m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                <m:sub><m:r><m:t>a</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>(a) = </m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·[1 + 4·</m:t></m:r>
            <m:nary>
                <m:naryPr>
                    <m:chr m:val="∑"/>
                    <m:limLoc m:val="undOvr"/>
                </m:naryPr>
                <m:sub>
                    <m:r><m:t>n=1</m:t></m:r>
                </m:sub>
                <m:sup>
                    <m:r><m:t>∞</m:t></m:r>
                </m:sup>
                <m:e>
                    <m:d>
                        <m:dPr>
                            <m:begChr m:val="("/>
                            <m:endChr m:val=")"/>
                        </m:dPr>
                        <m:e>
                            <m:f>
                                <m:num>
                                    <m:sSup>
                                        <m:e><m:r><m:t>K</m:t></m:r></m:e>
                                        <m:sup><m:r><m:t>n</m:t></m:r></m:sup>
                                    </m:sSup>
                                </m:num>
                                <m:den>
                                    <m:rad>
                                        <m:radPr><m:degHide m:val="1"/></m:radPr>
                                        <m:deg/>
                                        <m:e>
                                            <m:r><m:t>1 + (2nh</m:t></m:r>
                                            <m:sSub>
                                                <m:e><m:r>h<m:t/></m:r></m:e>
                                                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
                                            </m:sSub>
                                            <m:r><m:t>/a)²</m:t></m:r>
                                        </m:e>
                                    </m:rad>
                                </m:den>
                            </m:f>
                            <m:r><m:t> − </m:t></m:r>
                            <m:f>
                                <m:num>
                                    <m:sSup>
                                        <m:e><m:r><m:t>K</m:t></m:r></m:e>
                                        <m:sup><m:r><m:t>n</m:t></m:r></m:sup>
                                    </m:sSup>
                                </m:num>
                                <m:den>
                                    <m:rad>
                                        <m:radPr><m:degHide m:val="1"/></m:radPr>
                                        <m:deg/>
                                        <m:e>
                                            <m:r><m:t>4 + (2nh</m:t></m:r>
                                            <m:sSub>
                                                <m:e><m:r><m:t/></m:r></m:e>
                                                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
                                            </m:sSub>
                                            <m:r><m:t>/a)²</m:t></m:r>
                                        </m:e>
                                    </m:rad>
                                </m:den>
                            </m:f>
                        </m:e>
                    </m:d>
                </m:e>
            </m:nary>
            <m:r><m:t>]</m:t></m:r>
        </m:oMath>
    </m:oMathPara>""",

    # IG = Df · Sf · 3·I₀
    "ig": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>I</m:t></m:r></m:e>
                <m:sub><m:r><m:t>G</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>D</m:t></m:r></m:e>
                <m:sub><m:r><m:t>f</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>S</m:t></m:r></m:e>
                <m:sub><m:r><m:t>f</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·3·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>I</m:t></m:r></m:e>
                <m:sub><m:r><m:t>0</m:t></m:r></m:sub>
            </m:sSub>
        </m:oMath>
    </m:oMathPara>""",

    # Df = √(1 + (Ta/tf)·(1 - e^(-2tf/Ta)))
    "df": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>D</m:t></m:r></m:e>
                <m:sub><m:r><m:t>f</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:rad>
                <m:radPr><m:degHide m:val="1"/></m:radPr>
                <m:deg/>
                <m:e>
                    <m:r><m:t>1 + </m:t></m:r>
                    <m:f>
                        <m:num>
                            <m:sSub>
                                <m:e><m:r><m:t>T</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>a</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:num>
                        <m:den>
                            <m:sSub>
                                <m:e><m:r><m:t>t</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>f</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:den>
                    </m:f>
                    <m:r><m:t>·(1 − </m:t></m:r>
                    <m:sSup>
                        <m:e><m:r><m:t>e</m:t></m:r></m:e>
                        <m:sup>
                            <m:r><m:t>−2</m:t></m:r>
                            <m:sSub>
                                <m:e><m:r><m:t>t</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>f</m:t></m:r></m:sub>
                            </m:sSub>
                            <m:r><m:t>/</m:t></m:r>
                            <m:sSub>
                                <m:e><m:r><m:t>T</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>a</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:sup>
                    </m:sSup>
                    <m:r><m:t>)</m:t></m:r>
                </m:e>
            </m:rad>
        </m:oMath>
    </m:oMathPara>""",

    # A = I · √(tc · α · ρr / (TCAP · ln((K0+Tm)/(K0+Ta))))     (Sverak condutor)
    "sverak_condutor": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:r><m:t>A = I·</m:t></m:r>
            <m:rad>
                <m:radPr><m:degHide m:val="1"/></m:radPr>
                <m:deg/>
                <m:e>
                    <m:f>
                        <m:num>
                            <m:sSub>
                                <m:e><m:r><m:t>t</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
                            </m:sSub>
                            <m:r><m:t>·</m:t></m:r>
                            <m:sSub>
                                <m:e><m:r><m:t>α</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>r</m:t></m:r></m:sub>
                            </m:sSub>
                            <m:r><m:t>·</m:t></m:r>
                            <m:sSub>
                                <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>r</m:t></m:r></m:sub>
                            </m:sSub>
                            <m:r><m:t>·10⁴</m:t></m:r>
                        </m:num>
                        <m:den>
                            <m:r><m:t>TCAP·ln</m:t></m:r>
                            <m:d>
                                <m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/></m:dPr>
                                <m:e>
                                    <m:f>
                                        <m:num>
                                            <m:sSub>
                                                <m:e><m:r><m:t>K</m:t></m:r></m:e>
                                                <m:sub><m:r><m:t>0</m:t></m:r></m:sub>
                                            </m:sSub>
                                            <m:r><m:t>+</m:t></m:r>
                                            <m:sSub>
                                                <m:e><m:r><m:t>T</m:t></m:r></m:e>
                                                <m:sub><m:r><m:t>m</m:t></m:r></m:sub>
                                            </m:sSub>
                                        </m:num>
                                        <m:den>
                                            <m:sSub>
                                                <m:e><m:r><m:t>K</m:t></m:r></m:e>
                                                <m:sub><m:r><m:t>0</m:t></m:r></m:sub>
                                            </m:sSub>
                                            <m:r><m:t>+</m:t></m:r>
                                            <m:sSub>
                                                <m:e><m:r><m:t>T</m:t></m:r></m:e>
                                                <m:sub><m:r><m:t>a</m:t></m:r></m:sub>
                                            </m:sSub>
                                        </m:den>
                                    </m:f>
                                </m:e>
                            </m:d>
                        </m:den>
                    </m:f>
                </m:e>
            </m:rad>
        </m:oMath>
    </m:oMathPara>""",

    # I_corpo = k / √ts   (Dalziel)
    "dalziel": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>I</m:t></m:r></m:e>
                <m:sub><m:r><m:t>corpo</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num><m:r><m:t>k</m:t></m:r></m:num>
                <m:den>
                    <m:rad>
                        <m:radPr><m:degHide m:val="1"/></m:radPr>
                        <m:deg/>
                        <m:e>
                            <m:sSub>
                                <m:e><m:r><m:t>t</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:e>
                    </m:rad>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # Cs = 1 - 0.09(1 - ρ/ρs) / (2hs + 0.09)
    "cs": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>C</m:t></m:r></m:e>
                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = 1 − </m:t></m:r>
            <m:f>
                <m:num>
                    <m:r><m:t>0,09·(1 − ρ/</m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
                    </m:sSub>
                    <m:r><m:t>)</m:t></m:r>
                </m:num>
                <m:den>
                    <m:r><m:t>2·</m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>h</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
                    </m:sSub>
                    <m:r><m:t> + 0,09</m:t></m:r>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # E_toque = (1000 + 1.5·Cs·ρs) · k / √ts
    "etoque_adm": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>E</m:t></m:r></m:e>
                <m:sub><m:r><m:t>toque</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = (1000 + 1,5·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>C</m:t></m:r></m:e>
                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>)·</m:t></m:r>
            <m:f>
                <m:num><m:r><m:t>k</m:t></m:r></m:num>
                <m:den>
                    <m:rad>
                        <m:radPr><m:degHide m:val="1"/></m:radPr>
                        <m:deg/>
                        <m:e>
                            <m:sSub>
                                <m:e><m:r><m:t>t</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:e>
                    </m:rad>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # E_passo = (1000 + 6·Cs·ρs) · k / √ts
    "epasso_adm": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>E</m:t></m:r></m:e>
                <m:sub><m:r><m:t>passo</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = (1000 + 6·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>C</m:t></m:r></m:e>
                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>ρ</m:t></m:r></m:e>
                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>)·</m:t></m:r>
            <m:f>
                <m:num><m:r><m:t>k</m:t></m:r></m:num>
                <m:den>
                    <m:rad>
                        <m:radPr><m:degHide m:val="1"/></m:radPr>
                        <m:deg/>
                        <m:e>
                            <m:sSub>
                                <m:e><m:r><m:t>t</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>s</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:e>
                    </m:rad>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # Rg Sverak: Rg = ρ · [1/Lt + 1/√(20A) · (1 + 1/(1+h√(20/A)))]
    "rg_sverak": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>R</m:t></m:r></m:e>
                <m:sub><m:r><m:t>g</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = ρ·</m:t></m:r>
            <m:d>
                <m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr>
                <m:e>
                    <m:f>
                        <m:num><m:r><m:t>1</m:t></m:r></m:num>
                        <m:den>
                            <m:sSub>
                                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                                <m:sub><m:r><m:t>t</m:t></m:r></m:sub>
                            </m:sSub>
                        </m:den>
                    </m:f>
                    <m:r><m:t> + </m:t></m:r>
                    <m:f>
                        <m:num><m:r><m:t>1</m:t></m:r></m:num>
                        <m:den>
                            <m:rad>
                                <m:radPr><m:degHide m:val="1"/></m:radPr>
                                <m:deg/>
                                <m:e><m:r><m:t>20·A</m:t></m:r></m:e>
                            </m:rad>
                        </m:den>
                    </m:f>
                    <m:r><m:t>·</m:t></m:r>
                    <m:d>
                        <m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/></m:dPr>
                        <m:e>
                            <m:r><m:t>1 + </m:t></m:r>
                            <m:f>
                                <m:num><m:r><m:t>1</m:t></m:r></m:num>
                                <m:den>
                                    <m:r><m:t>1 + h·</m:t></m:r>
                                    <m:rad>
                                        <m:radPr><m:degHide m:val="1"/></m:radPr>
                                        <m:deg/>
                                        <m:e><m:r><m:t>20/A</m:t></m:r></m:e>
                                    </m:rad>
                                </m:den>
                            </m:f>
                        </m:e>
                    </m:d>
                </m:e>
            </m:d>
        </m:oMath>
    </m:oMathPara>""",

    # R1 Schwarz
    "rg_schwarz_r1": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>R</m:t></m:r></m:e>
                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num><m:r><m:t>ρ</m:t></m:r></m:num>
                <m:den>
                    <m:r><m:t>π·</m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>L</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
                    </m:sSub>
                </m:den>
            </m:f>
            <m:r><m:t>·[ ln(2</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>/a') + </m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>k</m:t></m:r></m:e>
                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>/√A − </m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>k</m:t></m:r></m:e>
                <m:sub><m:r><m:t>2</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> ]</m:t></m:r>
        </m:oMath>
    </m:oMathPara>""",

    # R2 Schwarz
    "rg_schwarz_r2": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>R</m:t></m:r></m:e>
                <m:sub><m:r><m:t>2</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num><m:r><m:t>ρ</m:t></m:r></m:num>
                <m:den>
                    <m:r><m:t>2π·n·</m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>L</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>r</m:t></m:r></m:sub>
                    </m:sSub>
                </m:den>
            </m:f>
            <m:r><m:t>·[ ln(8</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>r</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>/d) − 1 + 2·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>k</m:t></m:r></m:e>
                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>r</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·(√n−1)²/√A ]</m:t></m:r>
        </m:oMath>
    </m:oMathPara>""",

    # Rm Schwarz
    "rg_schwarz_rm": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>R</m:t></m:r></m:e>
                <m:sub><m:r><m:t>m</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num><m:r><m:t>ρ</m:t></m:r></m:num>
                <m:den>
                    <m:r><m:t>π·</m:t></m:r>
                    <m:sSub>
                        <m:e><m:r><m:t>L</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
                    </m:sSub>
                </m:den>
            </m:f>
            <m:r><m:t>·[ ln(2</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>/</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>r</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>) + </m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>k</m:t></m:r></m:e>
                <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>·</m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>L</m:t></m:r></m:e>
                <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t>/√A − </m:t></m:r>
            <m:sSub>
                <m:e><m:r><m:t>k</m:t></m:r></m:e>
                <m:sub><m:r><m:t>2</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> + 1 ]</m:t></m:r>
        </m:oMath>
    </m:oMathPara>""",

    # Rg Schwarz combinada
    "rg_schwarz": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub>
                <m:e><m:r><m:t>R</m:t></m:r></m:e>
                <m:sub><m:r><m:t>g</m:t></m:r></m:sub>
            </m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num>
                    <m:sSub><m:e><m:r><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t>·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>2</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t> − </m:t></m:r>
                    <m:sSubSup>
                        <m:e><m:r><m:t>R</m:t></m:r></m:e>
                        <m:sub><m:r><m:t>m</m:t></m:r></m:sub>
                        <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
                    </m:sSubSup>
                </m:num>
                <m:den>
                    <m:sSub><m:e><m:r><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t> + </m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>2</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t> − 2·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # Em = ρ · Km · Ki · IG / Lm
    "em": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num>
                    <m:r><m:t>ρ·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t>·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t>·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>I</m:t></m:r></m:e><m:sub><m:r><m:t>G</m:t></m:r></m:sub></m:sSub>
                </m:num>
                <m:den>
                    <m:sSub><m:e><m:r><m:t>L</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # Es = ρ · Ks · Ki · IG / Ls
    "es": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub>
            <m:r><m:t> = </m:t></m:r>
            <m:f>
                <m:num>
                    <m:r><m:t>ρ·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t>·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>
                    <m:r><m:t>·</m:t></m:r>
                    <m:sSub><m:e><m:r><m:t>I</m:t></m:r></m:e><m:sub><m:r><m:t>G</m:t></m:r></m:sub></m:sSub>
                </m:num>
                <m:den>
                    <m:sSub><m:e><m:r><m:t>L</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub>
                </m:den>
            </m:f>
        </m:oMath>
    </m:oMathPara>""",

    # Em ≤ Etoque  ∧  Es ≤ Epasso
    "criterio": f"""<m:oMathPara {M_NS}>
        <m:oMathParaPr><m:jc m:val="center"/></m:oMathParaPr>
        <m:oMath>
            <m:sSub><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>
            <m:r><m:t> ≤ </m:t></m:r>
            <m:sSub><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sub><m:r><m:t>toque</m:t></m:r></m:sub></m:sSub>
            <m:r><m:t>     e     </m:t></m:r>
            <m:sSub><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub>
            <m:r><m:t> ≤ </m:t></m:r>
            <m:sSub><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sub><m:r><m:t>passo</m:t></m:r></m:sub></m:sSub>
        </m:oMath>
    </m:oMathPara>""",
}


# ============================================================
# FUNÇÕES PÚBLICAS
# ============================================================

def insere_equacao_no_paragrafo(doc, identificador: str):
    """
    Cria um novo parágrafo no documento contendo a equação OMML.

    O <m:oMathPara> é envolvido em <w:p> conforme exigido pelo schema OOXML.

    Args:
        doc: documento python-docx
        identificador: chave em EQUACOES_OMML

    Raises:
        KeyError: se identificador não existir
    """
    if identificador not in EQUACOES_OMML:
        raise KeyError(
            f"Equação '{identificador}' não definida. "
            f"Disponíveis: {list(EQUACOES_OMML.keys())}"
        )

    xml = EQUACOES_OMML[identificador].strip()
    omath = parse_xml(xml)

    # Cria parágrafo e injeta a equação dentro
    par = doc.add_paragraph()
    par._p.append(omath)
