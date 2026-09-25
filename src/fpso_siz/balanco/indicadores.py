"""Grandezas derivadas do balanço exibidas nos relatórios (memorial, envelopes).

Vazões por fase, vazão real de gás, vazões molares, BSW, eficiências, envelopes,
casos críticos, fechamento e sensibilidade. É física/definição, não formatação: por
isso mora no núcleo e a camada de saída só apresenta. As expressões seguem a ordem de
operações do script de referência (paridade byte a byte do memorial).
"""
from fpso_siz.balanco.balancos import balanco_bloco, balanco_global, topologia
from fpso_siz.balanco.dados import constantes, pocos
from fpso_siz.balanco.modelo import COMP, LIQUIDOS, resolver_caso
from fpso_siz.balanco.propriedades import gas_props, poco_do_fluido, standing_rs
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import HORAS_POR_DIA, POR_CENTO, PPM_POR_UNIDADE, SEGUNDOS_POR_HORA, c_para_k

GAS_VRU = ("C-04", "C-09", "C-17")


def criterios():
    return carregar("constantes.toml")["criterios"]


# ------------------------------------------------------------------ por corrente
def q(r, sid, c):
    """Vazão volumétrica padrão do componente c na corrente (m³/d; Sm³/d para gás)."""
    return r.vol(r.streams[sid], c)


def q_agua(r, sid):
    """Água produzida + diluição na corrente, m³/d."""
    return q(r, sid, "W") + q(r, sid, "D")


def m(r, sid):
    """Vazão mássica total da corrente, kg/s."""
    return sum(r.streams[sid].values())


def v_liquido(r, sid):
    """Vazão volumétrica de líquido na condição padrão, m³/s."""
    s = r.streams[sid]
    return sum(s[c] / r.rho[c] for c in LIQUIDOS)


def bsw_pct(r, sid):
    ww = q_agua(r, sid)
    o = q(r, sid, "O")
    return POR_CENTO * ww / (ww + o) if ww + o > 0 else 0


def q_real_gas(r, chave, P, T, dados):
    """Vazão real de gás (m³/h) com Z = 1 (P-39)."""
    return r.gas[chave] * dados.P_std_kPa / P * c_para_k(T) / c_para_k(dados.T_std_C) / HORAS_POR_DIA


def molares_acidos(r):
    """{CO2|H2S: (entrada C-01, saída no gás, erro relativo)} em kmol/h."""
    y, Mg, st = r.gp["y"], r.gp["MW"], r.streams
    out = {}
    for i in ("CO2", "H2S"):
        nin = y[i] * st["C-01"]["G"] / Mg * SEGUNDOS_POR_HORA
        nout = y[i] * sum(st[s]["G"] for s in GAS_VRU) / Mg * SEGUNDOS_POR_HORA
        out[i] = (nin, nout, abs(nin - nout) / nin)
    return out


def co2_molar(r):
    return r.gp["y"]["CO2"] * r.streams["C-01"]["G"] / r.gp["MW"] * SEGUNDOS_POR_HORA


def h2s_molar(r):
    return r.gp["y"]["H2S"] * r.streams["C-01"]["G"] / r.gp["MW"] * SEGUNDOS_POR_HORA


# ------------------------------------------------------------------ eficiências
def eta_gas_fwko(r):
    return r.gas["G_F"] / r.gas["G_in"]


def eta_gas_v001(r):
    return r.gas["G_D1"] / (r.gas["G_D1"] + r.gas["G_D2"])


def eta_agua(r, saida, entrada):
    """Q_{A+D,saída}/Q_{A+D,entrada}; None se não há água a separar."""
    return q_agua(r, saida) / q_agua(r, entrada) if q_agua(r, entrada) > 0 else None


def eta_oleo_fwko(r):
    return 1 - r.streams["C-05"]["O"] / r.streams["C-03"]["O"]


def standing_exemplo(r, prem, dados):
    """(Rs no FWKO, Rs de referência, Rs no V-001) em Sm³/Sm³, sem o corte em zero."""
    ks, T_ref = constantes().standing, constantes().T_ref_C
    g, api = r.gp["gamma"], r.api
    return (standing_rs(prem["P_FWKO"], r.T["C-03"], g, api, ks),
            standing_rs(dados.P_std_kPa, T_ref, g, api, ks),
            standing_rs(prem["P_D1"], r.T["C-08"], g, api, ks))


# ------------------------------------------------------------------ entre casos
def maximo(resultados, f):
    """(valor máximo, [casos empatados no máximo])."""
    tol = criterios()["empate_rel"]
    vals = [f(r) for r in resultados]
    mx = max(vals)
    return mx, [r.num for r, v in zip(resultados, vals) if abs(v - mx) <= tol * max(1, abs(mx))]


def casos_abaixo_T_fwko(resultados, prem):
    tol = criterios()["tol_temperatura"]
    return [r.num for r in resultados if r.T["C-03"] < prem["T_FWKO_min"] - tol]


def casos_sem_preaquecimento(resultados):
    return [r.num for r in resultados if r.duties["Q_pre"] < criterios()["carga_nula_kW"]]


def casos_sem_diluicao(resultados):
    return [r.num for r in resultados if r.gas["Dv"] < criterios()["vazao_nula_m3_d"]]


def casos_acima_T_separacao(resultados):
    lim = carregar("constantes.toml")["bot"]["T_separacao_max_C"]
    return [r.num for r in resultados if r.T["C-08"] > lim]


def max_delta_gas(dados):
    return max(abs(c["total_gas_sm3d"] - c["produced_gas_sm3d"] - c["lift_gas_sm3d"] - c["transferred_gas_sm3d"])
               for c in dados.casos)


# ------------------------------------------------------------------ fluidos
def normalizacao_composicoes(dados):
    """Verificação da origem das composições: Σx, k_f por CO2 e C1, H2S em ppm, poço."""
    bot = carregar("composicao_bot.toml")
    linhas = []
    for f, cc in dados.composicoes.items():
        co2, c1 = bot["CO2_pct"][f], bot["C1_pct"][f]
        linhas.append(dict(fluido=f, soma=sum(cc.values()), co2_bot=co2, k_co2=cc["CO2"] / (co2 / POR_CENTO),
                           c1_bot=c1, k_c1=cc["C1"] / (c1 / POR_CENTO), h2s_ppm=cc["H2S"] * PPM_POR_UNIDADE,
                           poco=poco_do_fluido(dados, f)))
    return linhas


def propriedades_fluidos(dados, VM):
    const = constantes()
    linhas = []
    for f in dados.composicoes:
        poco = poco_do_fluido(dados, f)
        api = pocos()[poco].api
        linhas.append(dict(fluido=f, poco=poco, api=api, gp=gas_props(dados.composicoes[f], const, VM),
                           rho_O=const.api_a / (const.api_b + api) * const.rho_agua_15_6C,
                           h2s_ppmv=dados.h2s_ppmv[f]))
    return linhas


def rho_oleo_poco(poco):
    const = constantes()
    return const.api_a / (const.api_b + pocos()[poco].api) * const.rho_agua_15_6C


# ------------------------------------------------------------------ envelopes
def envelopes(resultados, dados, prem):
    """{id: (máximo, casos)} dos envelopes preliminares por variável."""
    Pf = prem["P_FWKO"]
    defs = {
        "oleo_C01": lambda r: r.caso["oil_sm3d"],
        "liquido_C01": lambda r: r.caso["liquid_sm3d"],
        "agua_C01": lambda r: r.Wv,
        "liquido_C03": lambda r: q(r, "C-03", "O") + q_agua(r, "C-03"),
        "gas_modulo": lambda r: r.gas["G_in"],
        "gas_total_bot": lambda r: r.caso["total_gas_sm3d"],
        "gas_real_fwko": lambda r: q_real_gas(r, "G_F", Pf, r.T["C-04"], dados),
        "Q_pre": lambda r: r.duties["Q_pre"],
        "Q_H": lambda r: r.duties["Q_H"],
        "Q_aquecimento": lambda r: r.duties["Q_H"] + r.duties["Q_D"],
        "Q_C": lambda r: r.duties["Q_C"],
        "W_bombas": lambda r: r.duties["W_B1"] + r.duties["W_B2"] + r.duties["W_Bo"],
        "T_chegada_max": lambda r: r.caso["T_C"],
        "T_chegada_min": lambda r: -r.caso["T_C"],
        "mu_fwko": lambda r: r.mu[0],
        "BSW_chegada": lambda r: POR_CENTO * r.BSW01,
        "reciclo_C02": lambda r: q_agua(r, "C-02"),
        "diluicao": lambda r: r.gas["Dv"],
        "CO2_fluido": lambda r: dados.composicoes[r.fluid]["CO2"],
        "CO2_molar": co2_molar,
        "H2S_ppmv": lambda r: dados.h2s_ppmv[r.fluid],
        "H2S_molar": h2s_molar,
    }
    return {k: maximo(resultados, f) for k, f in defs.items()}


def criticos(resultados, dados, prem):
    """Lista ordenada (id, máximo, casos) dos critérios candidatos por equipamento."""
    defs = [
        ("SG-001/gas_real", lambda r: q_real_gas(r, "G_F", prem["P_FWKO"], r.T["C-04"], dados)),
        ("SG-001/liquido_C03", lambda r: q(r, "C-03", "O") + q_agua(r, "C-03")),
        ("SG-001/viscosidade", lambda r: r.mu[0]),
        ("P-001/Q", lambda r: r.duties["Q_pre"]),
        ("P-002/Q", lambda r: r.duties["Q_H"]),
        ("V-001/gas_real", lambda r: q_real_gas(r, "G_D1", prem["P_D1"], r.T["C-09"], dados)),
        ("V-001/liquido_C10", lambda r: q(r, "C-10", "O") + q_agua(r, "C-10")),
        ("TO-001/agua_C12", lambda r: q_agua(r, "C-12")),
        ("TO-001/oleo_C10", lambda r: q(r, "C-10", "O")),
        ("B-002/vazao_C12", lambda r: q_agua(r, "C-12")),
        ("DWH-001/Q_D", lambda r: r.gas["Dv"]),
        ("V-002/gas_real", lambda r: q_real_gas(r, "G_D2", prem["P_D2"], r.T["C-17"], dados)),
        ("TO-002/liquido_C18", lambda r: q(r, "C-18", "O") + q_agua(r, "C-18")),
        ("B-003/vazao_C19", lambda r: q_agua(r, "C-19")),
        ("B-001/vazao_C21", lambda r: q(r, "C-21", "O") + q_agua(r, "C-21")),
        ("P-003/Q", lambda r: r.duties["Q_C"]),
        ("materiais/CO2_molar", lambda r: r.gp["y"]["CO2"] * r.streams["C-01"]["G"] / r.gp["MW"]),
        ("materiais/H2S_ppmv", lambda r: dados.h2s_ppmv[r.fluid]),
    ]
    return [(k, *maximo(resultados, f)) for k, f in defs]


# ------------------------------------------------------------------ fechamento
def fechamento(resultados):
    """Maior erro de massa/energia por bloco e global, com o caso onde ocorre."""
    lim = criterios()["fechamento_max"]
    nums = [r.num for r in resultados]
    linhas, ok = [], True
    for b in topologia()["blocos"]:
        em = [balanco_bloco(r, b)["em"] for r in resultados]
        ee = [balanco_bloco(r, b)["eE"] for r in resultados]
        im = max(range(len(resultados)), key=lambda i: em[i])
        ie = max(range(len(resultados)), key=lambda i: ee[i])
        ok &= em[im] <= lim and ee[ie] <= lim
        linhas.append(dict(id=b["id"], nome=b["nome"], em=em[im], caso_m=nums[im], eE=ee[ie], caso_E=nums[ie]))
    gb = [balanco_global(r) for r in resultados]
    gm, ge = max(g["em"] for g in gb), max(g["eE"] for g in gb)
    ok &= gm <= lim and ge <= lim
    glob = dict(em=gm, caso_m=nums[max(range(len(gb)), key=lambda i: gb[i]["em"])],
                eE=ge, caso_E=nums[max(range(len(gb)), key=lambda i: gb[i]["eE"])])
    return linhas, glob, ok


def residuos_componentes(r):
    """(resíduo global por componente, maior |resíduo| entre os volumes de controle)."""
    topo, st = topologia(), r.streams
    res = {k: sum(st[s][k] for s in topo["global_in"]) - sum(st[s][k] for s in topo["global_out"]) for k in COMP}
    mxb = max(abs(v) for b in topo["blocos"] for v in balanco_bloco(r, b)["comp"].values())
    return res, mxb


# ------------------------------------------------------------------ sensibilidade
def sensibilidade(resultados, dados, prem):
    """Casos avaliados e [(caso, rótulo, resultado)] para cada variação declarada."""
    cfg = carregar("sensibilidade_balanco.toml")
    iQH = max(range(len(resultados)), key=lambda i: resultados[i].duties["Q_H"])
    casos = [resultados[iQH].num, *cfg["casos_fixos"]]
    corridas = []
    for n in casos:
        caso = dados.caso(n)
        for v in cfg["variacoes"]:
            p = dict(prem)
            p.update(v["alteracoes"])
            corridas.append((n, v["rotulo"], resolver_caso(caso, dados, p)))
    return casos, corridas


def soma_q(r, sids, c):
    """Σ vazão padrão do componente c num conjunto de correntes."""
    return sum(q(r, s, c) for s in sids)


# ------------------------------------------------------------------ verificação física (F10v)
def _verif():
    return carregar("verificacao_balanco.toml")


def massa_agua(r, sid):
    """Água (produzida + diluição) na corrente, kg/s."""
    return sum(r.streams[sid][c] for c in _verif()["componentes_agua"])


def bsw(r, sid):
    """BSW volumétrico na condição padrão (fração); 0 sem líquido."""
    ww, o = q_agua(r, sid), q(r, sid, "O")
    return ww / (ww + o) if ww + o > 0 else 0.0


def balanco_agua(r):
    """Água que entra e sai pelas correntes de fronteira do diagrama (kg/s), o reciclo e o
    resíduo entra − sai. As fronteiras vêm da topologia."""
    topo = topologia()
    entra = {s: massa_agua(r, s) for s in topo["global_in"]}
    sai = {s: massa_agua(r, s) for s in topo["global_out"]}
    return dict(num=r.num, entra=entra, sai=sai, reciclo=massa_agua(r, _verif()["reciclo"]),
                residuo=sum(entra.values()) - sum(sai.values()))


def sal_real_mgL(r, sid, prem):
    """Salinidade da água da corrente com o sal de cada componente (S_W, S_D), mg/L."""
    w, d = q(r, sid, "W"), q(r, sid, "D")
    return (w * prem["S_W"] + d * prem["S_D"]) / (w + d) if w + d > 0 else 0.0


def verificacao_fisica(resultados, prem):
    """Conferência física do balanço, caso a caso (não altera o resultado):

    - água: fechamento pelas fronteiras e reciclo; casos sem fase aquosa (P-42);
    - BSW de cada separador = min(BSW de entrada; especificação) (P-24/P-28/P-29, P-42);
    - FWKO com água na saída de óleo sempre que a chegada tem água (BOT 2.7.1.2);
    - salinidade do óleo tratado com o sal real de W e D, na base do volume da emulsão,
      e na do óleo (informativa), contra S_spec;
    - água de diluição com o sal real da água residual × a calculada com S_W (modelo);
    - FWKO abaixo de T_FWKO_min (F-07; o reciclo de óleo da Nota 11 não é modelado, P-41);
    - γ do gás por caso (validade de Standing, P-23: faixa pendente de fonte no acervo)."""
    v = _verif()
    tol = v["tol_rel"]
    agua = [balanco_agua(r) for r in resultados]
    sem_agua = [a["num"] for a in agua if not sum(a["entra"].values()) > 0]
    separadores = []
    for s in v["separadores"]:
        spec = prem[s["premissa"]]
        for r in resultados:
            b_in, b_out = bsw(r, s["entrada"]), bsw(r, s["oleo"])
            esperado = min(b_in, spec)
            separadores.append(dict(bloco=s["bloco"], premissa=s["premissa"], num=r.num, entrada=b_in, saida=b_out,
                                    esperado=esperado, ok=abs(b_out - esperado) <= tol * max(1, spec)))
    fwko = v["separadores"][0]
    fwko_seco = [r.num for r in resultados if massa_agua(r, fwko["entrada"]) > 0 and not massa_agua(r, fwko["oleo"]) > 0]
    oleo, antes = v["oleo_tratado"], v["agua_antes_da_diluicao"]
    sal, diluicao = [], []
    for r in resultados:
        if r.num in sem_agua:
            continue
        s_agua = sal_real_mgL(r, oleo, prem)
        ww, o = q_agua(r, oleo), q(r, oleo, "O")
        sal.append(dict(num=r.num, emulsao=s_agua * ww / (ww + o), oleo=s_agua * ww / o))
        w_antes = q_agua(r, antes)
        s_res = prem["S_spec"] / prem["BSW_t"]
        real = w_antes * (sal_real_mgL(r, antes, prem) / s_res - 1) / prem["eta_mix"]
        diluicao.append(dict(num=r.num, modelo=r.gas["Dv"], sal_real=real,
                             excesso_rel=r.gas["Dv"] / real - 1 if real > 0 else 0.0))
    return dict(
        agua=agua, sem_fase_aquosa=sem_agua,
        maior_residuo_agua=max(abs(a["residuo"]) for a in agua),
        saidas_agua=[s for s in topologia()["global_out"] if any(a["sai"][s] > 0 for a in agua)],
        separadores=separadores, bsw_ok=all(x["ok"] for x in separadores), fwko_sem_agua_no_oleo=fwko_seco,
        sal_oleo=sal, sal_max_emulsao=max((x["emulsao"] for x in sal), default=0.0), limite_sal=prem["S_spec"],
        diluicao=diluicao, abaixo_T_fwko=casos_abaixo_T_fwko(resultados, prem), t_fwko_min=prem["T_FWKO_min"],
        gamma_gas={r.num: r.gp["gamma"] for r in resultados},
    )
