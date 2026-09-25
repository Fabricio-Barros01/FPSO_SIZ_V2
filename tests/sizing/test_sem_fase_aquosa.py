"""Premissa P-42 (BOT Tab. 2.2.2.3 Notas 5 e 11; 2.3.1.1): num caso sem vazão de água e com
óleo, os critérios que dependem da fase aquosa (decantação líquido-líquido e retenção da
água) são "não aplicável — sem fase aquosa". Não é inviabilidade nem exceção, e o caso não
governa o teto do envelope: a fase aquosa é dimensionada pelos casos com água."""
import math

import pytest

from fpso_siz.core.casos import Case, CaseSet
from fpso_siz.core.corrente import stream_from_case, stream_parameters
from fpso_siz.core.motor import size_envelope
from fpso_siz.core.parametros import defaults, with_defaults
from fpso_siz.sizing import ArnoldElectrostatic, ElectrostaticTreater, Separator, StewartArnold
from fpso_siz.sizing import separador as m_sep
from fpso_siz.sizing import tratador as m_tr
from fpso_siz.sizing.vasos import SEM_FASE_AQUOSA, mechanism_label, sem_fase_aquosa

SA, SEP = StewartArnold(), Separator()
TR, TRM = ElectrostaticTreater(), ArnoldElectrostatic()
AQUOSAS = ("dm_water", "dm_oil", "tr_water")


def separador(**ajuste):
    return defaults(stream_parameters()) | defaults(SA.parameters()) | ajuste


def tratador(**ajuste):
    return defaults(TRM.stream_parameters()) | defaults(TRM.parameters()) | ajuste


def restricoes(metodo, vals):
    s = stream_from_case(vals, required=metodo.stream_keys())
    return metodo.sizing_constraints(s, with_defaults(metodo.parameters(), vals), metodo.constants())


@pytest.mark.parametrize("metodo, vals", [(SA, separador), (TRM, tratador)])
def test_sem_agua_criterios_aquosos_nao_aplicaveis(metodo, vals):
    com = restricoes(metodo, vals(q_water=0.0))
    ok, c, tr = com
    assert ok and c.mechanism == SEM_FASE_AQUOSA and c.d_max_mm == math.inf and c.aw_over_a == 0.0
    na = [e for e in tr.entries if e.eq == "P-42"]
    assert len(na) == 1 and na[0].value == 0.0 and "não aplicável — sem fase aquosa" in na[0].formula
    assert not [e for e in tr.block_entries("settling") if e.eq != "P-42"]  # nenhum critério aquoso avaliado
    # as entradas aquosas podem faltar (NaN): o caso não as usa
    ok2, c2, _ = restricoes(metodo, vals(q_water=0.0, **{k: math.nan for k in AQUOSAS}))
    assert ok2 and (c2.d_leff_gas, c2.d2_leff, c2.beta) == (c.d_leff_gas, c.d2_leff, c.beta)
    assert mechanism_label(SEM_FASE_AQUOSA) == "não aplicável — sem fase aquosa"


@pytest.mark.parametrize("metodo, vals, modulo", [(SA, separador, m_sep), (TRM, tratador, m_tr)])
def test_capacidade_de_liquido_igual_a_de_antes_sem_agua(metodo, vals, modulo, monkeypatch):
    """Sem água, (tr)w·Qw = 0: capacidade de gás e de líquido, β e a fração de água são os
    mesmos números da forma geral (a de antes da P-42); só o teto deixa de existir."""
    ok, c, _ = restricoes(metodo, vals(q_water=0.0))
    monkeypatch.setattr(modulo, "sem_fase_aquosa", lambda fu: False)
    ok0, c0, _ = restricoes(metodo, vals(q_water=0.0))
    assert ok and ok0 and math.isfinite(c0.d_max_mm) and c.d_max_mm == math.inf
    assert (c.d_leff_gas, c.d2_leff, c.beta, c.aw_over_a) == (c0.d_leff_gas, c0.d2_leff, c0.beta, c0.aw_over_a)


def test_regra_so_com_oleo_e_zero_exato():
    fu = type("FU", (), {})
    for q_w, q_o, esperado in ((0.0, 1.0, True), (1e-12, 1.0, False), (0.0, 0.0, False), (math.nan, 1.0, False)):
        f = fu()
        f.q_w, f.q_o = q_w, q_o
        assert sem_fase_aquosa(f) is esperado


def test_oleo_e_agua_nulos_mantem_a_inviabilidade_do_tratador():
    vals = tratador(q_oil=0.0, q_water=0.0)
    r = TRM.size_equipment(TR, TRM.case_input(vals), vals)
    assert not r.feasible and "Eq. 4.16" in r.message


def test_caso_sem_agua_nao_governa_o_teto_do_envelope():
    com_agua, sem_agua = separador(), separador(q_water=0.0)
    so_agua = size_envelope(SEP, SA, CaseSet([Case("com água", com_agua)]))
    ambos = size_envelope(SEP, SA, CaseSet([Case("com água", com_agua), Case("sem água", sem_agua)]))
    assert ambos.feasible and ambos.ceiling == so_agua.ceiling and ambos.ceiling_case == "com água"
    sozinho = size_envelope(SEP, SA, CaseSet([Case("sem água", sem_agua | {k: math.nan for k in AQUOSAS})]))
    assert sozinho.feasible and sozinho.ceiling == math.inf and sozinho.ceiling_mechanism == SEM_FASE_AQUOSA


def test_tratador_sem_agua_com_retencao_invalida_e_inviavel():
    ok, msg, _ = restricoes(TRM, tratador(q_water=0.0, tr_oil=math.nan))
    assert not ok and "Eq. 4.15b" in msg
