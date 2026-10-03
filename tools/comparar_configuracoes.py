"""Comparação finita de configurações e pacote para o HYSYS (docs/validacao/47).

Avalia o domínio declarado do subproblema (`config/pfd/otimizacao.toml`, padrão `configuracao`)
com a configuração atual primeiro, até o limite de avaliações, pelo mesmo avaliador da otimização
(`pfd/otimizacao.comparar`); classifica cada candidato (inviável, decisão pendente, verificação
incompleta, viável) com os motivos; e grava o relatório e o pacote de dados para o HYSYS da
configuração de referência, com a comparação dentro.

    uv run python tools/comparar_configuracoes.py [--limite N] [--processos N] [--saida saida/hysys]
"""
import argparse
import math
import os
import time
from pathlib import Path

from fpso_siz import _otim
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.output import hysys
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
SITUACAO = {"viavel": "viável", "verificacao_incompleta": "admissível; verificação incompleta",
            "decisao_pendente": "admissível; decisão pendente", "inviavel": "inviável",
            "nao_avaliavel": "não avaliável (falta dado)", "nao_convergiu": "balanço não convergiu"}


def f(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def motivos(a):
    return "; ".join(f"{m['tipo']}: {m['id']} ({', '.join(m['criterios'])})" if m["criterios"] else
                     f"{m['tipo']}: {m['id']}" for m in a.motivos()) or "—"


def relatorio(c, segundos):
    ids_var = [v["id"] for v in ot.variaveis(c.sub)]
    objs = ot.objetivos(c.sub)
    frente = {a.x for a in c.frente()}
    out = [f"# Comparação de configurações — `{c.sub}`", "",
           f"{ot.subproblema(c.sub)['rotulo']}. {ot.subproblema(c.sub)['fonte']}.", "",
           "Critério: dominância de Pareto entre candidatos **admissíveis** (sem violação de requisito "
           "obrigatório), nos objetivos abaixo; sem pesos e sem somar grandezas de unidades diferentes. "
           "Admissível com decisão pendente ou verificação incompleta **não é aprovado**.", "",
           "| Objetivo | Unidade | Definição |", "|---|---|---|"]
    out += [f"| {o['rotulo']} (`{o['id']}`) | {o['unidade']} | {o['fonte']} |" for o in objs]
    out += ["", f"Domínio: {len(c.dominio)} pontos; limite: {c.limite} avaliações; avaliados: {len(c.avaliacoes)} "
            f"em {f(segundos, 0)} s" + (f"; **limite atingido**, {len(c.nao_avaliados)} sem avaliar (resultado parcial)."
                                        if c.limite_atingido else "."), "",
            f"| {' | '.join(ids_var)} | " + " | ".join(o["id"] for o in objs) + " | situação | não dominado | motivos |",
            "|" + "---:|" * (len(ids_var) + len(objs)) + "---|---|---|"]
    for i, a in enumerate(c.avaliacoes):
        xs = " | ".join(f(v, 0) for v in a.x)
        out.append(f"| {xs} | " + " | ".join(f(a.objetivos[o['id']]) for o in objs)
                   + f" | {SITUACAO[a.situacao]}{' (referência)' if i == 0 else ''} | "
                   f"{'sim' if a.x in frente else 'não'} | {motivos(a)} |")
    aprovados = c.com_situacao("viavel")
    out += ["", ("Nenhum candidato atende a todos os critérios: " + ", ".join(
        f"{len(c.com_situacao(s))} {SITUACAO[s]}" for s in SITUACAO if c.com_situacao(s)) + "."
                 if not aprovados else f"{len(aprovados)} candidato(s) viável(is)."), ""]
    if c.nao_avaliados:
        out += ["Não avaliados (limite): " + "; ".join(str(dict(zip(ids_var, x))) for x in c.nao_avaliados), ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--sub", default="configuracao")
    ap.add_argument("--limite", type=int, default=None, help="máximo de avaliações (padrão: o declarado no TOML)")
    ap.add_argument("--processos", type=int, default=max(1, (os.cpu_count() or 2) // 4))
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "hysys")
    a = ap.parse_args()
    dados = carregar_casos(a.casos)
    t0 = time.perf_counter()
    c = ot.comparar(dados, a.sub, a.limite, avaliar_pontos=lambda pts: _otim.avaliar_pontos(
        dados, pts, sub=a.sub, processos=a.processos))
    segundos = time.perf_counter() - t0
    planta = dimensionar(contexto=servico.Contexto(dados, propostas=mod_propostas.padrao()))
    arquivos = hysys.gravar(planta, a.saida, c)
    (a.saida / "comparacao.md").write_text(relatorio(c, segundos), encoding="utf-8")
    print("\n".join(str(p) for p in [*arquivos, a.saida / "comparacao.md"]))


if __name__ == "__main__":
    main()
