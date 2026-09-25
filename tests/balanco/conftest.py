import hashlib
import json
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.balanco.modelo import EFICIENCIA, REFERENCIA, resolver_todos

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
    """Modo de paridade: a regra do FWKO do script de referência (o oráculo foi gerado com ela)."""
    return resolver_todos(dados, regra_fwko=REFERENCIA)


@pytest.fixture(scope="session")
def resultados_ef(dados):
    """Regra padrão (F10w): η_A do SG-001 = máx(η_padrão; η_req)."""
    return resolver_todos(dados, regra_fwko=EFICIENCIA)
