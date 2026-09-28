"""Relatório do trem de separação SG-001 → V-001 → V-002 de cada caso.

Só lê o `EstadoProcesso` (`balanco/modelo.resolver_todos` → `EstadoProcesso.trem`) e a medida
de compatibilidade com o BOT (`balanco/trem.coerencia_com_bot`): nenhuma física aqui. O trem
é diagnóstico dentro do estado oficial — a vazão de gás por estágio que o processo consome é a
de Standing (config/termo/proveniencia.toml).

    uv run python tools/relatorio_trem.py [--casos ARQ] [--saida saida/trem.md]
"""
import argparse
import time
from pathlib import Path

from fpso_siz.balanco import trem
from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def n(x, casas=4):
    return "—" if x is None or x != x else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def e(x):
    return "—" if x is None or x != x else f"{x:.2e}"


def gerar(dados):
    estados = resolver_todos(dados, premissas(dados))
    t0 = time.perf_counter()
    trens = [r.trem for r in estados]
    dt = time.perf_counter() - t0
    regra = trem.cfg()["base_molar"]
    out = ["# Trem de separação SG-001 → V-001 → V-002", "",
           "Gerado por `tools/relatorio_trem.py` a partir do `EstadoProcesso`. Diagnóstico: o processo consome a "
           "vazão de gás de Standing; β, x e y do trem são não validados e sem consumidor.", "",
           f"Base molar: `{regra['regra']}` — {regra['massa']}; {regra['mw']}.", "",
           "| caso | fluido | ṅ_F (kmol/d) | β SG-001 | β V-001 | β V-002 | MW_V V-002 | fecha (trem) | erro por componente |",
           "|---:|---|---:|---:|---:|---:|---:|:--:|---:|"]
    for r, t in zip(estados, trens):
        b = [s.beta for s in t.estagios] + [float("nan")] * (3 - len(t.estagios))
        mw = t.estagios[-1].vapor.MW if t.estagios and t.estagios[-1].vapor else float("nan")
        out.append(f"| {r.num} | {r.fluid} | {n(t.base.n_F_kmol_d, 1)} | {n(b[0])} | {n(b[1])} | {n(b[2])} | "
                   f"{n(mw, 2)} | {'sim' if t.fechamento.ok else 'não'} | {e(t.fechamento.erro_componente_max)} |")
    out += ["", "## Compatibilidade com o BOT (condição padrão)", "",
            "| caso | GOR BOT | GOR flash | razão | discordância entre as bases por split |", "|---:|---:|---:|---:|---:|"]
    for r in estados:
        c = trem.coerencia_com_bot(r, dados.T_std_C, dados.P_std_kPa)
        if c["bifasico"]:
            out.append(f"| {r.num} | {n(c['gor_bot'], 1)} | {n(c['gor_flash'], 1)} | {n(c['gor_flash'] / c['gor_bot'], 2)} "
                       f"| {n(c['discordancia'] * 100, 1)} % |")
    out += ["", "## Lacunas", ""]
    out += [f"- **{x['grandeza']}** ({x['situacao']}): {x['efeito']}" for x in trem.lacunas()]
    out += ["", f"Custo: {len(trens)} trens, {sum(len(t.estagios) for t in trens)} flashes, {n(dt, 3)} s.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS if CASOS.exists() else FIXTURE)
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "trem.md")
    a = ap.parse_args()
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(gerar(carregar_casos(a.casos)), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
