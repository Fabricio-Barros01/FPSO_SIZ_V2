"""Auditoria numérica independente do balanço (port de auditoria_independente()).

Recalcula as grandezas derivadas por álgebra INDEPENDENTE da usada no motor: Standing na
forma logarítmica, °C→°F como T·1,8+32, cargas a partir de Ċ ΔT por corrente, BSW e
salinidade pelas definições. Por isso este módulo NÃO importa modelo, balancos nem
propriedades (há teste). Ele só lê o resultado: correntes, T, cargas, ρ, cp e gás.

Cada verificação devolve o maior |desvio| absoluto entre modelo e recálculo nos casos.
As expressões seguem a ordem de operações do original (paridade com o oráculo F1).
"""
import math

from fpso_siz.balanco.dados import constantes
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import HORAS_POR_DIA, SEGUNDOS_POR_DIA, SEGUNDOS_POR_HORA, c_para_f_linear, c_para_k

COMP = ("O", "W", "D", "G")  # declarado aqui de propósito: independência do motor
LIQ = ("O", "W", "D")
GAS_VRU = ("C-04", "C-09", "C-17")


def auditar(resultados, dados, prem):
    """Lista de verificações {id, verificacao, base, unidade, max_desvio_abs}, na ordem do
    catálogo (config/auditoria.toml). Verificações sem caso aplicável são omitidas."""
    const = constantes()
    ks = const.standing
    T_ref = const.T_ref_C
    P = prem
    topo = carregar("topologia_db.toml")
    g_in, g_out = topo["global_in"], topo["global_out"]
    pior = {}

    def track(chave, v):
        atual = pior.get(chave)
        pior[chave] = max(atual, abs(v)) if atual is not None else abs(v)

    casos = dados.casos
    VM2 = const.R * c_para_k(dados.T_std_C) / dados.P_std_kPa
    track("identidade_liquido", max(abs(c["oil_sm3d"] + (c["liquid_sm3d"] - c["oil_sm3d"]) - c["liquid_sm3d"])
                                    for c in casos))
    track("identidade_gas", max(abs(c["total_gas_sm3d"] - c["produced_gas_sm3d"] - c["lift_gas_sm3d"]
                                    - c["transferred_gas_sm3d"]) for c in casos))
    track("soma_composicao", max(abs(sum(v.values()) - 1.0) for v in dados.composicoes.values()))
    track("volume_molar", VM2 - resultados[0].VM)

    for r in resultados:
        c = r.caso
        gp, api, st, cp, du, T, rho = r.gp, r.api, r.streams, r.cp, r.duties, r.T, r.rho
        rhoO = (const.api_a / (const.api_b + api)) * const.rho_agua_15_6C
        track("rho_oleo_api", rhoO - rho["O"])
        track("vazao_massica_C01", max(
            abs(c["oil_sm3d"] * rhoO / SEGUNDOS_POR_DIA - st["C-01"]["O"]),
            abs((c["liquid_sm3d"] - c["oil_sm3d"]) * P["rho_W"] / SEGUNDOS_POR_DIA - st["C-01"]["W"]),
            abs((c["produced_gas_sm3d"] + c["lift_gas_sm3d"]) * (gp["MW"] / VM2) / SEGUNDOS_POR_DIA - st["C-01"]["G"])))
        track("vazao_molar_gas", (c["produced_gas_sm3d"] + c["lift_gas_sm3d"]) / VM2 / HORAS_POR_DIA
              - st["C-01"]["G"] * SEGUNDOS_POR_HORA / gp["MW"])

        def rs(Pk, T_):  # Standing na forma logarítmica
            Ppsi = Pk / ks.kPa_por_psia
            TF = c_para_f_linear(T_)
            return (gp["gamma"] * 10 ** (ks.expoente * (math.log10(Ppsi / ks.a + ks.b) + (ks.c_api * api - ks.c_T * TF)))
                    * ks.Sm3_Sm3_por_scf_bbl)

        dF = rs(P["P_FWKO"], T["C-03"]) - rs(dados.P_std_kPa, T_ref)
        dD = rs(P["P_D1"], T["C-08"]) - rs(dados.P_std_kPa, T_ref)
        track("gas_por_estagio", max(
            abs((dF - dD) * c["oil_sm3d"] - r.gas["G_D1"]),
            abs(dD * c["oil_sm3d"] - r.gas["G_D2"]),
            abs(c["produced_gas_sm3d"] + c["lift_gas_sm3d"] - dF * c["oil_sm3d"] - r.gas["G_F"])))

        mi = sum(sum(st[x].values()) for x in g_in)
        mo = sum(sum(st[x].values()) for x in g_out)
        track("massa_global", mi - mo)

        def Hs(x):
            return sum(st[x][k] * cp[k] for k in COMP) * (T[x] - T_ref)

        Wt = du["W_Bo"] + du["W_B1"] + du["W_B2"]
        track("energia_global", Hs("C-01") + Hs("C-14") + du["Q_H"] + du["Q_D"] + Wt
              - sum(Hs(x) for x in g_out) - du["Q_C"])

        Cc = sum(st["C-06"][k] * cp[k] for k in COMP)
        Ch = sum(st["C-22"][k] * cp[k] for k in COMP)
        track("cargas_termicas", max(
            abs(Cc * (T["C-07"] - T["C-06"]) - Ch * (T["C-22"] - T["C-23"])),
            abs(Cc * (T["C-08"] - T["C-07"]) - du["Q_H"]),
            abs(sum(st["C-14"][k] * cp[k] for k in COMP) * (P["T_dil_out"] - P["T_dil_in"]) - du["Q_D"]),
            abs(Ch * (T["C-23"] - T["C-24"]) - du["Q_C"])))

        def Vd(x):
            return sum(st[x][k] / rho[k] for k in LIQ)

        track("potencias_bombas", max(
            abs(Vd("C-21") * (P["P_pump_oil"] - P["P_D2"]) / P["eta_pump"] - du["W_Bo"]),
            abs(Vd("C-12") * (P["P_rec"] - P["P_D1"]) / P["eta_pump"] - du["W_B1"]),
            abs(Vd("C-19") * (P["P_rec"] - P["P_D2"]) / P["eta_pump"] - du["W_B2"])))

        for k in COMP:
            track("residuo_componente", sum(st[x][k] for x in g_in) - sum(st[x][k] for x in g_out))

        for i in ("CO2", "H2S"):
            y = gp["y"][i]
            track("molar_CO2_H2S", y * st["C-01"]["G"] / gp["MW"] * SEGUNDOS_POR_HORA
                  - y * sum(st[x]["G"] for x in GAS_VRU) / gp["MW"] * SEGUNDOS_POR_HORA)

        def lv(x):  # água + diluição, m³/d
            return (st[x]["W"] / rho["W"] + st[x]["D"] / rho["D"]) * SEGUNDOS_POR_DIA

        def ov(x):
            return st[x]["O"] / rho["O"] * SEGUNDOS_POR_DIA

        def bs(x):
            return lv(x) / (lv(x) + ov(x)) if lv(x) + ov(x) > 0 else 0.0

        track("bsw_saida", max(
            abs(bs("C-06") - r.BSW_F),
            abs(bs("C-11") - (P["BSW_pre"] if lv("C-11") > 0 else 0.0)),
            abs(bs("C-21") - (P["BSW_t"] if lv("C-21") > 0 else 0.0))))
        if lv("C-03") > 0:
            # η_A = máx(η_padrão; η_req) e BSW_C06 ≤ BSW_lim, pelas definições, a partir das correntes
            eta = lv("C-05") / lv("C-03")
            eta_req = 1 - P["BSW_F"] / (1 - P["BSW_F"]) * ov("C-06") / lv("C-03")
            track("eficiencia_fwko", max(abs(eta - max(P["eta_F"], eta_req)), max(0.0, bs("C-06") - P["BSW_F"])))
        if lv("C-11") > 0:
            Sres = P["S_W"] * lv("C-11") / (lv("C-11") + r.gas["Dv"])
            track("salinidade_oleo", Sres * bs("C-21") - P["S_spec"])

    return [dict(id=chave, verificacao=e["verificacao"], base=e["base"], unidade=e["unidade"],
                 max_desvio_abs=pior[chave])
            for chave, e in carregar("auditoria.toml").items() if chave in pior]
