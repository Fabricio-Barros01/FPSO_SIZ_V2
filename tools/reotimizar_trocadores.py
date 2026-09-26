"""Reotimização discreta dos trocadores P-002 e P-003 (F10x.7): docs/validacao/18-trocadores.md.

Roda pfd/reotimizacao.buscar (grade e regras em config/pfd/reotimizacao.toml) com as
propostas do pacote e o óleo vivo (o padrão da planta), e escreve, por TAG: cada etapa (número
de cascos, candidatos, viáveis, bloqueios do melhor), o candidato escolhido e a operação de
cada caso no feixe escolhido. Determinístico; lento (o P-003 tem 16 casos).

    uv run python tools/reotimizar_trocadores.py [--saida docs/validacao/18-trocadores.md]
"""
import argparse
import collections
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd import reotimizacao as ro

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
ROTULOS = {"comprimento": "comprimento de tubo > l_tubo_max", "casco": "casco > d_casco_max",
           "dittus_boelter": "fora da faixa de Dittus-Boelter", "v_max": "v > v_max", "v_min": "v < v_min",
           "v_min_projeto": "v < v_min no caso de projeto", "calculo": "cálculo do feixe não fecha",
           "lacuna": "entrada em lacuna", "preparacao": "caso não prepara"}


def f(x, casas=0):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def bloqueios_txt(c, nomes):
    grupos = collections.defaultdict(list)
    for crit, i in c.bloqueios:
        grupos[crit].append(nomes[i][:6] if i >= 0 else "")
    return "; ".join(f"{ROTULOS.get(k, k)}" + (f" ({', '.join(v)})" if any(v) else "") for k, v in grupos.items()) or "—"


def secao(ctx, ident):
    etapas = ro.buscar(ctx, ident)
    c = ro.escolhido(etapas)
    nomes = [n for n, _ in c.rt.entradas.case_set().expand()]
    t = ro.cfg()["tags"][ident]
    out = [f"## {ident}", "", f"Divisão permitida: `{t['divisao']}` quando o melhor candidato tem o bloqueio "
           f"`{t['gatilho']}` (até {t['n_cascos_max']} cascos, limite da busca).", "",
           "| Cascos | Candidatos | Viáveis | Melhor candidato: bloqueios |", "|---|---|---|---|"]
    for e in etapas:
        out.append(f"| {e.cascos} | {len(e.candidatos)} | {sum(x.viavel for x in e.candidatos)} | "
                   f"{bloqueios_txt(e.melhor, nomes)} |")
    grade = {k: v for k, v in c.valores.items() if k in ro.cfg()["grade"]}
    out += ["", "**Escolhido** (" + ("viável" if c.viavel else "inviável: melhor feixe encontrado") + "): "
            + ", ".join(f"`{k}` = {v:g}" for k, v in c.valores.items()) + ".", "",
            f"Tubos por passe {f(c.x)}; comprimento por casco {f(c.y, 2)} m; área total {f(c.area, 1)} m²; "
            f"bloqueios: {bloqueios_txt(c, nomes)}.", "",
            "| Caso | Papel | Carga (kW) | v (m/s) | Re | Dittus-Boelter | h_i (W/m²K) | h_o (W/m²K) | L exigido (m) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for o in ro.operacao(c):
        out.append(f"| {o['caso']} | {o['papel']} | {f(o['q'] / 1000)} | {f(o['v'], 2)} | {f(o['re'])} | "
                   f"{'válida' if o['nu_valido'] else 'FORA'} | {f(o['h_i'])} | {f(o['h_o'])} | {f(o['l'], 2)} |")
    return out + [""], grade, c


def gerar():
    dados = carregar_casos(CASOS)
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())
    linhas = ["# F10x.7 — trocadores P-002 e P-003: reotimização discreta", "",
              "Gerado por `tools/reotimizar_trocadores.py` (grade e regras em `config/pfd/reotimizacao.toml`); "
              "todos os números saem do serviço por TAG. Topologia P-46 (óleo no casco), P-45 ativa, limites "
              "l_tubo_max = 6 m e d_casco_max = 2.500 mm mantidos.", ""]
    escolhas = {}
    for ident in ro.cfg()["tags"]:
        sec, _, c = secao(ctx, ident)
        linhas += sec
        escolhas[ident] = c
    return "\n".join(linhas) + "\n", escolhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "18-trocadores.md")
    a = ap.parse_args()
    texto, escolhas = gerar()
    a.saida.write_text(texto, encoding="utf-8")
    for ident, c in escolhas.items():
        print(ident, c.viavel, c.valores, c.bloqueios)
    print(a.saida)


if __name__ == "__main__":
    main()
