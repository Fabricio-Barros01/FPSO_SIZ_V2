import pytest

from fpso_siz.core.unidades import kw_para_w
from fpso_siz.pfd.equipamento import Contexto
from fpso_siz.sizing.rating import ResultadoRating


def _metade(estado):
    q_rec = kw_para_w(estado.duties.get("Q_rec_max", estado.duties["Q_pre"]))
    q = q_rec / 2
    cc = kw_para_w(estado.C(estado.streams["C-06"]))
    ch = kw_para_w(estado.C(estado.streams["C-22"]))
    return ResultadoRating(q_rec, q, q, estado.T["C-06"] + q / cc,
                           estado.T["C-22"] - q / ch, 1.0, 1.0, 1.0,
                           q_rec - q, True, 1)


def test_contexto_propaga_rating_sem_mudar_massa(planta_base):
    originais = planta_base.balanco
    ctx = Contexto(planta_base.dados, balanco=originais, rating_p001=_metade)
    novos = ctx.balanco
    assert ctx.diagnostico_integracao["convergiu"]
    for antes, depois in zip(originais, novos):
        assert depois.streams == antes.streams
        assert depois.duties["Q_real"] == pytest.approx(antes.duties["Q_pre"] / 2)
        assert depois.duties["Q_H"] >= antes.duties["Q_H"]
        assert depois.duties["Q_C"] >= antes.duties["Q_C"]
        assert depois.C(depois.streams["C-06"]) * (depois.T["C-07"] - depois.T["C-06"]) \
            == pytest.approx(depois.duties["Q_real"])
        assert depois.C(depois.streams["C-22"]) * (depois.T["C-22"] - depois.T["C-23"]) \
            == pytest.approx(depois.duties["Q_real"])
