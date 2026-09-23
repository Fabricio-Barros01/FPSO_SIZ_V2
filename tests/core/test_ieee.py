import math

from fpso_siz.core.ieee import div


def test_divisao_ieee():
    assert div(1.0, 2.0) == 0.5
    assert div(1.0, 0.0) == math.inf and div(-1.0, 0.0) == -math.inf and div(1.0, -0.0) == -math.inf
    assert math.isnan(div(0.0, 0.0)) and math.isnan(div(math.nan, 0.0))
