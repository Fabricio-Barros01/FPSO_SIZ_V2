import tomllib
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import REFERENCIA, resolver_todos
from fpso_siz.pfd.planta import dimensionar

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="session")
def planta_base():
    return dimensionar(carregar_casos(FIXTURES / "python_ref" / "design_cases_bot.json"))


@pytest.fixture(scope="session")
def ajustes_sinteticos():
    return tomllib.loads((FIXTURES / "pfd" / "ajustes_sinteticos.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def planta_ajustada(planta_base, ajustes_sinteticos):
    """As entradas sintéticas da F10b foram escritas para a alocação do PFD F1 (óleo no tubo do
    P-002/P-003): a planta ajustada roda com topologia_julia=True."""
    return dimensionar(planta_base.dados, ajustes=ajustes_sinteticos, balanco=planta_base.balanco,
                       topologia_julia=True)


@pytest.fixture(scope="session")
def planta_referencia(planta_base):
    """A planta sobre o balanço com a regra do FWKO do script de referência (modo de paridade):
    as fixtures do PFD F1 do Julia e da F10b foram geradas com ela. Viscosidade do óleo morto
    (oleo_vivo=False) e alocação de correntes do PFD F1 (topologia_julia=True), como naquelas fases."""
    dados = planta_base.dados
    return dimensionar(dados, balanco=resolver_todos(dados, premissas(dados), REFERENCIA), oleo_vivo=False,
                       topologia_julia=True)


@pytest.fixture(scope="session")
def planta_referencia_ajustada(planta_referencia, ajustes_sinteticos):
    return dimensionar(planta_referencia.dados, ajustes=ajustes_sinteticos, balanco=planta_referencia.balanco,
                       oleo_vivo=False, topologia_julia=True)


@pytest.fixture(scope="session")
def planta_oleo_morto(planta_base):
    """A planta padrão (regra de eficiência do FWKO) com a viscosidade do óleo morto do BOT: o
    modo das fases F10w–F13, em que o SG-001 fica em alarme (docs/validacao/16-oleo-vivo.md)."""
    return dimensionar(planta_base.dados, balanco=planta_base.balanco, oleo_vivo=False)


@pytest.fixture(scope="session")
def planta_propostas(planta_base):
    """A planta padrão com as propostas do pacote (config/pfd/pendencias_propostas.toml)."""
    from fpso_siz.pfd import equipamento as servico
    from fpso_siz.pfd import propostas as mod_propostas
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco, propostas=mod_propostas.padrao())
    return dimensionar(contexto=ctx)
