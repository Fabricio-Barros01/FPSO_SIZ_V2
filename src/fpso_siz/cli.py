"""Linha de comando `fpso-siz`. Invariante 4: não nomeia parâmetro nem grandeza; só itera
os descritores declarados em TOML (premissas, colunas, verificações) e o registro de
métodos. Sem argumentos, num terminal, abre o modo interativo."""
import argparse
import sys
import tomllib
from pathlib import Path

import fpso_siz.sizing  # noqa: F401  (registra os métodos de dimensionamento)
from fpso_siz import __version__
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import carregar_casos, descritores_premissas, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.configuracao import exemplos
from fpso_siz.core.motor import size_envelope
from fpso_siz.output import dimensionamento
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.balanco import memorial
from fpso_siz.output.terminal.comum import alteracoes as _alteracoes
from fpso_siz.output.terminal.comum import gravar_balanco
from fpso_siz.output.terminal.estilo import Estilo
from fpso_siz.output.terminal.relatorio import resumo_dimensionamento
from fpso_siz.output.terminal.sessao import Sessao

COLUNAS = 79  # largura dos resumos fora do modo interativo (saída pode ser arquivo)


def cmd_balanco(a):
    dados = carregar_casos(a.casos)
    prem = premissas(dados, **_alteracoes(a.premissa))
    resultados = resolver_todos(dados, prem)
    aud = auditar(resultados, dados, prem)
    arq_json, arq_csv = gravar_balanco(dados, prem, resultados, aud, a.saida)

    nao = [r for r in resultados if not r.convergiu]
    print(f"{dados.origem} (sha256 {dados.sha256[:12]}…): {len(resultados)} casos, "
          f"{len(resultados) - len(nao)} convergidos")
    for r in nao:
        print(f"  ATENÇÃO caso {r.num}: reciclo não convergiu ({r.iters + 1} iterações, "
              f"resíduo {r.residuo_reciclo:.3e})")
    alteradas = [d for d in descritores_premissas(dados) if prem[d["nome"]] != d["valor"]]
    for d in alteradas:
        print(f"  premissa alterada {d['id']} {d['nome']} = {prem[d['nome']]} {d['unidade']} "
              f"(base {d['valor']})")
    print("auditoria independente (maior |desvio| nos casos):")
    for v in aud:
        print(f"  {v['id']:<22} {v['max_desvio_abs']:.3e}  {v['unidade']}")
    print(f"gravados: {arq_json}, {arq_csv}")
    return 1 if nao else 0


def cmd_memorial(a):
    dados = carregar_casos(a.casos)
    prem = premissas(dados, **_alteracoes(a.premissa))
    resultados = resolver_todos(dados, prem)
    tex = memorial.gravar(dados, prem, resultados, a.saida, a.layout)
    print(f"memorial ({a.layout}): {tex}")
    if a.pdf:
        try:
            print(f"PDF: {compilacao.compilar(tex)}")
        except compilacao.ErroCompilacao as e:
            print(f"erro: {e}", file=sys.stderr)
            return 3
    return 0


def cmd_premissas(a):
    dados = carregar_casos(a.casos) if a.casos else None
    for d in descritores_premissas(dados):
        valor = d["valor"] if d["valor"] is not None else f"({d['origem']})"
        print(f"{d['id']:<5} {d['nome']:<12} {valor!s:<24} {d['unidade']:<22} {d['descricao']}")
    return 0


def cmd_dimensionar(a):
    if a.exemplo:
        cfg, origem = exemplos()[a.exemplo], f"exemplo:{a.exemplo}"
    else:
        cfg, origem = tomllib.loads(a.casos.read_text(encoding="utf-8")), str(a.casos)
    declarado = cfg.get("equipment")
    if a.equipamento and declarado and declarado != a.equipamento:
        raise ValueError(f"o arquivo declara equipment = {declarado!r}, mas --equipamento = {a.equipamento!r}")
    eq_id = a.equipamento or declarado
    if not eq_id:
        raise ValueError("informe --equipamento: o arquivo de casos não declara `equipment`")
    eq, m = registro.resolver(eq_id, a.metodo)
    casos = case_set_from_config(cfg)
    r = size_envelope(eq, m, casos)
    print("\n".join(resumo_dimensionamento(eq, m, r, Estilo.para(sys.stdout), COLUNAS)).lstrip("\n"))
    if a.saida:
        print("gravados: " + ", ".join(str(p) for p in dimensionamento.gravar(eq, m, casos, r, a.saida, origem)))
    return 0 if r.feasible else 1


def cmd_interativo(a):
    return Sessao(casos=a.casos).rodar()


def cmd_pfd(a):
    from fpso_siz.output import pfd
    from fpso_siz.output.terminal.pfd import resumo
    from fpso_siz.pfd.planta import dimensionar

    dados = carregar_casos(a.casos)
    prem = premissas(dados, **_alteracoes(a.premissa))
    ajustes = tomllib.loads(a.ajustes.read_text(encoding="utf-8")) if a.ajustes else {}
    planta = dimensionar(dados, prem, ajustes)
    print("\n".join(resumo(planta, Estilo.para(sys.stdout), COLUNAS)).lstrip("\n"))
    if a.saida:
        print("gravados: " + ", ".join(str(p) for p in pfd.gravar(planta, a.saida)))
    return 0 if planta.completa else 1


def _terminal():
    return sys.stdin.isatty() and sys.stdout.isatty()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fpso-siz", description="FPSO_Siz — balanço preliminar e dimensionamento. "
                                 "Sem argumentos, num terminal, abre o modo interativo.")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="comando", required=True)

    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        if _terminal():
            return Sessao().rodar()

    b = sub.add_parser("balanco", help="balanço de massa e energia dos casos de projeto")
    b.add_argument("--casos", required=True, type=Path, help="arquivo de casos (JSON do BOT)")
    b.add_argument("--saida", required=True, type=Path, help="pasta de saída (JSON + CSV)")
    b.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR",
                   help="sobrescreve uma premissa (repetível); ver `fpso-siz premissas`")
    b.set_defaults(func=cmd_balanco)

    m = sub.add_parser("memorial", help="memorial de cálculo do balanço em LaTeX (A4)")
    m.add_argument("--casos", required=True, type=Path, help="arquivo de casos (JSON do BOT)")
    m.add_argument("--saida", required=True, type=Path, help="pasta de saída (main.tex)")
    m.add_argument("--layout", choices=sorted(memorial.LAYOUTS), default="original",
                   help="original = idêntico ao script de referência; senai = template SENAI CETIQT")
    m.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR")
    m.add_argument("--pdf", action="store_true", help="compila com latexmk, se instalado")
    m.set_defaults(func=cmd_memorial)

    p = sub.add_parser("premissas", help="lista as premissas do balanço (id, valor, unidade, fonte)")
    p.add_argument("--casos", type=Path, help="arquivo de casos, para os valores que vêm dele")
    p.set_defaults(func=cmd_premissas)

    d = sub.add_parser("dimensionar", help="dimensiona um equipamento para um conjunto de casos (envelope)")
    fonte = d.add_mutually_exclusive_group(required=True)
    fonte.add_argument("--casos", type=Path, help="arquivo TOML com blocos [[case]]")
    fonte.add_argument("--exemplo", choices=sorted(exemplos()), help="arquivo de casos de exemplo embutido")
    d.add_argument("--equipamento", choices=[e.method_id for e in registro.equipments()],
                   help="dispensável se o arquivo declara `equipment`")
    d.add_argument("--metodo", help="id do método (padrão: o primeiro registrado para o equipamento)")
    d.add_argument("--saida", type=Path, help="pasta de saída (JSON + CSV); sem ela, só o resumo")
    d.set_defaults(func=cmd_dimensionar)

    f = sub.add_parser("pfd", help="dimensiona os TAGs da planta a partir do balanço")
    f.add_argument("--casos", required=True, type=Path, help="arquivo de casos (JSON do BOT)")
    f.add_argument("--ajustes", type=Path, help="TOML de entradas por TAG e por caso")
    f.add_argument("--saida", type=Path, help="pasta de saída (JSON por TAG + planta.csv)")
    f.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR")
    f.set_defaults(func=cmd_pfd)

    i = sub.add_parser("interativo", help="assistente: contexto, casos, resumo e exportação opcional")
    i.add_argument("--casos", type=Path, help="arquivo de casos do balanço (JSON do BOT)")
    i.set_defaults(func=cmd_interativo)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, KeyError, FileNotFoundError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e  # KeyError põe aspas no str()
        print(f"erro: {msg}", file=sys.stderr)
        return 2
