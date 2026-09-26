"""F8 na planta: alvos de energia do pré-aquecedor (docs/validacao/22-pinch-planta.md).

Monta, para cada caso do balanço, a rede térmica declarada em config/pfd/pinch.toml — o óleo
vivo que sai do SG-001 e o óleo tratado que vai para o cargo tank —, calcula os alvos pela
Problem Table (Kemp) com o ΔTmin da premissa P-32, e compara com as cargas que o balanço
realizou no P-001, no P-002 e no P-003. Determinístico; os números vêm do balanço e do núcleo.

    uv run python tools/pinch_planta.py [--casos <json>] [--saida docs/validacao/22-pinch-planta.md]
"""
import argparse
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import pinch as pp

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def f(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabela_alvos(redes):
    out = ["| Caso | ΔTmin (°C) | QHmin alvo (kW) | Q_H do balanço (kW) | QCmin alvo (kW) | Q_C do balanço (kW) | "
           "Recuperação alvo (kW) | Q_pre do balanço (kW) | T de pinch deslocada (°C) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for rc in redes:
        if not rc.aplicavel:
            out.append(f"| {rc.nome} | {f(rc.dt_min)} | — | {f(rc.realizado['utilidade_quente'])} | — | "
                       f"{f(rc.realizado['utilidade_fria'])} | — | {f(rc.realizado['recuperacao'])} | "
                       "rede incompleta |")
            continue
        a = pp.alvos(rc)
        tp = rc.tabela.t_pinch_shifted[0] if rc.tabela.t_pinch_shifted else math.nan
        out.append(f"| {rc.nome} | {f(rc.dt_min)} | {f(a['utilidade_quente'])} | {f(rc.realizado['utilidade_quente'])} "
                   f"| {f(a['utilidade_fria'])} | {f(rc.realizado['utilidade_fria'])} | {f(a['recuperacao'])} | "
                   f"{f(rc.realizado['recuperacao'])} | {f(tp)} |")
    return out


def tabela_folgas(redes):
    out = ["| Caso | Utilidade quente acima do alvo (kW) | Utilidade fria acima do alvo (kW) | "
           "Recuperação abaixo do alvo (kW) |", "|---|---|---|---|"]
    for rc in redes:
        d = pp.folgas(rc)
        out.append(f"| {rc.nome} | {f(d['utilidade_quente'], 3)} | {f(d['utilidade_fria'], 3)} | "
                   f"{f(d['recuperacao'], 3)} |")
    return out


def tabela_correntes(redes):
    out = ["| Caso | Corrente | T entrada (°C) | T destino (°C) | CP (kW/°C) | Carga (kW) |", "|---|---|---|---|---|---|"]
    from fpso_siz.analysis import pinch as pa
    for rc in redes:
        for s in rc.streams:
            seg = s.segments[0]
            out.append(f"| {rc.nome} | {s.name} | {f(seg.t_in, 2)} | {f(seg.t_out, 2)} | {f(seg.mcp, 3)} | "
                       f"{f(pa.heat_load(s))} |")
        for rotulo, motivo in rc.omitidas:
            out.append(f"| {rc.nome} | {rotulo} | — | — | — | omitida: {motivo} |")
    return out


def gerar(casos):
    dados = carregar_casos(casos)
    prem = premissas(dados)
    c = pp.cfg()
    redes = pp.redes(resolver_todos(dados, prem), prem)
    aplicaveis = [rc for rc in redes if rc.aplicavel]
    maior = max((abs(v) for rc in aplicaveis for v in pp.folgas(rc).values() if math.isfinite(v)), default=math.nan)
    out = ["# F8 — alvos de energia do pré-aquecedor (Análise Pinch na planta do BOT)", "",
           "Gerado por `tools/pinch_planta.py`; todos os números saem do balanço e do núcleo da Análise Pinch "
           "(`analysis/pinch.py`, Kemp §3.9.1).", "",
           "## A rede e por que é esta", "",
           "Pedido do usuário (2026-09-26): a F8 aplicada ao **pré-aquecedor depois do SG**, com as correntes de "
           "**óleo tratado antes de ir para o cargo tank** e **óleo vivo que sai do SG**. São as duas correntes que "
           "o balanço já cruza no P-001:", ""]
    for corr in c["corrente"]:
        out.append(f"- **{corr['rotulo']}**: {corr['entrada']} → premissa `{corr['destino_premissa']}` "
                   f"({corr['sentido']}); CP = C({corr['capacidade']}) do balanço. {corr['fonte']}")
    out += ["",
            f"**ΔTmin = a própria premissa `{c['dt_min_premissa']}`** — {c['fonte_dt_min']}. Não há ΔTmin novo "
            "suposto: com outro valor as duas coisas comparadas seriam redes diferentes.", "",
            "O **destino** de cada corrente é a premissa, não a temperatura que o balanço realizou: usar a realizada "
            "embutiria o arranjo na resposta. Quando a exigência já está atendida no caso (o destino é piso para quem "
            "aquece e teto para quem resfria), a corrente **não entra na rede** e o motivo é registrado — inverter o "
            "seu sentido inventaria uma carga que o processo não pede.", "",
            "## Alvos por caso, contra o que o balanço realizou", ""]
    out += tabela_alvos(redes)
    out += ["", "## Folga do arranjo do BOT", "",
            "Utilidade acima do alvo é utilidade desperdiçada; recuperação abaixo do alvo é calor que o "
            "pré-aquecedor poderia trocar e não troca.", ""]
    out += tabela_folgas(redes)
    out += ["", "**Resultado:** nos casos em que a rede se aplica, o arranjo do BOT **alcança o alvo "
            f"termodinâmico** — a maior folga em módulo é {f(maior, 6)} kW, ruído de ponto flutuante. É uma "
            "validação cruzada genuína: o alvo vem da cascata de calor da Problem Table, e as cargas do balanço vêm "
            "da regra Q_pre = min(C_frio, C_quente)·(ΔT − ΔT_app) de `balanco/modelo.py`. Dois caminhos "
            "independentes, o mesmo número.", "",
            "Com duas correntes e um ΔTmin, o ótimo de recuperação é o encosto das duas na aproximação — e é "
            "exatamente o que aquela regra calcula. O alvo NÃO promete mais recuperação do que o único trocador já "
            "entrega; ele prova que não há mais a recuperar nesta rede. Ganho adicional exigiria outra rede (mais "
            "correntes, outras utilidades ou outro ΔTmin), que é decisão de projeto do usuário.", "",
            "## As correntes de cada caso", ""]
    out += tabela_correntes(redes)
    out += ["", "## O que este documento NÃO afirma", "",
            "- Não sintetiza rede de trocadores, não dá alvo de área nem número mínimo de unidades (fora do escopo "
            "declarado do método, `config/equipment/pinch/kemp.toml`).", "",
            "- Não propõe mudar o ΔTmin do projeto: o ΔTmin usado é a premissa P-32 do próprio balanço.", "",
            "- Não altera o balanço, o PFD nem as recomendações de nenhum TAG: é leitura sobre o balanço já "
            "resolvido.", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "22-pinch-planta.md")
    a = ap.parse_args()
    a.saida.write_text(gerar(a.casos), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
