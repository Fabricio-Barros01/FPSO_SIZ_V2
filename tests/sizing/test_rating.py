import math

import pytest

from fpso_siz.sizing.rating import (LIMITADO_PELA_AREA, LIMITADO_PELO_ALVO, NAO_AVALIAVEL,
                                    SEM_FORCA_MOTRIZ, CasoRating, integrar, rating)


CASO = CasoRating(20.0, 100.0, 10.0, 20.0, 500.0)


def constante(ua):
    return lambda q, tc, th: ua


def test_area_zero_implica_carga_zero():
    r = rating(CASO, constante(0.0))
    assert r.q_real == pytest.approx(0.0, abs=1e-6)


def test_ua_infinito_tende_ao_alvo_e_nao_ultrapassa():
    r = rating(CASO, constante(1e12))
    assert r.q_real == CASO.q_rec_max
    assert r.q_rating <= r.q_rec_max


def test_area_nao_reduz_rating_e_fecha_energia():
    cargas = [rating(CASO, constante(ua)).q_real for ua in (1.0, 10.0, 100.0)]
    assert cargas == sorted(cargas)
    r = rating(CASO, constante(10.0))
    assert CASO.c_fria * (r.t_fria_out - CASO.t_fria_in) == pytest.approx(r.q_real)
    assert CASO.c_quente * (CASO.t_quente_in - r.t_quente_out) == pytest.approx(r.q_real)
    assert r.t_fria_out < CASO.t_quente_in
    assert r.t_quente_out > CASO.t_fria_in
    assert r.convergiu and math.isfinite(r.dt_lm)


def test_utilidades_absorvem_recuperacao_nao_realizada():
    r = rating(CASO, constante(1.0))
    b = integrar(CASO, r, 80.0, 40.0)
    assert b.q_p002 == pytest.approx(CASO.c_fria * (80.0 - r.t_fria_out))
    assert b.q_p003 == pytest.approx(CASO.c_quente * (r.t_quente_out - 40.0))



# ------------------------------------------------------------------ estados declarados (ADR 0005)
def test_area_grande_e_limitada_pelo_alvo_do_pinch():
    r = rating(CASO, constante(1e12))
    assert r.estado == LIMITADO_PELO_ALVO and r.motivo
    assert r.q_real == CASO.q_rec_max and r.recuperacao_nao_realizada == 0
    assert r.fracao_do_alvo == 1.0


def test_area_pequena_e_limitada_pela_area():
    r = rating(CASO, constante(1.0))
    assert r.estado == LIMITADO_PELA_AREA
    assert 0 < r.q_real < CASO.q_rec_max
    assert r.recuperacao_nao_realizada == pytest.approx(CASO.q_rec_max - r.q_real)


def test_sem_forca_motriz_e_resultado_nao_lacuna():
    """Quente entrando abaixo do frio: Q = 0 é RESULTADO, e o estado diz por quê."""
    frio = CasoRating(100.0, 20.0, 10.0, 20.0, 500.0)
    r = rating(frio, constante(1e6))
    assert r.estado == SEM_FORCA_MOTRIZ and r.avaliavel
    assert r.q_real == 0.0 and r.recuperacao_nao_realizada == CASO.q_rec_max
    assert "não entra acima" in r.motivo


def test_alvo_nulo_tambem_e_resultado():
    r = rating(CasoRating(20.0, 100.0, 10.0, 20.0, 0.0), constante(1e6))
    assert r.estado == SEM_FORCA_MOTRIZ and r.q_real == 0.0 and r.fracao_do_alvo == 1.0


@pytest.mark.parametrize("ua", [math.nan, math.inf, -1.0])
def test_ua_nao_avaliavel_nao_vira_carga_zero(ua):
    """O defeito que a ADR 0005 cobra: U·A que não pôde ser avaliado NÃO é transferência nula.

    Devolver zero afirmaria que a geometria não troca calor — o que não foi calculado. O
    resultado é NaN com o estado e o motivo declarados (invariante 5)."""
    r = rating(CASO, constante(ua))
    assert r.estado == NAO_AVALIAVEL and not r.avaliavel
    assert math.isnan(r.q_rating) and math.isnan(r.q_real)
    assert math.isnan(r.recuperacao_nao_realizada) and math.isnan(r.fracao_do_alvo)
    assert r.motivo


def test_integrar_propaga_nao_avaliavel_como_nan():
    b = integrar(CASO, rating(CASO, constante(math.nan)), 80.0, 40.0)
    assert all(math.isnan(x) for x in (b.q_p002, b.q_p003, b.utilidade_quente_residual,
                                       b.utilidade_fria_residual))


def test_temperaturas_de_entrada_nao_finitas_sao_nao_avaliaveis():
    r = rating(CasoRating(math.nan, 100.0, 10.0, 20.0, 500.0), constante(10.0))
    assert r.estado == NAO_AVALIAVEL and "não finitas" in r.motivo


@pytest.mark.parametrize("caso", [CasoRating(20.0, 100.0, 0.0, 20.0, 500.0),
                                  CasoRating(20.0, 100.0, 10.0, 20.0, -1.0)])
def test_entrada_invalida_e_erro_de_programacao(caso):
    """Capacidade térmica não positiva ou alvo negativo é ValueError: não é estado físico."""
    with pytest.raises(ValueError):
        rating(caso, constante(10.0))


def test_ua_reavaliado_em_cada_iteracao_nao_e_congelado():
    """O U·A é função de Q: a raiz tem de ser a do U·A(Q), não a de um U·A fixo."""
    vistos = []

    def ua(q, tc, th):
        vistos.append((q, tc, th))
        return 1.0 * (1 + q / CASO.q_rec_max)   # cresce com a carga

    r = rating(CASO, ua)
    assert len(vistos) > 2 and len({q for q, _, _ in vistos}) > 2
    assert r.ua == pytest.approx(1.0 * (1 + r.q_rating / CASO.q_rec_max))
    assert r.q_real > rating(CASO, constante(1.0)).q_real   # mais área, mais carga


def test_fator_f_fora_do_dominio_reduz_a_carga_mas_nao_e_falta_de_dado():
    """F não finito é recusa de DOMÍNIO naquele Q (o arranjo não fecha): a bisseção procura o
    Q em que ele fecha, e o resultado continua avaliável."""
    def f(q, tc, th):
        return 1.0 if q <= CASO.q_rec_max / 2 else math.nan

    r = rating(CASO, constante(1e9), f)
    assert r.avaliavel and r.q_real <= CASO.q_rec_max / 2
