"""Peças comuns à CLI por comando e ao modo interativo."""
import shlex
from pathlib import Path

from fpso_siz.balanco.exportacao import colunas_correntes, estrutura_balanco, tabela_correntes
from fpso_siz.output.arquivos import escrever_csv, escrever_json

ARQ_JSON = "balanco.json"
ARQ_CSV = "correntes.csv"
PROG = "fpso-siz"


def alteracoes(pares):
    """['NOME=VALOR', ...] → {NOME: float}; ValueError com a entrada ofendida."""
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


def gravar_balanco(dados, prem, resultados, auditoria, pasta):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    escrever_json(estrutura_balanco(dados, prem, resultados, auditoria), pasta / ARQ_JSON)
    escrever_csv(colunas_correntes(), tabela_correntes(resultados), pasta / ARQ_CSV)
    return [pasta / ARQ_JSON, pasta / ARQ_CSV]


def comando(*partes, **opcoes):
    """Linha de comando equivalente, pronta para colar no shell. Valor lista = opção repetida;
    True = flag; None/False = omitida."""
    args = [PROG, *partes]
    for k, v in opcoes.items():
        flag = "--" + k
        for item in (v if isinstance(v, list) else [v]):
            if item is True:
                args.append(flag)
            elif item not in (None, False):
                args += [flag, str(item)]
    return shlex.join(args)
