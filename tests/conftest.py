import tomllib
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.pfd.planta import dimensionar

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def planta_base():
    """A planta só com o que tem fonte (sem as propostas): as lacunas ficam abertas."""
    return dimensionar(carregar_casos(FIXTURES / "python_ref" / "design_cases_bot.json"))


@pytest.fixture(scope="session")
def ajustes_sinteticos():
    return tomllib.loads((FIXTURES / "pfd" / "ajustes_sinteticos.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def planta_ajustada(planta_base, ajustes_sinteticos):
    """A planta com entradas sintéticas para as lacunas (exercita os métodos sem as propostas)."""
    return dimensionar(planta_base.dados, ajustes=ajustes_sinteticos, balanco=planta_base.balanco)


@pytest.fixture(scope="session")
def planta_propostas(planta_base):
    """A planta produtiva: as propostas do pacote (config/pfd/pendencias_propostas.toml)."""
    from fpso_siz.pfd import equipamento as servico
    from fpso_siz.pfd import propostas as mod_propostas
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco, propostas=mod_propostas.padrao())
    return dimensionar(contexto=ctx)
