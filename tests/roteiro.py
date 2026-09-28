"""Sessões interativas roteirizadas (entrada injetada, saída capturada) para os testes.
Os números das opções vêm de config/interativo.toml e do catálogo de TAGs, não de literais."""
import io
import shlex
from datetime import datetime
from pathlib import Path

from fpso_siz.cli import main
from fpso_siz.core.configuracao import carregar
from fpso_siz.output.terminal.estilo import Estilo
from fpso_siz.output.terminal.sessao import Sessao

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
AGORA = datetime(2026, 9, 23, 14, 2, 11)


def op(menu, acao):
    ids = [a["id"] for a in carregar("interativo.toml")["menus"][menu]["acoes"]]
    return str(ids.index(acao) + 1)


def tag_op(ident):
    """Número do TAG na lista 'Qual equipamento?' (ordem do catálogo)."""
    from fpso_siz.pfd.tags import tags
    return str([t.tag for t in tags()].index(ident) + 1)


def abrir_tag(ident, modo=None):
    """Equipamento / TAG → o TAG → (modo de preenchimento, se o TAG ainda não tem estado)."""
    passos = [op("principal", "equipamento"), tag_op(ident)]
    return passos + ([op("preenchimento", modo)] if modo else [])


def roteiro(*respostas):
    fila = list(respostas)

    def entrada(prompt):
        if not fila:
            raise EOFError
        r = fila.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r
    return entrada


def sessao(*respostas, casos=CASOS, colunas=100, cor=False, unicode=True, ajustes=None, propostas=False):
    """Sessão roteirizada; por padrão SEM os valores propostos (os roteiros das fases F10b/F10c
    exercitam o preenchimento das lacunas). `propostas=None` usa o padrão da aplicação."""
    out = io.StringIO()
    s = Sessao(casos=casos, entrada=roteiro(*respostas), saida=out, estilo=Estilo(cor, unicode), colunas=colunas,
               agora=lambda: AGORA, ajustes=ajustes, propostas=propostas)
    return s, out


def rodar(*respostas, **kw):
    s, out = sessao(*respostas, **kw)
    rc = s.rodar()
    return rc, out.getvalue(), s


def comandos_repetir(texto):
    bloco = texto.split("Para repetir sem o assistente:")[-1]
    return [shlex.split(li.strip())[1:] for li in bloco.splitlines() if li.strip().startswith("fpso-siz ")]


def repetir_comando(texto):
    """Executa, via main(), cada linha 'fpso-siz …' que a sessão mandou repetir."""
    cmds = comandos_repetir(texto)
    assert cmds
    return [main(c) for c in cmds]
