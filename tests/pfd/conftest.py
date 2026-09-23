import tomllib
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
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
    return dimensionar(planta_base.dados, ajustes=ajustes_sinteticos, balanco=planta_base.balanco)
