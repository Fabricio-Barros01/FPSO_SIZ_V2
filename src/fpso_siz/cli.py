"""Linha de comando `fpso-siz`. Invariante 4: não nomeia parâmetro nem grandeza; só itera
os descritores declarados em TOML (premissas, colunas, verificações)."""
import argparse
import sys
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import carregar_casos, descritores_premissas, premissas
from fpso_siz.balanco.exportacao import colunas_correntes, estrutura_balanco, tabela_correntes
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.output.arquivos import escrever_csv, escrever_json
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.balanco import memorial

ARQ_JSON = "balanco.json"
ARQ_CSV = "correntes.csv"


def _alteracoes(pares):
    alt = {}
    for par in pares:
        nome, sep, valor = par.partition("=")
        if not sep:
            raise ValueError(f"--premissa espera NOME=VALOR, recebeu {par!r}")
        try:
            alt[nome.strip()] = float(valor)
        except ValueError:
            raise ValueError(f"--premissa {nome.strip()}: valor não numérico {valor!r}") from None
    return alt


def cmd_balanco(a):
    dados = carregar_casos(a.casos)
    prem = premissas(dados, **_alteracoes(a.premissa))
    resultados = resolver_todos(dados, prem)
    aud = auditar(resultados, dados, prem)
    a.saida.mkdir(parents=True, exist_ok=True)
    escrever_json(estrutura_balanco(dados, prem, resultados, aud), a.saida / ARQ_JSON)
    escrever_csv(colunas_correntes(), tabela_correntes(resultados), a.saida / ARQ_CSV)

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
    print(f"gravados: {a.saida / ARQ_JSON}, {a.saida / ARQ_CSV}")
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fpso-siz", description="FPSO_Siz — balanço preliminar e dimensionamento")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="comando", required=True)

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

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, KeyError, FileNotFoundError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e  # KeyError põe aspas no str()
        print(f"erro: {msg}", file=sys.stderr)
        return 2
