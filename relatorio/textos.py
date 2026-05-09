"""
relatorio/textos.py
===================

Textos técnicos da metodologia, conclusão e referências.
As equações são marcadas com a sintaxe especial:

    [[EQ:identificador]]

e o gerador substitui por equações OMML nativas do Word durante a
renderização. Os identificadores correspondem a chaves do dict
EQUACOES_OMML em equacoes.py.
"""

# ============================================================
# OBJETIVO
# ============================================================

OBJETIVO_TEMPLATE = """\
Este documento apresenta a memória de cálculo da malha de aterramento da \
subestação do projeto **{nome_projeto}** (cód. {numero_projeto}, revisão R{revisao}), \
de propriedade do cliente **{cliente}**, com atendimento à concessionária \
**{concessionaria}**.

O objetivo do estudo é dimensionar a malha de aterramento de forma a garantir \
a segurança de pessoas e equipamentos durante a ocorrência de uma falta \
fase-terra na subestação, em conformidade com:

- IEEE Std 80-2013 — *Guide for Safety in AC Substation Grounding*;
- ABNT NBR 15751:2013 — *Sistemas de aterramento de subestações*;
- ABNT NBR 7117:2020 — *Medição da resistividade e determinação da estratificação do solo*.

Os critérios verificados são:

- Tensão de toque calculada (Em) ≤ tensão de toque admissível pelo corpo humano;
- Tensão de passo calculada (Es) ≤ tensão de passo admissível;
- Adequação térmica do condutor da malha (Sverak);
- Resistência total da malha (Rg) compatível com a operação do sistema de proteção.

Responsável técnico: {responsavel} — CREA {crea_responsavel}.
Data do cálculo: {data_calculo}.
"""


# ============================================================
# METODOLOGIA - subseções com marcadores de equação
# ============================================================
# Sintaxe: [[EQ:nome]] indica ponto onde inserir equação OMML.

METODOLOGIA_INTRO = """\
A metodologia adotada segue o procedimento da IEEE Std 80-2013 §16.4 \
(*Design procedure*), que estabelece um fluxograma iterativo: parte-se da \
caracterização do solo, calcula-se a corrente máxima de malha (IG), \
dimensiona-se o condutor, determinam-se as tensões admissíveis, calcula-se \
a resistência da malha (Rg) e as tensões reais de malha (Em) e de passo (Es), \
verificando-se se atendem aos critérios de segurança. Se não atenderem, \
ajusta-se a geometria (espaçamento, número de hastes, profundidade) e \
repete-se até a convergência.
"""

METODOLOGIA_SOLO = """\
**2.1. Caracterização do solo (Wenner + estratificação)**

A resistividade aparente do solo é medida em campo pelo método de Wenner \
(NBR 7117 §6.2), com quatro eletrodos igualmente espaçados em linha reta \
e profundidade de cravação muito menor que o espaçamento *a*. A leitura \
do terrômetro é a resistência R, e a resistividade aparente é:

[[EQ:wenner]]

Como o solo real é estratificado, ajusta-se a um modelo de duas camadas \
(camada superior com ρ₁ e espessura h₁; camada inferior com ρ₂ e \
profundidade infinita). A função teórica de Sunde para a resistividade \
aparente é:

[[EQ:sunde]]

onde K é o coeficiente de reflexão entre as camadas:

[[EQ:k_reflexao]]

Os parâmetros ρ₁, ρ₂ e h₁ são obtidos por minimização do erro quadrático \
relativo entre ρ_a teórico e ρ_a medido. Para os cálculos posteriores que \
assumem solo homogêneo (Sverak/Schwarz), adota-se uma resistividade \
equivalente ρ_eq por média ponderada na profundidade da haste.
"""

METODOLOGIA_CORRENTE = """\
**2.2. Corrente máxima de malha (IG)**

A corrente que efetivamente escoa pela malha durante uma falta fase-terra \
é (IEEE 80 eq. 70):

[[EQ:ig]]

onde 3I₀ é a corrente simétrica de falta fase-terra no barramento da SE, \
Sf é o fator de divisão de corrente (Tabela 10 IEEE 80), que considera \
a parcela escoada por cabos para-raios, neutros e malhas adjacentes; e \
Df é o fator de decremento, que contabiliza a componente DC durante o \
intervalo de eliminação da falta (eq. 79):

[[EQ:df]]

com Ta = X/(ω·R) sendo a constante de tempo DC e tf o tempo de eliminação \
da falta.
"""

METODOLOGIA_CONDUTOR = """\
**2.3. Dimensionamento do condutor (Sverak)**

A seção mínima do condutor da malha, de modo que a temperatura não \
ultrapasse o limite admissível pela conexão, é dada por (IEEE 80 eq. 37):

[[EQ:sverak_condutor]]

onde αr, ρr, K₀ e TCAP são propriedades do material (Tabela 1 IEEE 80), \
Tm é a temperatura máxima admissível pela conexão (250 °C para parafusada, \
450 °C para compressão, 1083 °C para solda exotérmica em cobre), Ta é a \
temperatura ambiente e tc é o tempo de eliminação da falta. Por robustez \
mecânica, a BK adota seção mínima prática de 50 mm² independentemente do \
resultado calculado.
"""

METODOLOGIA_TENSOES_ADM = """\
**2.4. Tensões admissíveis pelo corpo humano**

O critério de Dalziel (IEEE 80 §8.3) estabelece a corrente máxima \
admissível pelo corpo humano em função do tempo de exposição ts:

[[EQ:dalziel]]

onde k = 0,116 √A·s para pessoas de 50 kg e k = 0,157 √A·s para 70 kg.

Considerando a resistência do corpo Rb = 1000 Ω e a presença de uma camada \
superficial de brita com resistividade ρs e espessura hs, o fator de \
redução Cs é (eq. 27):

[[EQ:cs]]

As tensões de toque e de passo admissíveis são (eqs. 30-33):

[[EQ:etoque_adm]]

[[EQ:epasso_adm]]

A camada de brita tipicamente adotada possui hs = 0,10 m e ρs = 3000 Ω·m \
(brita seca, valor padrão IEEE 80).
"""

METODOLOGIA_RG = """\
**2.5. Resistência da malha (Sverak e Schwarz)**

A resistência da malha enterrada à profundidade h em solo de \
resistividade ρ é estimada por duas formulações:

**Sverak** (IEEE 80 eq. 52, simplificada):

[[EQ:rg_sverak]]

onde Lt é o comprimento total enterrado (cabos + hastes) e A é a área \
ocupada pela malha.

**Schwarz** (IEEE 80 §14.3, considera explicitamente as hastes):

[[EQ:rg_schwarz_r1]]

[[EQ:rg_schwarz_r2]]

[[EQ:rg_schwarz_rm]]

[[EQ:rg_schwarz]]

onde k₁ e k₂ são coeficientes geométricos (Fig. 25 IEEE 80) função da \
razão de lados e da profundidade. Adota-se o valor de Schwarz por ser \
mais preciso.
"""

METODOLOGIA_EM_ES = """\
**2.6. Tensões de malha (Em) e de passo (Es)**

A tensão de malha Em (máxima diferença de potencial dentro da retícula \
da malha) e a tensão de passo Es (máxima diferença entre dois pontos \
afastados de 1 m) são calculadas por (eqs. 80 e 92):

[[EQ:em]]

[[EQ:es]]

com Km, Ks os fatores de tensão de malha e de passo (eqs. 81 e 92), \
função da geometria (D, h, d, n); Ki = 0,644 + 0,148·n o fator de \
irregularidade (eq. 89); e Lm, Ls os comprimentos efetivos do condutor \
enterrado considerando contribuição das hastes (eqs. 88 e 93).

A verificação de adequação é:

[[EQ:criterio]]
"""

METODOLOGIA_DETALHES_PROJETO = """\
**2.7. Considerações de projeto e prática construtiva**

**Aterramento da cerca perimetral**
A cerca metálica deve ser aterrada com afastamento mínimo de 1 m da \
malha (IEEE 80 §17.3), com conexões à malha em pelo menos a cada 5-6 \
metros e nos cantos. A camada de brita deve ser estendida 1 m além da \
cerca para mitigar tensões de toque transferidas. Em SE com cerca \
relativamente próxima da malha, recomenda-se cabo perimetral adicional \
fora da malha principal a 1 m de afastamento, conectado à cerca.

**Aterramento de canaletas e eletrodutos**
Canaletas metálicas de cabos devem ser interligadas longitudinalmente \
com cabo de cobre nu, e o conjunto conectado à malha em pelo menos dois \
pontos por trecho. Eletrodutos metálicos enterrados devem ter equalização \
nas extremidades.

**Posicionamento das hastes**
A localização preferencial das hastes obedece a seguinte ordem \
(IEEE 80 §16.6): (i) cantos da malha — onde os gradientes de potencial \
são maiores; (ii) pontos médios das bordas — segunda região de maior \
gradiente; (iii) próximo a equipamentos com maior corrente injetada \
(transformadores, para-raios, neutros aterrados); (iv) distribuição \
uniforme nas bordas; e (v) interior da malha apenas após esgotadas as \
posições anteriores. O espaçamento mínimo entre hastes deve ser igual \
ou maior que o comprimento da haste, para evitar sobreposição das zonas \
de influência (NBR 15751 §6.3).

**Aterramento em taludes e fora da área britada**
Quando parte da SE estiver em talude ou fora da área coberta por \
brita, a tensão de toque admissível cai significativamente (Cs = 1, sem \
o fator redutor da brita). Recomenda-se: (i) estender a brita até o pé \
do talude sempre que possível; (ii) instalar cabo contrapeso paralelo \
ao talude; (iii) sinalização e cercamento da área não britada; (iv) \
verificação específica do cálculo nessa região, podendo exigir malha \
auxiliar ou redução do espaçamento D.

**Aterramento de chaves seccionadoras**
Chaves seccionadoras com operação local apresentam risco específico \
de tensão de toque transferida pelo cabo de comando metálico. Em alguns \
arranjos, recomenda-se aterramento independente para a estrutura de \
operação (esteira de pé do operador), com brita estendida e \
equipotencialização do operador. A integração à malha principal deve \
ser avaliada em função do estudo de tensão transferida — pode ser \
necessário cabo de comando isolado ou supressor de surto na haste de \
acionamento.

**Equalização de potencial**
Todas as bases de equipamentos, painéis, suportes metálicos, portões \
e elementos condutores expostos devem ser conectados à malha por dois \
caminhos independentes (redundância). Pisos elevados, salas de painéis \
e casas de comando devem possuir malha de equalização interna conectada \
à malha principal em pelo menos dois pontos.
"""


# ============================================================
# CONCLUSÃO
# ============================================================

CONCLUSAO_ATENDE = """\
Os resultados obtidos demonstram que a malha de aterramento dimensionada \
para a SE em estudo **atende integralmente** aos critérios de segurança \
estabelecidos pela IEEE Std 80-2013 e pela NBR 15751:

- A tensão de malha calculada (Em = {em:.0f} V) é inferior à tensão de \
toque admissível pelo corpo humano ({etoque_adm:.0f} V), com margem de \
{margem_toque:.1f}%;
- A tensão de passo calculada (Es = {es:.0f} V) é inferior à tensão de \
passo admissível ({epasso_adm:.0f} V), com margem de {margem_passo:.1f}%;
- A resistência total da malha (Rg = {rg:.2f} Ω) é compatível com a \
operação do sistema de proteção;
- O condutor adotado ({bitola_adotada:.0f} mm²) atende ao critério térmico \
de Sverak para a corrente IG = {ig:.0f} A durante {tempo:.2f} s.

Recomenda-se a execução conforme as práticas construtivas descritas na \
seção 2.7, com especial atenção ao aterramento da cerca perimetral, \
canaletas, equipamentos e regiões fora da área britada. Após a execução, \
deve-se realizar medição da resistência da malha pelo método da queda de \
potencial (NBR 15749), com valor de aceitação compatível com o calculado.
"""

CONCLUSAO_NAO_ATENDE = """\
Os resultados obtidos demonstram que a configuração proposta para a malha \
de aterramento da SE em estudo **NÃO atende** aos critérios de segurança \
da IEEE Std 80-2013 nas seguintes condições:

- Tensão de malha calculada Em = {em:.0f} V (admissível {etoque_adm:.0f} V) \
— margem {margem_toque:+.1f}%;
- Tensão de passo calculada Es = {es:.0f} V (admissível {epasso_adm:.0f} V) \
— margem {margem_passo:+.1f}%.

São recomendadas as seguintes medidas para adequação:

1. Reduzir o espaçamento da malha principal (D), aumentando a densidade de cabos;
2. Aumentar a profundidade de enterramento da malha (h), até o limite \
construtivo (geralmente 0,5–0,8 m);
3. Aumentar a espessura ou a resistividade da brita superficial;
4. Verificar o tempo de eliminação real do sistema de proteção — \
proteções primárias mais rápidas reduzem significativamente as tensões \
admissíveis exigidas;
5. Avaliar a expansão da área da malha (com cabo perimetral externo) ou \
malha auxiliar.

Recomenda-se nova iteração do projeto antes da emissão final do estudo.
"""


# ============================================================
# REFERÊNCIAS BIBLIOGRÁFICAS
# ============================================================

REFERENCIAS = [
    "IEEE Std 80-2013. *IEEE Guide for Safety in AC Substation Grounding*. "
    "Institute of Electrical and Electronics Engineers, New York, 2013.",
    "ABNT NBR 15751:2013. *Sistemas de aterramento de subestações — Requisitos*. "
    "Associação Brasileira de Normas Técnicas, Rio de Janeiro, 2013.",
    "ABNT NBR 7117:2020. *Medição da resistividade e determinação da "
    "estratificação do solo*. Associação Brasileira de Normas Técnicas, "
    "Rio de Janeiro, 2020.",
    "ABNT NBR 5419:2015. *Proteção contra descargas atmosféricas* "
    "(Partes 1 a 4). ABNT, Rio de Janeiro, 2015.",
    "ABNT NBR 15749:2009. *Medição de resistência de aterramento e de "
    "potenciais na superfície do solo em sistemas de aterramento*. "
    "ABNT, Rio de Janeiro, 2009.",
    "MAMEDE FILHO, J. *Manual de Equipamentos Elétricos*. 4ª ed. "
    "Rio de Janeiro: LTC, 2013.",
    "KINDERMANN, G.; CAMPAGNOLO, J. M. *Aterramento Elétrico*. "
    "5ª ed. Porto Alegre: Sagra Luzzato, 2002.",
    "SVERAK, J. G. \"Simplified Analysis of Electrical Gradients above a Ground "
    "Grid\". IEEE Transactions on Power Apparatus and Systems, vol. PAS-103, "
    "n. 1, pp. 7-25, 1984.",
    "SUNDE, E. D. *Earth Conduction Effects in Transmission Systems*. "
    "New York: Dover Publications, 1968.",
]
