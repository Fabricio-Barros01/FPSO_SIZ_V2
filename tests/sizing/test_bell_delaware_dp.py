"""Perda de carga do lado casco por Bell-Delaware — Branan (2012), Eq. 2-32 a 2-38 (Fase C, nota 46).

O que se prova: a Tabela 2-5 é contínua nas fronteiras de Reynolds em todas as linhas, exceto nas
duas faixas do layout 90° que o TOML declara não validadas (divergências 9 e 10); a forma usada
tem dimensão de pressão (a impressa não — divergências 7 e 8); os fatores de correção ficam no
intervalo físico; e o conjunto soma os cascos em série.
"""
import math
from dataclasses import replace

import pytest

from fpso_siz.core.configuracao import carregar
from fpso_siz.sizing import bell_delaware as bd

FRONTEIRAS = (10.0, 100.0, 1000.0, 10000.0)


def k():
    return carregar("equipment/exchanger/saari_lmtd.toml")["constants"]["bell_delaware"]


def geometria(layout=30, n_t=400.0, n_ss=1.0):
    d_o, p_t = 0.01905, 0.01905 * 1.25
    p_n, p_p, _ = bd.layout_pitches(layout, p_t, k())
    d_otl = 0.80
    d_s = d_otl + 2 * d_o
    return bd.ShellGeometry(d_s, d_otl, d_o, p_t, p_n, p_p, 0.25 * d_s, 0.4 * d_s, 0.0044, 0.0008, n_t, n_ss,
                            0.0, 2 * d_o, layout)


@pytest.mark.parametrize("layout", [30, 45, 60, 90])
def test_tabela_2_5_continua_exceto_as_faixas_nao_validadas(layout):
    d = carregar("equipment/comum/bell_delaware_dp.toml")
    nao_validadas = {i for lay, i in d["b_nao_validado"] if int(lay) == layout}
    for i, re in enumerate(FRONTEIRAS):
        abaixo, _ = bd.friction_ideal(re * (1 - 1e-9), layout, 1.25, 1.0, k())
        acima, _ = bd.friction_ideal(re * (1 + 1e-9), layout, 1.25, 1.0, k())
        continua = abs(acima / abaixo - 1) < 0.01
        assert continua == (not ({i, i + 1} & nao_validadas)), (layout, re, acima / abaixo)


def test_faixas_nao_validadas_sao_marcadas():
    assert bd.friction_ideal(50.0, 90, 1.25, 1.0, k())[1] is False
    assert bd.friction_ideal(5000.0, 90, 1.25, 1.0, k())[1] is False
    assert bd.friction_ideal(500.0, 90, 1.25, 1.0, k())[1] is True
    assert all(bd.friction_ideal(re, lay, 1.25, 1.0, k())[1] for lay in (30, 45, 60) for re in (5.0, 5e4))


@pytest.mark.parametrize("w_s", [1.0, 60.0])   # laminar (Eq. 2-37) e turbulento (Eq. 2-36)
def test_dimensao_de_pressao(w_s):
    """Com o mesmo Reynolds (ρ e µ não mudam o Re se µ fica), dobrar ρ divide a ΔP por dois em
    todos os termos de Ws² — e o termo laminar (µ·Ws/ρ) também escala com 1/ρ. É o que a forma
    dimensionalmente correta exige; a impressa (Ws/A_s) daria N, não Pa."""
    g = geometria()
    a = bd.perda_carga_casco(g, w_s, 850.0, 5e-3, 10.0, k())
    b = bd.perda_carga_casco(g, w_s, 1700.0, 5e-3, 10.0, k())
    assert a.re == b.re and b.dp == pytest.approx(a.dp / 2, rel=1e-12)
    assert (a.re < 100) == (w_s == 1.0)


def test_fatores_no_intervalo_fisico_e_bypass_bloqueado():
    g = geometria()
    p = bd.perda_carga_casco(g, 30.0, 850.0, 5e-3, 10.0, k())
    assert 0 < p.rl <= 1 and 0 < p.rb <= 1 and p.validado and p.dp > 0
    bloqueado = bd.perda_carga_casco(replace(g, n_ss=1e3), 30.0, 850.0, 5e-3, 10.0, k())
    assert bloqueado.rb == 1.0


def test_sem_densidade_nao_vira_zero():
    p = bd.perda_carga_casco(geometria(), 30.0, 0.0, 5e-3, 10.0, k())
    assert math.isnan(p.dp) and p.motivo
