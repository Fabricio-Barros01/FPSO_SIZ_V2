"""R1 — o feixe de Bell-Delaware é invariante no ponto fixo em L (docs/validacao/27-...).

`_tubo_bell_delaware` resolve um ponto fixo em L e, a cada passagem, só o número de chicanas
muda. Das cinco correções da Eq. 2-18, **só Js depende de n_b**; o resto do feixe depende apenas
da geometria e do escoamento do casco. Por isso o feixe é avaliado uma vez, fora do laço.

Estes testes prendem as duas coisas de que essa separação depende:

1. `bell_delaware` continua sendo exatamente `com_chicanas ∘ feixe_ideal` — inclusive nos
   caminhos de falha e no último bit;
2. o feixe realmente não depende de n_b, e `feixe_ideal` é chamada uma vez por `_tubo`.

Se alguém acoplar o feixe a n_b no futuro (por exemplo, ao dar entrada a vãos de ponta
diferentes), é o teste 2 que reprova primeiro — e aí a correção é chamar `feixe_ideal` dentro
do laço outra vez, não silenciar o teste.
"""
import copy
import math
from dataclasses import replace

import pytest

from fpso_siz.sizing import bell_delaware as BD
from fpso_siz.sizing import trocador
from fpso_siz.sizing.trocador import SaariLMTD

KBD = SaariLMTD().constants()["bell_delaware"]
N_B = (1.0, 2.0, 3.5, 20.0, 60.0, 1000.0)


def geo(d_s=0.60, corte=0.25, l_bc=0.24, layout=30, n_ss=1.0, n_t=400.0):
    d_o = 0.01905
    p_t = 1.25 * d_o
    p_n, p_p, _ = BD.layout_pitches(layout, p_t, KBD)
    from fpso_siz.core import unidades as U
    folga = U.mm_para_m(BD.baffle_clearance(d_s * 1000, KBD))
    return BD.ShellGeometry(d_s, d_s - folga, d_o, p_t, p_n, p_p, corte * d_s, l_bc, folga, 0.0008, n_t, n_ss,
                            0.0, 2 * d_o, layout)


ESCOAMENTO = dict(w_s=15.0, cp_s=2100.0, mu_s=3.0e-3, k_s=0.13)


def _bd(g, n_b, **kw):
    e = {**ESCOAMENTO, **kw}
    return BD.bell_delaware(g, e["w_s"], e["cp_s"], e["mu_s"], e["k_s"], n_b, g.l_bc, g.l_bc, KBD)


def _partido(g, n_b, **kw):
    e = {**ESCOAMENTO, **kw}
    feixe = BD.feixe_ideal(g, e["w_s"], e["cp_s"], e["mu_s"], e["k_s"], KBD)
    return BD.com_chicanas(feixe, n_b, g.l_bc, g.l_bc, g.l_bc, KBD)


def _identico(a, b):
    """Igualdade BIT A BIT, com NaN casando com NaN — `==` não serve para float."""
    (ha, fa, oka), (hb, fb, okb) = a, b
    def mesmo(x, y):
        return (math.isnan(x) and math.isnan(y)) or x == y
    return (mesmo(ha, hb) and oka == okb
            and all(mesmo(getattr(fa, c), getattr(fb, c))
                    for c in ("jc", "jl", "jb", "js", "jr", "produto", "h_ideal", "re", "a_s")))


@pytest.mark.parametrize("n_b", N_B)
def test_a_funcao_inteira_e_a_composicao_das_duas_partes(n_b):
    g = geo()
    assert _identico(_bd(g, n_b), _partido(g, n_b))


@pytest.mark.parametrize("quebra", [
    dict(p_n=0.0),        # área de escoamento cruzado inválida
    dict(l_bc=0.0),       # idem, pelo vão
    dict(d_s=0.0),        # geometria degenerada
])
def test_os_caminhos_de_falha_tambem_coincidem(quebra):
    g = replace(geo(), **quebra)
    inteira, partida = _bd(g, 20.0), _partido(g, 20.0)
    assert not inteira[2] and _identico(inteira, partida)


def test_escoamento_invalido_falha_igual():
    g = geo()
    for kw in (dict(mu_s=0.0), dict(w_s=0.0), dict(k_s=0.0), dict(cp_s=0.0)):
        assert _identico(_bd(g, 20.0, **kw), _partido(g, 20.0, **kw))


def test_o_feixe_nao_depende_do_numero_de_chicanas():
    """O que autoriza tirar `feixe_ideal` do laço: Re, A_s, h_ideal, Jc, Jl, Jb e Jr são os
    mesmos para qualquer n_b — só Js e o produto respondem a ele."""
    g = geo()
    fatores = [_bd(g, n)[1] for n in N_B]
    for campo in ("re", "a_s", "h_ideal", "jc", "jl", "jb", "jr"):
        assert len({getattr(f, campo) for f in fatores}) == 1, campo


def test_js_e_1_com_vaos_de_ponta_iguais_ao_central():
    """A premissa registrada em `saari_lmtd.toml`: o modelo tem um único espaçamento, e com
    l_bi = l_bo = l_bc a Eq. 2-28 dá Js = 1 para qualquer n_b. A equação NÃO é neutralizada —
    com vãos diferentes ela volta a valer, e é o que o segundo bloco confere."""
    g = geo()
    for n_b in N_B:
        assert BD.j_spacing(n_b, g.l_bc, g.l_bc, g.l_bc, False, KBD) == 1.0
        assert _bd(g, n_b)[1].js == 1.0
    # vão de ponta MAIOR que o central: Js deixa de ser 1 e passa a depender de n_b
    js = [BD.j_spacing(n_b, 1.5 * g.l_bc, 1.5 * g.l_bc, g.l_bc, False, KBD) for n_b in N_B]
    assert all(x < 1.0 for x in js) and len(set(js)) == len(js)


def test_feixe_ideal_e_avaliado_uma_vez_por_tubo(monkeypatch):
    """A contagem que dá o ganho do R1: uma avaliação de feixe por chamada de `_tubo`, e várias
    combinações com Js dentro do ponto fixo."""
    from fpso_siz.core.parametros import defaults, with_defaults

    m = SaariLMTD()
    vals = defaults(m.parameters())
    ok, cons, _ = m.sizing_constraints(m.case_input(vals), with_defaults(m.parameters(), vals),
                                       copy.deepcopy(m.constants()))
    assert ok

    n = {"feixe": 0, "comb": 0}
    orig_feixe, orig_comb = trocador.feixe_ideal, trocador.com_chicanas
    monkeypatch.setattr(trocador, "feixe_ideal",
                        lambda *a, **kw: (n.__setitem__("feixe", n["feixe"] + 1), orig_feixe(*a, **kw))[1])
    monkeypatch.setattr(trocador, "com_chicanas",
                        lambda *a, **kw: (n.__setitem__("comb", n["comb"] + 1), orig_comb(*a, **kw))[1])
    t = trocador._tubo(cons, 40.0)
    assert t["ok"]
    assert n["feixe"] == 1, "o feixe tem de sair do laço: uma avaliação por chamada de _tubo"
    assert n["comb"] >= 1 and n["comb"] >= n["feixe"]
