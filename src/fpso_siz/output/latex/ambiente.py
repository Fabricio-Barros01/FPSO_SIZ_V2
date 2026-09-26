"""Ambiente Jinja2 com delimitadores que não colidem com LaTeX.

    << expr >>      valor
    <% bloco %>     controle (a linha do bloco some: trim_blocks + lstrip_blocks)
    <# comentário #>
"""
from importlib.resources import files

import jinja2

from fpso_siz.output.latex import formatacao


def _carregador(pacotes):
    """Procura o template nos pacotes, em ordem (o MC por TAG reaproveita o preâmbulo do
    memorial do balanço)."""
    def ler(nome):
        for pacote in pacotes:
            arq = files(pacote).joinpath("templates", nome)
            if arq.is_file():
                return arq.read_text(encoding="utf-8")
        return None
    return jinja2.FunctionLoader(ler)


def ambiente(*pacotes):
    env = jinja2.Environment(
        loader=_carregador(pacotes),
        block_start_string="<%", block_end_string="%>",
        variable_start_string="<<", variable_end_string=">>",
        comment_start_string="<#", comment_end_string="#>",
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
        autoescape=False, undefined=jinja2.StrictUndefined,
    )
    env.filters.update(br=formatacao.br, mb=formatacao.mb, sci=formatacao.sci, esc=formatacao.esc, ids=formatacao.ids, mbn=formatacao.mbn,
                       sig=formatacao.sig, tx=formatacao.tx, sigt=formatacao.sigt, unid=formatacao.unid,
                       mapa=lambda chaves, d: [d[k] for k in chaves])
    env.globals.update(zip=zip)
    return env
