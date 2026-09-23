import hashlib
import json
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.balanco.modelo import resolver_todos

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref"
ENTRADA = FIXTURES / "design_cases_bot.json"


@pytest.fixture(scope="session")
def oraculo():
    return json.loads((FIXTURES / "oraculo_balanco.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def dados(oraculo):
    # a cópia versionada da entrada é a mesma que gerou o oráculo
    assert hashlib.sha256(ENTRADA.read_bytes()).hexdigest() == oraculo["proveniencia"]["entrada_sha256"]
    return carregar_casos(ENTRADA)


@pytest.fixture(scope="session")
def resultados(dados):
    return resolver_todos(dados)
