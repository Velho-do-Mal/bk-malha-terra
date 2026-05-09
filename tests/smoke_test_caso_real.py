"""
tests/smoke_test_caso_real.py
=============================

Simulação fim-a-fim de um caso real BK (SE 138 kV típica).
Não é teste unitário - é demonstração da pipeline completa.

Rodar:
    python tests/smoke_test_caso_real.py
"""

from core.condutor import Material, dimensiona_condutor
from core.corrente import corrente_malha_ig
from core.resistencia import GeometriaMalha, calcula_resistencia_e_tensoes
from core.solo import MedicaoWenner, estratifica_2_camadas, rho_equivalente_simplificado
from core.tensoes import calcula_tensoes_admissiveis
from core.verificacao import itera_num_hastes, verifica_malha


def simula_caso_se_138kv():
    print("=" * 70)
    print("SE DISTRIBUIÇÃO 138/13.8 kV - Caso fictício BK")
    print("=" * 70)

    # 1. SOLO - medições Wenner
    medicoes = [
        MedicaoWenner(1.0, 47.7),
        MedicaoWenner(2.0, 22.3),
        MedicaoWenner(4.0, 9.5),
        MedicaoWenner(8.0, 3.7),
        MedicaoWenner(16.0, 1.4),
        MedicaoWenner(32.0, 0.55),
    ]
    solo = estratifica_2_camadas(medicoes)
    rho_eq = rho_equivalente_simplificado(solo, comprimento_haste=3.0)

    print(f"\n[1] SOLO ESTRATIFICADO (NBR 7117 + Sunde):")
    print(f"    ρ₁  = {solo.rho1:7.1f} Ω·m")
    print(f"    ρ₂  = {solo.rho2:7.1f} Ω·m")
    print(f"    h₁  = {solo.h1:7.2f} m")
    print(f"    K   = {solo.coef_reflexao:7.3f}")
    print(f"    erro RMS ajuste = {solo.erro_rms:.2f}%")
    print(f"    ρ_equivalente   = {rho_eq:.1f} Ω·m")

    # 2. CORRENTE DE MALHA
    corrente = corrente_malha_ig(
        i_falta_3i0_a=8000,
        sf_div_corrente=0.6,
        xr_ratio=12,
        tf_s=0.5,
    )
    print(f"\n[2] CORRENTE DE MALHA (IEEE 80 §15):")
    print(f"    3I₀ = {corrente.i_falta_3i0_a:.0f} A")
    print(f"    Sf  = {corrente.sf_div_corrente}")
    print(f"    Df  = {corrente.df_decremento:.4f}")
    print(f"    IG  = {corrente.ig_a:.0f} A")

    # 3. CONDUTOR
    cond = dimensiona_condutor(
        corrente_a=corrente.ig_a,
        tempo_s=0.5,
        material=Material.COBRE_NU,
        temperatura_max_c=250,  # parafusado
    )
    print(f"\n[3] CONDUTOR (Sverak, IEEE 80 eq. 37):")
    print(f"    A calculada = {cond.bitola_calculada_mm2:.2f} mm²")
    print(f"    A adotada   = {cond.bitola_adotada_mm2:.0f} mm²")

    # 4. TENSÕES ADMISSÍVEIS
    tensoes = calcula_tensoes_admissiveis(
        rho_solo=solo.rho1,
        rho_brita=3000,
        h_brita=0.10,
        tempo_s=0.5,
        peso_kg=50,
    )
    print(f"\n[4] TENSÕES ADMISSÍVEIS (50 kg, brita 100mm 3000Ω·m):")
    print(f"    Cs              = {tensoes.cs_brita:.3f}")
    print(f"    Etoque admissível = {tensoes.etoque_v:.1f} V")
    print(f"    Epasso admissível = {tensoes.epasso_v:.1f} V")

    # 5. GEOMETRIA INICIAL E ITERAÇÃO
    geom = GeometriaMalha(
        largura_m=40, comprimento_m=50, profundidade_m=0.5,
        espac_malha_m=5, bitola_cabo_mm2=cond.bitola_adotada_mm2,
        haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=4,
    )
    print(f"\n[5] GEOMETRIA INICIAL:")
    print(f"    Área = {geom.area_m2} m² ({geom.largura_m}×{geom.comprimento_m})")
    print(f"    h    = {geom.profundidade_m} m, D = {geom.espac_malha_m} m")
    print(f"    Lc   = {geom.comprimento_cabos_m():.1f} m de cabo")

    # 6. ITERA Nº DE HASTES
    iteracao = itera_num_hastes(
        geom_inicial=geom,
        rho_eq=rho_eq,
        ig_a=corrente.ig_a,
        etoque_adm_v=tensoes.etoque_v,
        epasso_adm_v=tensoes.epasso_v,
        n_hastes_min=4,
        n_hastes_max=80,
        incremento=4,
    )

    res = iteracao.resultado
    verif = iteracao.verificacao

    print(f"\n[6] ITERAÇÃO ({iteracao.iteracoes} iterações):")
    for h in iteracao.historico:
        marca = "✓" if h["atende"] else " "
        print(f"    {marca} n={h['n_hastes']:3d} | Rg={h['rg_ohm']:5.2f}Ω | "
              f"Em={h['em_v']:6.0f}V | Es={h['es_v']:6.0f}V")

    print(f"\n[7] RESULTADOS FINAIS:")
    print(f"    nº hastes adotado = {iteracao.geometria_final.num_hastes}")
    print(f"    Rg Sverak  = {res.rg_sverak_ohm:.3f} Ω")
    print(f"    Rg Schwarz = {res.rg_schwarz_ohm:.3f} Ω")
    print(f"    GPR        = {res.gpr_v:.0f} V")
    print(f"    Em         = {res.em_v:.0f} V (admissível {tensoes.etoque_v:.0f})")
    print(f"    Es         = {res.es_v:.0f} V (admissível {tensoes.epasso_v:.0f})")
    print(f"    Margem toque = {verif.margem_toque_pct:+.1f}%")
    print(f"    Margem passo = {verif.margem_passo_pct:+.1f}%")

    print(f"\n[8] VEREDITO: {'✓ ATENDE' if verif.atende_geral else '✗ NÃO ATENDE'}")
    print("=" * 70)


if __name__ == "__main__":
    simula_caso_se_138kv()
