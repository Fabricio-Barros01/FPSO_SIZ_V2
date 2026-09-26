"""F8 — caso-ouro da Análise Pinch: Kemp, *Pinch Analysis and Process Integration*, 2ª ed.,
Butterworth-Heinemann, 2007 (ISBN 978-0-7506-8260-2).

**A fonte traz o exemplo resolvido inteiro, e por isso este é o caso-ouro mais completo do
projeto.** Não há aqui o buraco de `test_golden_bomba_trocador` (Saari não publica exemplo
numérico fechado do casco-e-tubos): Kemp publica as quatro correntes (Tab. 2.2, p. 21), a
tabela de intervalos com o CP líquido e o calor de cada um (Tab. 2.3, p. 22), **as duas
cascatas** (Fig. 2.9, p. 23) e os alvos com a temperatura de pinch (p. 24). Todos os números
abaixo estão impressos no livro; nenhum foi recalculado para caber.

O exemplo está no capítulo 2; o capítulo 3 traz o algoritmo passo a passo (§3.9.1, pp. 95-96) e
os problemas-limiar (§3.3.2, p. 54), que dão o segundo caso-ouro.

**Duas erratas da fonte, sem consequência para o programa** (ficam registradas pela mesma razão
que as de Stewart & Arnold e de Saari — quem conferir o teste contra o livro precisa saber por
que dois números não são o que a página diz):

1. O §3.3 (p. 53) manda ver os algoritmos em "Section 3.11"; o apêndice é o §3.9 (p. 95). Não
   há §3.11 no livro.
2. As cargas da p. 24 aparecem em kWh onde são kW ("510 and 470 kWh", "60 and 20 kWh") para
   grandezas que a própria Tab. 2.3 dá em kW — são taxas, não energias acumuladas.

Tolerância: 0,01 °C em temperatura e 0,1 % em calor. Na prática o acordo é exato — o algoritmo é
aritmética sobre os dados, sem correlação empírica no meio — e as folgas existem para o caso de
o livro ter arredondado, que é o que acontece no "5,55 °C" do §3.3.2.
"""
import math

import pytest

from fpso_siz.analysis import pinch as pa

TOL_T = 0.01     # °C
TOL_Q = 1e-3     # relativo


def kemp_tabela_2_2():
    """Tab. 2.2, p. 21. Quatro correntes; o tipo sai do sinal de T_in − T_out, não de rótulo."""
    return [pa.corrente("1 fria", 20, 135, 2.0), pa.corrente("2 quente", 170, 60, 3.0),
            pa.corrente("3 fria", 80, 140, 4.0), pa.corrente("4 quente", 150, 30, 1.5)]


def perto(a, b, rtol=TOL_Q, atol=1e-9):
    return abs(a - b) <= max(atol, rtol * abs(b))


def test_tabela_2_2_temperaturas_deslocadas_corrente_a_corrente():
    """As colunas SS e ST da tabela publicada, e o tipo, que o livro dá por extenso na coluna
    "Stream number and type" e que aqui tem de sair DERIVADO, sem ninguém informá-lo."""
    publicadas = [(25.0, 140.0),    # 1 fria:    20 → 135, sobe 5
                  (165.0, 55.0),    # 2 quente: 170 →  60, desce 5
                  (85.0, 145.0),    # 3 fria:    80 → 140, sobe 5
                  (145.0, 25.0)]    # 4 quente: 150 →  30, desce 5
    correntes = kemp_tabela_2_2()
    for s, esperado in zip(correntes, publicadas):
        obtido = pa.shifted_temperatures(s.segments[0], 10.0)
        assert abs(obtido[0] - esperado[0]) <= TOL_T and abs(obtido[1] - esperado[1]) <= TOL_T
    assert [pa.stream_type(s) for s in correntes] == ["cold", "hot", "cold", "hot"]


def test_tabela_2_3_fronteiras_cp_liquido_e_calor_de_cada_intervalo():
    r = pa.problem_table(kemp_tabela_2_2(), 10.0)
    assert r.feasible
    # as seis fronteiras impressas embaixo da tabela: S1 … S6
    assert [round(x, 6) for x in r.boundaries] == [165.0, 145.0, 140.0, 85.0, 55.0, 25.0]
    # as três colunas numéricas da Tab. 2.3, linha a linha (ΔT, CP líquido, ΔH)
    publicada = [(20.0, 3.0, 60.0),      # 1 — excedente
                 (5.0, 0.5, 2.5),        # 2 — excedente
                 (55.0, -1.5, -82.5),    # 3 — déficit
                 (30.0, 2.5, 75.0),      # 4 — excedente
                 (30.0, -0.5, -15.0)]    # 5 — déficit
    assert len(r.intervals) == 5
    for iv, (dt, cp, dh) in zip(r.intervals, publicada):
        assert abs((iv.s_top - iv.s_bot) - dt) <= TOL_T
        assert perto(iv.cp_net, cp) and perto(iv.dh, dh)
        # a última coluna do livro, "Surplus or deficit", é o sinal de ΔH
        assert math.copysign(1, iv.dh) == math.copysign(1, dh)


def test_figura_2_9_as_duas_cascatas_no_a_no():
    r = pa.problem_table(kemp_tabela_2_2(), 10.0)
    # (a) infactível: parte de zero no topo e passa por −20 kW, que é o que a torna
    # termodinamicamente impossível e o que fixa o QHmin
    for obtido, publicado in zip(r.cascade_infeasible, [0.0, 60.0, 62.5, -20.0, 55.0, 40.0]):
        assert perto(obtido, publicado)
    assert perto(min(r.cascade_infeasible), -20.0)
    # (b) factível: os mesmos fluxos somados de 20 kW, com zero exato no pinch
    for obtido, publicado in zip(r.cascade_feasible, [20.0, 80.0, 82.5, 0.0, 75.0, 60.0]):
        assert perto(obtido, publicado)


def test_p24_alvos_e_posicao_do_pinch():
    r = pa.problem_table(kemp_tabela_2_2(), 10.0)
    assert perto(r.q_h_min, 20.0) and perto(r.q_c_min, 60.0)
    # "the position of the pinch has been located. This is at the interval boundary with a
    # shifted temperature of 85°C (i.e. hot streams at 90°C and cold at 80°C)"
    assert len(r.t_pinch_shifted) == 1
    assert abs(r.t_pinch_shifted[0] - 85.0) <= TOL_T
    assert abs(r.t_pinch_hot[0] - 90.0) <= TOL_T
    assert abs(r.t_pinch_cold[0] - 80.0) <= TOL_T
    assert not r.threshold   # com as duas utilidades presentes, não é problema-limiar


def test_p24_conferencias_cruzadas_que_o_livro_manda_fazer():
    """"The total heat recovered by heat exchange is found by adding the heat loads for all the
    hot streams and all the cold streams – 510 and 470 kW[h] … gives the total heat recovery,
    450 kW[h], by two separate routes." """
    correntes = kemp_tabela_2_2()
    r = pa.problem_table(correntes, 10.0)
    quente, fria = pa.heat_loads(correntes)
    assert perto(quente, 510.0) and perto(fria, 470.0)
    # a recuperação por dois caminhos independentes, como o livro pede
    assert perto(quente - r.q_c_min, 450.0) and perto(fria - r.q_h_min, 450.0)
    # "The cold utility target minus the hot utility target should equal the bottom line of the
    # infeasible heat cascade, which is 40 kW[h]."
    assert perto(r.q_c_min - r.q_h_min, 40.0) and perto(r.cascade_infeasible[-1], 40.0)


@pytest.mark.parametrize("dt", [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 5.5])
def test_secao_3_3_2_abaixo_do_limiar_so_sobra_utilidade_fria_e_o_pinch_some(dt):
    """"at all lower values of ∆Tmin, the only utility needed is 40 kW cold utility". Sem pinch:
    é o que distingue um problema-limiar de um problema com pinch, e é por isso que `threshold` e
    `t_pinch_shifted` são campos separados."""
    r = pa.problem_table(kemp_tabela_2_2(), dt)
    assert r.feasible and r.threshold
    assert abs(r.q_h_min) <= 1e-9 and perto(r.q_c_min, 40.0)
    assert r.t_pinch_shifted == ()


def test_acima_do_limiar_a_utilidade_quente_reaparece_com_pinch():
    r6 = pa.problem_table(kemp_tabela_2_2(), 6.0)
    assert r6.q_h_min > 0 and not r6.threshold and len(r6.t_pinch_shifted) == 1


def test_secao_3_3_2_o_limiar_publicado_de_5_55_graus():
    """A forma fechada do QHmin destas correntes, válida em 0 ≤ ΔTmin ≤ 10: o nó da cascata que
    governa está na fronteira de 80 + ΔTmin/2 e vale 25 − 9·(ΔTmin/2), logo

        QHmin = max(0; 4,5·ΔTmin − 25),  com raiz em 50/9 = 5,5556 °C

    Ela reproduz os DOIS pontos publicados — o 20 kW da p. 24 e o "5,55 °C" da p. 54 — e é o que
    sustenta a monotonicidade analiticamente, e não por amostragem."""
    correntes = kemp_tabela_2_2()
    fechada = lambda dt: max(0.0, 4.5 * dt - 25.0)
    for i in range(1, 41):
        dt = i / 4
        assert perto(pa.problem_table(correntes, dt).q_h_min, fechada(dt))
    limiar = 50 / 9
    assert abs(limiar - 5.55) <= 0.01          # o valor impresso, dentro do arredondamento
    r = pa.problem_table(correntes, limiar)
    assert abs(r.q_h_min) <= 1e-9
    # no ΔTmin exato do limiar as duas coisas coexistem: a utilidade quente é zero E ainda há um
    # pinch interior. É o caso de borda que motiva os dois campos.
    assert r.threshold and len(r.t_pinch_shifted) == 1
    assert abs(r.t_pinch_shifted[0] - (80.0 + limiar / 2)) <= TOL_T
    # acima do limiar QHmin é estritamente crescente, com a inclinação de 4,5 kW/°C
    a = pa.problem_table(correntes, 8.0).q_h_min
    b = pa.problem_table(correntes, 9.0).q_h_min
    assert perto(b - a, 4.5)


def _t_em(h, t, x):
    """Interpola a temperatura da curva (h, t) na entalpia x. Só para o teste."""
    if x <= h[0]:
        return t[0]
    if x >= h[-1]:
        return t[-1]
    k = next(i for i in range(len(h) - 1) if h[i] <= x <= h[i + 1])
    if h[k + 1] == h[k]:
        return t[k]
    return t[k] + (t[k + 1] - t[k]) * (x - h[k]) / (h[k + 1] - h[k])


def test_secao_2_3_curvas_compostas_fecham_com_os_alvos_da_problem_table():
    """A conferência não depende de ler coordenadas num gráfico publicado: as curvas têm cinco
    invariantes que as amarram aos números já conferidos acima, e é contra eles que se testa."""
    correntes = kemp_tabela_2_2()
    cc = pa.composite_curves(correntes, 10.0)
    r = pa.problem_table(correntes, 10.0)
    quente, fria = pa.heat_loads(correntes)
    # os pontos de quebra são as temperaturas onde uma corrente entra ou sai da soma
    assert [round(x, 6) for x in cc.t_hot] == [30.0, 60.0, 150.0, 170.0]
    assert [round(x, 6) for x in cc.t_cold] == [20.0, 80.0, 135.0, 140.0]
    # entalpia acumulada: ΣCP·ΔT faixa a faixa. A quente parte de zero; a fria, de QCmin.
    assert [round(x, 6) for x in cc.h_hot] == [0.0, 45.0, 450.0, 510.0]
    assert [round(x, 6) for x in cc.h_cold] == [60.0, 180.0, 510.0, 530.0]
    # 1. cada composta fecha na carga total do seu lado
    assert perto(cc.h_hot[-1] - cc.h_hot[0], quente) and perto(cc.h_cold[-1] - cc.h_cold[0], fria)
    # 2. a fria começa exatamente em QCmin — é esse deslocamento que encosta as curvas
    assert perto(cc.h_cold[0], r.q_c_min)
    # 3. a sobreposição é o calor recuperado, e dá o mesmo pelos dois lados
    assert perto(cc.q_rec, quente - r.q_c_min) and perto(cc.q_rec, fria - r.q_h_min) and perto(cc.q_rec, 450.0)
    # 4. a folga da direita é QHmin: a quente acaba antes da fria por exatamente QHmin
    assert perto(cc.h_cold[-1] - cc.h_hot[-1], r.q_h_min)
    # 5. O QUE DEFINE ΔTmin: no pinch a separação vertical é exatamente ΔTmin, e em nenhum ponto
    # da sobreposição ela é menor. É a Fig. 2.4 enunciada como teste.
    h_pinch = 180.0            # onde as duas curvas passam pelo pinch (90 °C / 80 °C)
    assert abs(_t_em(cc.h_hot, cc.t_hot, h_pinch) - r.t_pinch_hot[0]) <= TOL_T
    assert abs(_t_em(cc.h_cold, cc.t_cold, h_pinch) - r.t_pinch_cold[0]) <= TOL_T
    lo, hi = max(cc.h_hot[0], cc.h_cold[0]), min(cc.h_hot[-1], cc.h_cold[-1])
    folgas = [_t_em(cc.h_hot, cc.t_hot, lo + (hi - lo) * i / 399)
              - _t_em(cc.h_cold, cc.t_cold, lo + (hi - lo) * i / 399) for i in range(400)]
    assert abs(min(folgas) - 10.0) <= 0.05 and all(f >= 10.0 - 0.05 for f in folgas)


def test_problema_inviavel_nao_inventa_curva():
    vazio = pa.composite_curves([], 10.0)
    assert vazio.h_hot == () and vazio.h_cold == () and not math.isfinite(vazio.q_rec)
