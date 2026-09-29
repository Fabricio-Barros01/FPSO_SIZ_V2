"""Relatório do trem de separação SG-001 → V-001 → V-002 de cada caso.

Só lê o `EstadoProcesso` (`balanco/modelo.resolver_todos` → `EstadoProcesso.trem`): nenhuma
física aqui. Nos casos avaliáveis o trem é produtivo (recombinação da Nota 4 + flashes); nos
casos com gás de lift, o estado diz por que não é avaliável. A TVP e o P_D2 em que ela atinge o
limite do BOT são DIAGNÓSTICO: o P_D2 é buscado re-resolvendo o mesmo caso pelo mesmo serviço.

    uv run python tools/relatorio_trem.py [--casos ARQ] [--saida saida/trem.md] [--sem-busca]
"""
import argparse
import math
import time
from pathlib import Path

from fpso_siz.balanco import trem
from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_caso, resolver_todos

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def n(x, casas=4):
    return "—" if x is None or x != x else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def e(x):
    return "—" if x is None or x != x else f"{x:.2e}"


def tvp(dados, prem, r):
    return r.tvp_kPa


def p_d2_no_limite(dados, prem, caso):
    """P_D2 [kPa] em que a TVP do óleo tratado atinge o limite do BOT (bisseção sobre o mesmo
    serviço: cada ponto é o caso inteiro re-resolvido com outra premissa)."""
    c = trem.cfg()["tvp"]
    lo, hi = c["P_D2_min_kPa"], c["P_D2_max_kPa"]

    def excede(p):
        return tvp(dados, prem, resolver_caso(caso, dados, dict(prem, P_D2=p))) > c["limite_kPa"]

    if excede(lo) or not excede(hi):
        return math.nan
    for _ in range(c["iteracoes"]):
        meio = (lo + hi) / 2
        lo, hi = (lo, meio) if excede(meio) else (meio, hi)
    return lo


def gerar(dados, busca=True):
    prem = premissas(dados)
    t0 = time.perf_counter()
    estados = resolver_todos(dados, prem)
    dt = time.perf_counter() - t0
    c = trem.cfg()
    out = ["# Trem de separação SG-001 → V-001 → V-002", "",
           "Gerado por `tools/relatorio_trem.py` a partir do `EstadoProcesso`. Nos casos avaliáveis o trem é o "
           "caminho produtivo; nos casos com gás de lift, "
           f"'{c['avaliacao']['estado_nao_avaliavel']}'.", "",
           f"Recombinação (Nota 4, premissa de modelagem): `{c['recombinacao']['regra']}` — "
           f"{c['recombinacao']['referencia']}.", "",
           "## Recombinação por caso", "",
           "| caso | fluido | Q_G BOT (Sm³/d) | Q_G no FWKO do z_caso | erro | Q_O BOT (m³/d) | Q_O de óleo morto | erro "
           "| Σz − 1 | molar | mássico | componente |",
           "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in estados:
        rc = r.recombinacao
        if rc is None:
            out.append(f"| {r.num} | {r.fluid} | {n(r.caso['produced_gas_sm3d'], 0)} | não avaliável | | "
                       f"{n(r.caso['oil_sm3d'], 0)} | | | | | | |")
            continue
        out.append(f"| {r.num} | {r.fluid} | {n(rc.q_gas_bot_sm3d, 0)} | {n(rc.reproducao.q_gas_fwko_sm3d, 1)} | "
                   f"{e(rc.reproducao.erro_gas_rel)} | {n(rc.q_oleo_bot_m3d, 0)} | {n(rc.reproducao.q_oleo_tanque_m3d, 3)} | "
                   f"{e(rc.reproducao.erro_oleo_rel)} | {e(rc.erro_soma_z)} | {e(rc.erro_molar)} | {e(rc.erro_massico)} | "
                   f"{e(rc.componente[1])} |")
    out += ["", "## Estágios", "",
            "| caso | estágio | T (°C) | P (kPa) | β | Q_G (Sm³/d) | ṅ_V (kmol/d) | ṁ_V (kg/d) | MW_v | Z_v | ρ_v (kg/m³) |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in estados:
        for s in (r.trem.estagios if r.avaliavel else []):
            v = s.vapor
            out.append(f"| {r.num} | {s.ponto} | {n(s.T_C, 2)} | {n(s.P_kPa, 1)} | {n(s.beta, 6)} | {n(s.q_vapor_sm3d, 0)} | "
                       f"{n(s.n_vapor_kmol_d, 1)} | {n(s.m_vapor_kg_d, 0)} | {n(v.MW, 3)} | {n(v.Z, 5)} | {n(v.rho, 4)} |")
    out += ["", "## Fechamento do trem", "", "| caso | completo | molar | mássico | componente | pior |",
            "|---:|:--:|---:|---:|---:|---|"]
    for r in estados:
        if r.avaliavel:
            f = r.trem.fechamento
            out.append(f"| {r.num} | {'sim' if f.ok else 'não'} | {e(f.erro_molar_relativo)} | {e(f.erro_massico_relativo)} | "
                       f"{e(f.erro_componente_max)} | {f.componente_pior} |")
    lim = c["tvp"]["limite_kPa"]
    T = prem[c["tvp"]["premissa_T"]]
    out += ["", f"## TVP do óleo tratado a {n(T, 1)} °C (diagnóstico; limite do BOT {n(lim, 0)} kPa)", "",
            "| caso | P_D2 atual (kPa) | TVP (kPa) | P_D2 em que TVP = limite (kPa) |", "|---:|---:|---:|---:|"]
    for r in estados:
        if not r.avaliavel:
            out.append(f"| {r.num} | {n(prem['P_D2'], 1)} | não avaliável | não avaliável |")
            continue
        alvo = p_d2_no_limite(dados, prem, r.caso) if busca else math.nan
        out.append(f"| {r.num} | {n(prem['P_D2'], 1)} | {n(tvp(dados, prem, r), 1)} | {n(alvo, 1)} |")
    out += ["", "## Lacunas", ""]
    out += [f"- **{x['grandeza']}** ({x['situacao']}): {x['efeito']}" for x in trem.lacunas()]
    out += ["", f"Custo da resolução dos {len(estados)} casos: {n(dt, 2)} s "
            f"(flashes distintos em memória: {trem._flash.cache_info().currsize}).", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS if CASOS.exists() else FIXTURE)
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "trem.md")
    ap.add_argument("--sem-busca", action="store_true", help="não busca o P_D2 em que a TVP atinge o limite")
    a = ap.parse_args()
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(gerar(carregar_casos(a.casos), busca=not a.sem_busca), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
