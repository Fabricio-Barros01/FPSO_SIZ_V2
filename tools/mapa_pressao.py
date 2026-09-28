"""Mapa determinístico pressão → flash → dimensionamento → TVP, sobre a grade de P_D1 × P_D2 de
config/pfd/mapa_pressao.toml.

Estudo de sensibilidade (decisão do usuário, 2026-09-28): P_D1 e P_D2 variam como PREMISSAS, pelo
mesmo serviço (`pfd/equipamento.Contexto(alteracoes=…)` → `resolver_todos` → trem → TAGs); nada
aqui calcula física. Não é otimização e não entra no pymoo. P-001 fora do subproblema. Só os casos
termodinamicamente avaliáveis entram na TVP; SG-001, V-001 e V-002 são dimensionados nos 16 casos
(o envelope do BOT), como no produto.

    uv run python tools/mapa_pressao.py [--casos ARQ] [--saida saida/mapa_pressao]
"""
import argparse
import csv
import math
from pathlib import Path

from fpso_siz.balanco import trem
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.core import memoria
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def cfg():
    return carregar("pfd/mapa_pressao.toml")


def ponto(dados, p_d1, p_d2):
    """Uma linha do mapa: o processo e os TAGs do subproblema, com P_D1 e P_D2 dados."""
    ctx = servico.Contexto(dados, alteracoes={"P_D1": p_d1, "P_D2": p_d2}, propostas=propostas.padrao())
    b = ctx.balanco
    aval = [r for r in b if r.avaliavel]
    T = ctx.prem[trem.cfg()["tvp"]["premissa_T"]]
    tvps = {r.num: trem.tvp_kpa(r.trem, T, r.mws_plus) for r in aval}
    lim = next(x["valor"] for x in cfg()["limite"] if x["id"] == "tvp")
    linha = {"P_D1_kPa": p_d1, "P_D2_kPa": p_d2,
             "TVP_max_kPa": max(tvps.values()), "TVP_min_kPa": min(tvps.values()),
             "casos_TVP_acima": sum(v > lim for v in tvps.values()),
             "Q_G_V001_max_Sm3_d": max(r.gas["G_D1"] for r in b), "Q_G_V002_max_Sm3_d": max(r.gas["G_D2"] for r in b),
             "Q_G_VRU_max_Sm3_d": max(r.gas["G_D1"] + r.gas["G_D2"] for r in b),
             "oleo_tratado_Sm3_d": sum(r.q("C-21", "O") for r in aval),
             "W_B001_max_kW": max(r.duties["W_Bo"] for r in b), "W_B002_max_kW": max(r.duties["W_B1"] for r in b),
             "W_B003_max_kW": max(r.duties["W_B2"] for r in b)}
    volume = 0.0
    for ident in cfg()["tags"]:
        res = servico.executar(ctx, servico.estado_inicial(ident)).resultado
        cap = memoria.capacidades(res, res.x) if res.feasible else {}
        pref = ident.replace("-", "")
        linha.update({f"{pref}_d_mm": res.x, f"{pref}_Leff_m": res.y, f"{pref}_governante": res.governing,
                      f"{pref}_caso": res.driver_case,
                      f"{pref}_volume_m3": res.derivados.get("volume", math.nan) if res.feasible else math.nan,
                      f"{pref}_gas_sobre_liquido": cap.get("gas", math.nan) / cap["liquid"] if "liquid" in cap else math.nan})
        volume += linha[f"{pref}_volume_m3"]
    linha["volume_total_m3"] = volume
    return linha


def n(x, casas=1):
    if isinstance(x, str):
        return x
    return "—" if x is None or x != x else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar(dados, saida):
    c = cfg()
    linhas = [ponto(dados, p1, p2) for p1 in c["P_D1_kPa"] for p2 in c["P_D2_kPa"] if p2 < p1]
    saida.mkdir(parents=True, exist_ok=True)
    with (saida / "mapa_pressao.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    lim = next(x["valor"] for x in c["limite"] if x["id"] == "tvp")
    md = ["# Mapa pressão → flash → dimensionamento → TVP", "",
          "Gerado por `tools/mapa_pressao.py` (estudo; P_D1 e P_D2 como premissas, pelo mesmo serviço). "
          f"TVP nos casos avaliáveis, na estocagem; limite do BOT {n(lim, 0)} kPa.", "",
          "| P_D1 | P_D2 | TVP máx | TVP mín | casos > limite | Q_G V-001 máx | Q_G V-002 máx | V-001 d / Leff / vol | "
          "V-002 d / Leff / vol | gás/líquido V-001 | gás/líquido V-002 | SG-001 d / Leff | vol. total | W B-001 máx | "
          "óleo tratado Σ avaliáveis (m³/d) |",
          "|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|---:|"]
    for li in linhas:
        md.append(f"| {n(li['P_D1_kPa'], 0)} | {n(li['P_D2_kPa'], 0)} | {n(li['TVP_max_kPa'])} | {n(li['TVP_min_kPa'])} | "
                  f"{li['casos_TVP_acima']} | {n(li['Q_G_V001_max_Sm3_d'], 0)} | {n(li['Q_G_V002_max_Sm3_d'], 0)} | "
                  f"{n(li['V001_d_mm'], 0)} / {n(li['V001_Leff_m'], 2)} / {n(li['V001_volume_m3'])} | "
                  f"{n(li['V002_d_mm'], 0)} / {n(li['V002_Leff_m'], 2)} / {n(li['V002_volume_m3'])} | "
                  f"{n(li['V001_gas_sobre_liquido'], 3)} | {n(li['V002_gas_sobre_liquido'], 3)} | "
                  f"{n(li['SG001_d_mm'], 0)} / {n(li['SG001_Leff_m'], 3)} | {n(li['volume_total_m3'])} | "
                  f"{n(li['W_B001_max_kW'])} | {n(li['oleo_tratado_Sm3_d'])} |")
    (saida / "mapa_pressao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return linhas


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS if CASOS.exists() else FIXTURE)
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "mapa_pressao")
    a = ap.parse_args()
    gerar(carregar_casos(a.casos), a.saida)
    print(a.saida)


if __name__ == "__main__":
    main()
