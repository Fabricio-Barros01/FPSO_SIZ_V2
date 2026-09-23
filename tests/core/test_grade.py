"""A grade de varredura cai nos mesmos pontos que `collect(a:passo:b)` do Julia 1.12.6
(saídas conferidas no próprio Julia e coladas aqui)."""
import pytest

from fpso_siz.core.grade import faixa_julia, rat

JULIA = [
    ((16 * 25.4, 6 * 25.4, 48 * 25.4), [406.4, 558.8, 711.1999999999999, 863.5999999999999, 1015.9999999999999,
                                         1168.3999999999999]),
    ((0.1, 0.1, 1.0), [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]),
    ((0.0, 0.3, 1.0), [0.0, 0.3, 0.6, 0.9]),
    ((1.0, 0.05, 1.3), [1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3]),
    ((5200.0, 150.0, 5950.0), [5200.0, 5350.0, 5500.0, 5650.0, 5800.0, 5950.0]),
    ((2.5, -0.5, 0.0), [2.5, 2.0, 1.5, 1.0, 0.5, 0.0]),
    ((1.0, 1.0, 0.5), []),
    ((3000.0, 150.0, 8000.0), [3000.0 + 150.0 * i for i in range(34)]),
]


@pytest.mark.parametrize("args, esperado", JULIA)
def test_igual_ao_julia(args, esperado):
    assert list(faixa_julia(*args)) == esperado


def test_bordas():
    assert faixa_julia(5.0, 1.0, 5.0) == (5.0,)
    assert rat(0.5) == (1, 2) and rat(3.0) == (3, 1)
    with pytest.raises(ValueError):
        faixa_julia(0.0, 0.0, 1.0)
