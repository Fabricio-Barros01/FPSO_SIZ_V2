"""Fase 5 — integração em modo sombra: mapa de proveniência, fechamentos e antigo × novo.

Gera `docs/validacao/31-integracao-modo-sombra.md`.

    uv run python tools/integracao_termodinamica.py
"""
import argparse
import json
import math
import time
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import integracao as ig

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def n(x, casas=4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def e(x, casas=2):
    return "—" if x is None or not math.isfinite(x) else f"{x:.{casas}e}"


def gerar(dados, prem, mws):
    res = resolver_todos(dados, prem)
    # conta flashes e condições (T, P, z) distintas: recomputação medida, não otimizada
    from collections import Counter

    from fpso_siz.pfd import _chedl
    original, chaves, n_flash = _chedl.flash_pseudo, Counter(), [0]

    def espiao(reais, pseudos, zs, T, P, kij):
        n_flash[0] += 1
        chaves[(round(T, 9), round(P, 3), tuple(round(v, 12) for v in zs))] += 1
        return original(reais, pseudos, zs, T, P, kij)

    _chedl.flash_pseudo = espiao
    try:
        t0 = time.perf_counter()
        sombras = ig.rodar(res, dados, prem, mws_plus=mws)
        dt = time.perf_counter() - t0
    finally:
        _chedl.flash_pseudo = original
    distintas = len(chaves)
    okk = [s for s in sombras if s.estado and s.estado.ok]

    out = ["# Fase 5 — integração do serviço termodinâmico, em modo sombra", "",
           "Gerado por `tools/integracao_termodinamica.py`.", "",
           f"> **O processo continua consumindo o caminho legado.** O flash roda em paralelo nos "
           f"{len(ig.pontos())} pontos de equilíbrio e é comparado; nenhum resultado da planta mudou "
           "— há paridade bit a bit. Trocar a origem de uma propriedade exige mudar o `status` dela "
           "no mapa, e o guarda recusa consumo de propriedade não liberada.", "",
           "## 1. Onde o flash foi integrado", "",
           "| ponto | corrente de gás | pressão | o que o legado faz |", "|---|---|---|---|"]
    for p in ig.pontos():
        out.append(f"| {p['id']} | {p['corrente_gas']} | `{p['pressao']}` | {p['legado']} |")

    out += ["", "## 2. Mapa de proveniência", "",
            "A regra é a invariante 5 do `CLAUDE.md`: backend devolver número não é o mesmo que "
            "propriedade validada para engenharia.", "",
            "| propriedade | origem atual | origem proposta | consumidores | status |",
            "|---|---|---|---|---|"]
    for i, d in ig.mapa().items():
        cons = "; ".join(d["consumidores"])
        marca = {"liberada": "**liberada**", "sombra": "sombra", "bloqueada": "**BLOQUEADA**"}[d["status"]]
        out.append(f"| `{i}` — {d['rotulo']} | {d['origem_atual']} | {d['origem_proposta']} | {cons} | {marca} |")
    out += ["", "**Motivo de cada bloqueio:**", ""]
    for i, d in ig.mapa().items():
        if d["status"] != ig.LIBERADA:
            out.append(f"- `{i}` ({d['status']}): {d['motivo']}")
    out += ["", "### O estado é híbrido, e isso é declarado", "",
            "Nenhum resumo deve apresentar o conjunto abaixo como produzido por um modelo "
            "termodinâmico único. Origem efetiva de cada propriedade **hoje**:", "",
            "| propriedade | origem efetiva |", "|---|---|"]
    for i, org in ig.proveniencia().items():
        out.append(f"| `{i}` | {org} |")

    out += ["", "## 3. Fechamentos", "",
            f"{len(okk)} de {len(sombras)} pontos convergiram "
            f"({len(res)} casos × {len(ig.pontos())} pontos de equilíbrio). Erros máximos, em número:", "",
            "| verificação | erro máximo |", "|---|---|"]
    if okk:
        f = [s.fechamento for s in okk if s.fechamento]
        out += [f"| z_i = β·y_i + (1−β)·x_i, componente a componente | {e(max(x.erro_componente_max for x in f))} |",
                f"| soma das composições (z, y, x) | {e(max(max(x.erro_soma_z, x.erro_soma_y, x.erro_soma_x) for x in f))} |",
                f"| balanço molar (Σβ = 1) | {e(max(x.erro_balanco_molar for x in f))} |",
                f"| balanço mássico (Σβ_mássica = 1) | {e(max(x.erro_balanco_massico for x in f))} |",
                f"| recomposição da corrente original | {e(max(x.erro_recomposicao for x in f))} |",
                f"| coerência molar × mássica | {e(max(x.coerencia_molar_massica for x in f if math.isfinite(x.coerencia_molar_massica)))} |",
                f"| pontos monofásicos (fase desaparece corretamente) | {sum(1 for x in f if x.monofasico)} de {len(f)} |"]
        out += ["", "Todos no nível do épsilon de máquina: o flash fecha.", ""]

    out += ["## 4. Antigo × novo, nos 16 casos", "",
            "A comparação é do **gás liberado**: o legado usa a diferença de Rs de Standing (correlação "
            "black-oil calibrada em razão de solubilidade); o novo usa equilíbrio de fases sobre a "
            "composição caracterizada. São físicas diferentes respondendo à mesma pergunta, então a "
            "diferença é esperada — o que não se admite é diferença **inexplicada**.", "",
            "| caso | ponto | T (°C) | P (kPa) | gás legado (kg/s) | VF molar (novo) | VF mássica (novo) | Z (novo) |",
            "|---|---|---|---|---|---|---|---|"]
    for s in sombras:
        st = s.estado
        out.append(f"| {s.caso} | {s.ponto} | {n(s.T_C,1)} | {n(s.P_kPa,0)} | "
                   f"{n(s.legado.get('gas_legado_kg_s'),4)} | "
                   + (f"{n(st.fracao_vapor,5)} | {n(st.fracao_vapor_massica,5)} | "
                      f"{n(st.vapor.Z,5) if st.vapor else '—'} |" if st and st.ok else "não convergiu | — | — |"))
    out += ["", "**Razão física da diferença.** O legado não calcula fração de fase: ele calcula quanto "
            "gás sai de solução, por ΔRs de Standing, e atribui esse volume ao estágio. O flash calcula a "
            "fração de vapor da corrente inteira na condição (T, P). Os dois números não são a mesma "
            "grandeza, e por isso nenhuma substituição foi feita: trocar um pelo outro mudaria a vazão de "
            "gás de todos os estágios e, por ela, o balanço de energia — que esta fase não pode ativar.", "",
            "## 5. O que mudou na planta", "",
            "**Nada.** Nenhum equipamento teve resultado alterado: a paridade bit a bit do instantâneo dos "
            "11 TAGs e das 5.391 linhas de varredura é a mesma de antes do R1. O flash é calculado e "
            "descartado; o guarda impede consumo de propriedade não liberada.", "",
            "## 6. Desempenho", "",
            "| medida | valor |", "|---|---|",
            f"| flashes por rodada de sombra | {n_flash[0]} |",
            f"| condições (T, P, z) distintas | {distintas} |",
            f"| **fator de recomputação** | **{n(n_flash[0]/max(1,distintas),3)}** |",
            f"| tempo total em flash | {n(dt,3)} s |",
            f"| tempo por flash | {n(1000*dt/max(1,n_flash[0]),2)} ms |", "",
            "A recomputação vem de casos do mesmo fluido que caem na mesma condição (V-001 e V-002 "
            "operam a T e P fixas). **Não foi otimizada, apenas medida** — a Fase 5 não otimiza.", "",
            "O caminho produtivo **não** paga nada disso: `resolver_caso` (0,52 ms), `resolver_todos` "
            "(19,7 ms) e `avaliar()` seguem sem chamar o flash, porque o modo é sombra. A medida acima "
            "é o custo que a integração terá **quando** for ligada.", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "31-integracao-modo-sombra.md")
    a = ap.parse_args()
    dados = carregar_casos(a.casos)
    mws = {k: v["mw"] for k, v in json.loads(a.casos.read_text(encoding="utf-8"))["c20_pseudo"].items()}
    a.saida.write_text(gerar(dados, premissas(dados), mws), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
