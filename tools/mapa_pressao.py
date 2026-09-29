"""Mapa determinístico pressão → flash → dimensionamento → TVP, sobre a GRADE DE SENSIBILIDADE de
config/pfd/mapa_pressao.toml, e a sensibilidade de cada saída a P_D1 e P_D2.

Estudo (decisão do usuário, 2026-09-28): P_D1 e P_D2 variam como PREMISSAS, pelo mesmo serviço

    P_D1/P_D2 → Contexto(alteracoes=…) → resolver_todos → trem produtivo
              → dimensionamento SG-001/V-001/V-002 → TVP e métricas

Nada aqui calcula física: só orquestra a API e faz estatística sobre a grade (máximo, mínimo,
monotonicidade). Não é otimização e não entra no pymoo; P-001 fica fora. Dois universos:

- ENVELOPE DE DIMENSIONAMENTO: SG-001/V-001/V-002 sobre os 16 casos do BOT (os 4 com gás de lift
  seguem por Standing), como no produto; vazões de gás e potências também sobre os 16;
- ANÁLISE TERMODINÂMICA: TVP e óleo tratado só sobre os 12 casos avaliáveis.

Pontos inválidos ou não avaliáveis são CLASSIFICADOS na saída, nunca descartados em silêncio.

    uv run python tools/mapa_pressao.py [--casos ARQ] [--saida docs/validacao/mapa_pressao]
"""
import argparse
import csv
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.core import memoria
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
VALIDO = "válido"

# grandezas contínuas analisadas: (chave, rótulo, universo)
CONTINUAS = [
    ("TVP_max_kPa", "TVP máxima", "12 termo"), ("TVP_min_kPa", "TVP mínima", "12 termo"),
    ("oleo_tratado_m3_d", "óleo tratado Σ", "12 termo"),
    ("Q_G_SG001_max_Sm3_d", "Q_G SG-001 máx.", "16 dim."), ("Q_G_V001_max_Sm3_d", "Q_G V-001 máx.", "16 dim."),
    ("Q_G_V002_max_Sm3_d", "Q_G V-002 máx.", "16 dim."), ("Q_G_VRU_max_Sm3_d", "Q_G VRU máx. (V-001 + V-002)", "16 dim."),
    ("SG001_Leff_m", "SG-001 Leff", "16 dim."), ("SG001_volume_m3", "SG-001 volume", "16 dim."),
    ("V001_Leff_m", "V-001 Leff", "16 dim."), ("V001_volume_m3", "V-001 volume", "16 dim."),
    ("V002_Leff_m", "V-002 Leff", "16 dim."), ("V002_volume_m3", "V-002 volume", "16 dim."),
    ("V001_gas_sobre_liquido", "V-001 exigência gás/líquido", "16 dim."),
    ("V002_gas_sobre_liquido", "V-002 exigência gás/líquido", "16 dim."),
    ("volume_total_m3", "volume total dos três vasos", "16 dim."),
    ("W_B001_max_kW", "B-001 potência máx.", "16 dim."), ("W_B002_max_kW", "B-002 potência máx.", "16 dim."),
    ("W_B003_max_kW", "B-003 potência máx.", "16 dim."),
]
DISCRETAS = [(f"{p}_{c}", f"{t} {r}") for p, t in (("SG001", "SG-001"), ("V001", "V-001"), ("V002", "V-002"))
             for c, r in (("d_mm", "diâmetro"), ("governante", "governante"), ("caso", "caso governante"))]


def cfg():
    return carregar("pfd/mapa_pressao.toml")


def limite(ident):
    return next(x for x in cfg()["limite"] if x["id"] == ident)


# ------------------------------------------------------------------ um ponto da grade
def ponto(dados, p_d1, p_d2):
    """Uma linha do mapa, com o estado do ponto classificado."""
    linha = {"P_D1_kPa": p_d1, "P_D2_kPa": p_d2}
    if p_d2 >= p_d1:
        return dict(linha, estado="inválido: P_D2 ≥ P_D1 (limite de processo)")
    ctx = servico.Contexto(dados, alteracoes={"P_D1": p_d1, "P_D2": p_d2}, propostas=propostas.padrao())
    try:
        b = ctx.balanco
    except ValueError as e:  # recombinação que não fecha, trem incompleto, flash sem convergência
        return dict(linha, estado=f"não convergiu: {e}")
    aval = [r for r in b if r.avaliavel]
    tvps = {r.num: r.tvp_kPa for r in aval}
    finitas = [v for v in tvps.values() if math.isfinite(v)]
    lim = limite("tvp")["valor"]
    linha.update({
        "casos_dimensionamento": len(b), "casos_termodinamicos": len(aval),
        "casos_nao_avaliaveis": len(b) - len(aval),
        "TVP_max_kPa": max(finitas) if finitas else math.nan, "TVP_min_kPa": min(finitas) if finitas else math.nan,
        "casos_TVP_acima": sum(v > lim for v in finitas), "casos_TVP_sem_solucao": len(tvps) - len(finitas),
        "oleo_tratado_m3_d": sum(r.q("C-21", "O") for r in aval),
        "Q_G_SG001_max_Sm3_d": max(r.gas["G_F"] for r in b),
        "Q_G_V001_max_Sm3_d": max(r.gas["G_D1"] for r in b), "Q_G_V002_max_Sm3_d": max(r.gas["G_D2"] for r in b),
        "Q_G_VRU_max_Sm3_d": max(r.gas["G_D1"] + r.gas["G_D2"] for r in b),
        "W_B001_max_kW": max(r.duties["W_Bo"] for r in b), "W_B002_max_kW": max(r.duties["W_B1"] for r in b),
        "W_B003_max_kW": max(r.duties["W_B2"] for r in b)})
    volume, inviaveis = 0.0, []
    for ident in cfg()["tags"]:
        res = servico.executar(ctx, servico.estado_inicial(ident)).resultado
        pref = ident.replace("-", "")
        if res is None or not res.feasible:
            inviaveis.append(ident)
            linha.update({f"{pref}_d_mm": math.nan, f"{pref}_governante": "inviável", f"{pref}_caso": ""})
            continue
        cap = memoria.capacidades(res, res.x)
        linha.update({f"{pref}_d_mm": res.x, f"{pref}_Leff_m": res.y, f"{pref}_volume_m3": res.derivados["volume"],
                      f"{pref}_governante": res.governing, f"{pref}_caso": res.driver_case,
                      f"{pref}_gas_sobre_liquido": cap["gas"] / cap["liquid"]})
        volume += res.derivados["volume"]
    linha["volume_total_m3"] = volume if not inviaveis else math.nan
    if inviaveis:
        linha["estado"] = f"TAG inviável: {', '.join(inviaveis)}"
    elif linha["casos_TVP_sem_solucao"]:
        linha["estado"] = f"TVP sem solução em {linha['casos_TVP_sem_solucao']} caso(s)"
    else:
        linha["estado"] = VALIDO
    return linha


# ------------------------------------------------------------------ sensibilidade (estatística da grade)
def _monotonica(seqs):
    """'crescente', 'decrescente', 'constante' ou 'não monotônica' sobre todas as sequências."""
    sinais = set()
    for s in seqs:
        for a, b in zip(s, s[1:]):
            if b > a:
                sinais.add(1)
            elif b < a:
                sinais.add(-1)
    return {frozenset(): "constante", frozenset({1}): "crescente", frozenset({-1}): "decrescente"}.get(
        frozenset(sinais), "não monotônica")


def _amplitude_media(seqs):
    """Média de (máx − mín) sobre as linhas com dois pontos ou mais (as de um ponto não medem)."""
    com = [max(x) - min(x) for x in seqs if len(x) > 1]
    return sum(com) / len(com) if com else 0.0


def classificar(drel):
    s = cfg()["sensibilidade"]
    if drel < s["insensivel_max"]:
        return "INSENSÍVEL"
    return "FRACAMENTE SENSÍVEL" if drel < s["sensivel_min"] else "SENSÍVEL"


def sensibilidade(linhas, ref):
    """Por grandeza contínua: Δ absoluto e relativo (ao ponto de referência), pontos de mínimo e
    máximo, monotonicidade em cada pressão, e qual pressão domina (maior amplitude média ao
    longo do seu eixo)."""
    val = [li for li in linhas if li["estado"] == VALIDO]
    p1s = sorted({li["P_D1_kPa"] for li in val})
    p2s = sorted({li["P_D2_kPa"] for li in val})
    por = {(li["P_D1_kPa"], li["P_D2_kPa"]): li for li in val}
    out = []
    for chave, rotulo, universo in CONTINUAS:
        pts = [(li[chave], li["P_D1_kPa"], li["P_D2_kPa"]) for li in val if math.isfinite(li[chave])]
        mn, mx = min(pts), max(pts)
        dabs = mx[0] - mn[0]
        base = abs(ref[chave]) if ref[chave] else abs(mx[0])
        drel = dabs / base if base else 0.0
        ao_longo_p2 = [[por[(a, b)][chave] for b in p2s if (a, b) in por] for a in p1s]
        ao_longo_p1 = [[por[(a, b)][chave] for a in p1s if (a, b) in por] for b in p2s]
        amp2 = _amplitude_media(ao_longo_p2)
        amp1 = _amplitude_media(ao_longo_p1)
        out.append(dict(chave=chave, rotulo=rotulo, universo=universo, dabs=dabs, drel=drel,
                        minimo=mn, maximo=mx, mono_p1=_monotonica(ao_longo_p1), mono_p2=_monotonica(ao_longo_p2),
                        amp_p1=amp1, amp_p2=amp2,
                        domina="P_D2" if amp2 > amp1 else "P_D1" if amp1 > amp2 else "nenhuma",
                        classe=classificar(drel)))
    for chave, rotulo in DISCRETAS:
        valores = sorted({str(li[chave]) for li in val})
        out.append(dict(chave=chave, rotulo=rotulo, universo="16 dim.", valores=valores,
                        classe="INSENSÍVEL" if len(valores) == 1 else "SENSÍVEL"))
    return out


# ------------------------------------------------------------------ saída
def n(x, casas=1):
    if isinstance(x, str):
        return x
    return "—" if x is None or x != x else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar(dados, saida):
    c = cfg()
    prem = premissas(dados)
    linhas = [ponto(dados, p1, p2) for p1 in c["P_D1_kPa"] for p2 in c["P_D2_kPa"]]
    ref = next((li for li in linhas if (li["P_D1_kPa"], li["P_D2_kPa"]) == (prem["P_D1"], prem["P_D2"])), None)
    if ref is None or ref["estado"] != VALIDO:
        ref = ponto(dados, prem["P_D1"], prem["P_D2"])
    saida.mkdir(parents=True, exist_ok=True)
    campos = list(dict.fromkeys(k for li in linhas for k in li))
    with (saida / "mapa_pressao.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    sens = sensibilidade(linhas, ref)
    val = [li for li in linhas if li["estado"] == VALIDO]
    md = ["# Mapa pressão → flash → dimensionamento → TVP (tabelas geradas)", "",
          f"Gerado por `tools/mapa_pressao.py`. Referência: P_D1 = {n(prem['P_D1'], 0)} kPa (P-18), "
          f"P_D2 = {n(prem['P_D2'], 0)} kPa (P-19). CSV completo: `mapa_pressao.csv`.", "",
          "## Estado de cada ponto da grade", "", "| P_D1 | P_D2 | estado |", "|---:|---:|---|"]
    md += [f"| {n(li['P_D1_kPa'], 0)} | {n(li['P_D2_kPa'], 0)} | {li['estado']} |" for li in linhas]
    md += ["", "## Análise termodinâmica (12 casos avaliáveis)", "",
           "| P_D1 | P_D2 | TVP mín (kPa) | TVP máx (kPa) | casos TVP > 70 | TVP sem solução | óleo tratado Σ (m³/d) |",
           "|---:|---:|---:|---:|---:|---:|---:|"]
    md += [f"| {n(li['P_D1_kPa'], 0)} | {n(li['P_D2_kPa'], 0)} | {n(li['TVP_min_kPa'])} | {n(li['TVP_max_kPa'])} | "
           f"{li['casos_TVP_acima']} | {li['casos_TVP_sem_solucao']} | {n(li['oleo_tratado_m3_d'])} |" for li in val]
    md += ["", "## Envelope de dimensionamento (16 casos do BOT)", "",
           "| P_D1 | P_D2 | Q_G SG-001 | Q_G V-001 | Q_G V-002 | Q_G VRU | SG-001 d / Leff / vol / gov. / caso | "
           "V-001 d / Leff / vol / gov. / caso | V-002 d / Leff / vol / gov. / caso | gás/líq V-001 | gás/líq V-002 | "
           "vol. total (m³) | W B-001 / B-002 / B-003 (kW) |",
           "|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---|"]

    def vaso(li, p):
        return (f"{n(li[p + '_d_mm'], 0)} / {n(li[p + '_Leff_m'], 3)} / {n(li[p + '_volume_m3'])} / "
                f"{li[p + '_governante']} / {li[p + '_caso'].split(' — ')[0]}")

    md += [f"| {n(li['P_D1_kPa'], 0)} | {n(li['P_D2_kPa'], 0)} | {n(li['Q_G_SG001_max_Sm3_d'], 0)} | "
           f"{n(li['Q_G_V001_max_Sm3_d'], 0)} | {n(li['Q_G_V002_max_Sm3_d'], 0)} | {n(li['Q_G_VRU_max_Sm3_d'], 0)} | "
           f"{vaso(li, 'SG001')} | {vaso(li, 'V001')} | {vaso(li, 'V002')} | {n(li['V001_gas_sobre_liquido'], 3)} | "
           f"{n(li['V002_gas_sobre_liquido'], 3)} | {n(li['volume_total_m3'], 2)} | "
           f"{n(li['W_B001_max_kW'])} / {n(li['W_B002_max_kW'])} / {n(li['W_B003_max_kW'])} |" for li in val]
    s = c["sensibilidade"]
    md += ["", "## Sensibilidade", "",
           f"Critério: Δrel = (máx − mín)/|valor na referência|; INSENSÍVEL se Δrel < {n(100 * s['insensivel_max'], 0)} %, "
           f"FRACAMENTE SENSÍVEL se < {n(100 * s['sensivel_min'], 0)} %, SENSÍVEL acima. Domina a pressão de maior "
           "amplitude média ao longo do seu eixo.", "",
           "| grandeza | universo | referência | Δ abs | Δ rel | mínimo (P_D1; P_D2) | máximo (P_D1; P_D2) | em P_D1 | "
           "em P_D2 | amplitude média P_D1 / P_D2 | domina | classe |",
           "|---|---|---:|---:|---:|---|---|---|---|---|---|---|"]
    for x in sens:
        if "valores" in x:
            continue
        md.append(f"| {x['rotulo']} | {x['universo']} | {n(ref[x['chave']], 3)} | {n(x['dabs'], 3)} | "
                  f"{n(100 * x['drel'], 2)} % | {n(x['minimo'][0], 3)} ({n(x['minimo'][1], 0)}; {n(x['minimo'][2], 0)}) | "
                  f"{n(x['maximo'][0], 3)} ({n(x['maximo'][1], 0)}; {n(x['maximo'][2], 0)}) | {x['mono_p1']} | "
                  f"{x['mono_p2']} | {n(x['amp_p1'], 3)} / {n(x['amp_p2'], 3)} | {x['domina']} | {x['classe']} |")
    md += ["", "| grandeza discreta | valores na grade | classe |", "|---|---|---|"]
    md += [f"| {x['rotulo']} | {'; '.join(x['valores'])} | {x['classe']} |" for x in sens if "valores" in x]
    (saida / "mapa_pressao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return linhas, sens, ref


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS if CASOS.exists() else FIXTURE)
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "mapa_pressao")
    a = ap.parse_args()
    gerar(carregar_casos(a.casos), a.saida)
    print(a.saida)


if __name__ == "__main__":
    main()
