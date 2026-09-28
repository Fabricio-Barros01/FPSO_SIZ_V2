from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.balanco.modelo import resolver_todos

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref"
ENTRADA = FIXTURES / "design_cases_bot.json"


@pytest.fixture(scope="session")
def dados():
    return carregar_casos(ENTRADA)


@pytest.fixture(scope="session")
def resultados(dados):
    """O EstadoProcesso de cada caso, pelo único resolvedor produtivo."""
    return resolver_todos(dados)
