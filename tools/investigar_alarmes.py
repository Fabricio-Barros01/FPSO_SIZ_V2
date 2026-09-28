"""Relatório dos alarmes de inviabilidade (config/pfd/alarmes.toml).

Roda a planta sem e com as propostas (config/pfd/pendencias_propostas.toml), lista os TAGs
inviáveis com a evidência do motor, as hipóteses registradas e o resultado de cada variante de
estudo pelo mesmo serviço por TAG (`pfd/investigacao.executar_variante`). É daqui — e não do
memorial — que as variantes são executadas. Determinístico: os números vêm do código.

    uv run python tools/investigar_alarmes.py [--saida saida/alarmes.md]
"""
import argparse
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import investigacao as inv
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
PROPOSTAS = RAIZ / "src" / "fpso_siz" / "config" / "pfd" / "pendencias_propostas.toml"


def f(x, casas=0):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def secao_planta(titulo, ctx, planta):
    if not inv.alarmes(planta):
        return [f"## {titulo}", "", "Nenhum TAG inviável: não há alarme a investigar.", ""]
    out = [f"## {titulo}", "", "| TAG | Estado | Casos com solução isolados | Casos sem solução isolados | Motivo do motor |",
           "|---|---|---|---|---|"]
    for rt, ev, _ in inv.alarmes(planta):
        viaveis = ", ".join(f"{n[:6]} ({f(x)})" for n, x in ev.casos_viaveis) or "—"
        inviaveis = ", ".join(n[:6] for n, _ in ev.casos_inviaveis) or "—"
        out.append(f"| {rt.tag.tag} | inviável (alarme) | {viaveis} | {inviaveis} | {ev.mensagem[:220]}… |")
    out += ["", "### Variantes executadas (mesmo motor)", "",
            "| TAG | Variante | Origem do valor | Resultado |", "|---|---|---|---|"]
    for ident, _, v, rt in inv.investigar(ctx, planta):
        r = rt.resultado
        if r.feasible:
            res = f"viável, x = {f(r.x)}"
        else:
            teto = f" (teto {f(r.ceiling)} mm, {r.ceiling_case})" if math.isfinite(r.ceiling) else ""
            res = f"segue inviável{teto}: {r.message[:160]}…"
        out.append(f"| {ident} | {v['rotulo']} | {v['origem']} | {res} |")
    return out + [""]


def estudo_p44(ctx, planta):
    """Bombas com e sem a P-44 (variante sem_p44: banda em todos os casos, regra do Julia)."""
    out = ["## Estudo da P-44 (banda de velocidade pelo caso de projeto)", "",
           "| TAG | Com a P-44 (padrão) | Sem a P-44 (variante `sem_p44`) |", "|---|---|---|"]
    v = inv.variante("sem_p44")
    for rt in planta.tags:
        if rt.tag.metodo != "moran" or rt.resultado is None:
            continue
        sem = inv.executar_variante(ctx, rt.tag.tag, v).resultado
        com = rt.resultado
        txt = [f"DN {f(r.x)} mm, H {f(r.y, 1)} m" if r.feasible else f"inviável: {r.message[:160]}…" for r in (com, sem)]
        out.append(f"| {rt.tag.tag} | {txt[0]} | {txt[1]} |")
    return out + [""]


def hipoteses():
    out = ["## Hipóteses registradas (config/pfd/alarmes.toml)", ""]
    classes = inv.cfg()["classes"]
    for a in inv.cfg()["alarme"]:
        out += [f"### {a['tag']} — investigação {a['estado']}", "", a["resumo"], ""]
        out += [f"- **{classes[h['classe']]}**: {h['texto']}" for h in a["hipoteses"]]
        out.append("")
    return out


def gerar():
    dados = carregar_casos(CASOS)
    ctx0 = servico.Contexto(dados)
    p0 = dimensionar(contexto=ctx0)
    ctx1 = servico.Contexto(dados, propostas=mod_propostas.carregar(PROPOSTAS))
    p1 = dimensionar(contexto=ctx1)
    linhas = ["# Alarmes de inviabilidade: anotação e investigação", "",
              "Gerado por `tools/investigar_alarmes.py`; todos os números saem do serviço por TAG.", "",
              "A unidade do BOT (I-ET-3010.2K-1200-941-P4X-001, rev. C, em `docs/bot/`) é um projeto básico real:",
              "um TAG sem equipamento que atenda aos casos é **alarme** de erro de premissa, numérico ou de modelo,",
              "nunca conclusão de projeto. Nenhuma variante altera o cálculo padrão; a decisão é do usuário.", ""]
    linhas += secao_planta("Planta sem propostas (catálogo com fonte)", ctx0, p0)
    linhas += secao_planta("Planta com as propostas (pendencias_propostas.toml, status proposto)", ctx1, p1)
    linhas += estudo_p44(ctx1, p1)
    linhas += hipoteses()
    return "\n".join(linhas) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "alarmes.md")
    a = ap.parse_args()
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(gerar(), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
