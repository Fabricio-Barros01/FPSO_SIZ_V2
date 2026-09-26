"""F8 — encaixe da Análise Pinch no contrato de varredura (`sizing/pinch_kemp.py`).

`test_golden_kemp.py` prova o ALGORITMO contra os números publicados. O que se prova aqui é que
o encaixe não perde nem desloca nada pelo caminho: o mesmo resultado saindo pelo motor, o grupo
repetível de correntes, a fronteira de tradução que recusa instância pela metade, a exigência
não-decrescente que autoriza chamar o QHmin de exigência, e o cartão dizendo o que a tela NÃO
faz.
"""
import math

import pytest

from fpso_siz.analysis import pinch as pa
from fpso_siz.core import registro
from fpso_siz.core.casos import Case, CaseSet
from fpso_siz.core.motor import governing_summary, size_envelope
from fpso_siz.core.parametros import group_instance, in_group, instance_key, is_template, with_defaults
from fpso_siz.sizing import PinchKemp, PinchTarget

M, EQ = PinchKemp(), PinchTarget()


def valores_kemp():
    """As quatro correntes da Tab. 2.2 nas chaves sintetizadas de `instance_key`."""
    dados = [(20.0, 135.0, 2.0), (170.0, 60.0, 3.0), (80.0, 140.0, 4.0), (150.0, 30.0, 1.5)]
    v = {"dt_min_alvo": 10.0}
    for i, (t_in, t_out, mcp) in enumerate(dados, 1):
        v[instance_key("corrente", i, "t_in")] = t_in
        v[instance_key("corrente", i, "t_out")] = t_out
        v[instance_key("corrente", i, "mcp")] = mcp
    return v


def params():
    return with_defaults(M.parameters(), {})


def test_o_molde_declara_o_grupo_e_a_instancia_o_carrega():
    g = M.parameter_groups()[0]
    assert (g["key"], g["label"], g["min"], g["max"]) == ("corrente", "Corrente", 2, 12)
    moldes = [s for s in M.parameters() if in_group(s)]
    assert [s.key for s in moldes] == ["t_in", "t_out", "mcp"] and all(is_template(s) for s in moldes)
    inst = group_instance(moldes[0], 3, prefixo="Corrente")
    assert inst.key == "corrente_3_t_in" and inst.instance == 3 and inst.label.startswith("Corrente 3 — ")
    # expandir uma instância outra vez é erro, e levanta em vez de inventar chave
    with pytest.raises(ValueError):
        group_instance(inst, 4)


def test_os_globais_sao_a_grade_de_dt_min_e_o_alvo():
    assert M.global_keys() == ["dt_min_min", "dt_min_max", "dt_min_step", "dt_min_alvo"]
    assert M.stream_keys() == ()      # a rede não é uma corrente de processo do StreamState
    assert M.action_label() == "Analisar"


def test_case_input_converte_as_instancias_em_correntes():
    correntes = M.case_input(valores_kemp())
    assert len(correntes) == 4
    assert [pa.stream_type(s) for s in correntes] == ["cold", "hot", "cold", "hot"]
    assert [s.segments[0].t_in for s in correntes] == [20.0, 170.0, 80.0, 150.0]
    assert [s.segments[0].t_out for s in correntes] == [135.0, 60.0, 140.0, 30.0]
    assert [s.segments[0].mcp for s in correntes] == [2.0, 3.0, 4.0, 1.5]
    # o nome é sintetizado do índice, e é o que as mensagens de recusa citam
    assert [s.name for s in correntes] == [f"Corrente {i}" for i in range(1, 5)]


def test_case_input_recusa_instancia_pela_metade_e_rede_vazia():
    """Instância pela metade é recusada, não completada com o default do descritor: uma corrente
    que ninguém informou não entra no alvo de energia."""
    meia = valores_kemp()
    del meia["corrente_3_mcp"]
    with pytest.raises(ValueError, match="pela metade"):
        M.case_input(meia)
    with pytest.raises(ValueError, match="corrente_3_mcp"):
        M.case_input(meia)
    with pytest.raises(ValueError):
        M.case_input({"dt_min_alvo": 10.0})


def test_buraco_no_meio_nao_e_erro():
    """1, 2 e 4 descrevem três correntes, e a 3 simplesmente não existe."""
    com_buraco = valores_kemp()
    for k in ("t_in", "t_out", "mcp"):
        del com_buraco[instance_key("corrente", 3, k)]
    assert len(M.case_input(com_buraco)) == 3


def test_o_motor_converte_a_excecao_da_fronteira_em_inviabilidade():
    """A recusa chega ao usuário como mensagem com o NOME do caso, nunca como exceção."""
    meia = valores_kemp()
    del meia["corrente_2_t_out"]
    r = size_envelope(EQ, M, CaseSet([Case("cenário incompleto", meia)]))
    assert not r.feasible and math.isnan(r.x)
    assert "cenário incompleto" in r.message and "pela metade" in r.message


def test_corrente_invalida_vira_mensagem_de_sizing_constraints():
    """Segmento isotérmico é recusa de dado, e volta como mensagem (com a receita da p. 44), não
    como exceção."""
    iso = valores_kemp()
    iso["corrente_1_t_out"] = iso["corrente_1_t_in"]
    ok, msg, _ = M.sizing_constraints(M.case_input(iso), params(), {})
    assert not ok and "isotérmico" in msg and "§3.1.3" in msg
    r = size_envelope(EQ, M, CaseSet([Case("isotérmica", iso)]))
    assert not r.feasible and "isotérmico" in r.message


def test_o_metodo_esta_registrado_e_o_par_equipamento_metodo_fecha():
    eq, m = registro.resolver("pinch", "pinch_kemp")
    assert isinstance(eq, PinchTarget) and isinstance(m, PinchKemp)
    assert m.applies_to().method_id == eq.method_id == "pinch"
    eq2, m2 = registro.resolver("pinch")     # método único do equipamento
    assert m2.method_id == "pinch_kemp"


def test_o_eixo_e_o_dt_min_e_a_exigencia_e_o_qhmin():
    p = params()
    eixo = M.sweep_axis(p)
    assert eixo.key == "dt_min" and eixo.unit == "°C"
    assert eixo.values[0] == 5.0 and eixo.values[-1] == 50.0
    assert p["dt_min_alvo"] in eixo.values     # o alvo é atingível pela grade
    correntes = M.case_input(valores_kemp())
    ok, cons, _ = M.sizing_constraints(correntes, p, {})
    assert ok
    # `requirement` é exatamente o QHmin do núcleo puro — nenhuma física reimplementada
    for dt in (5.0, 10.0, 20.0, 50.0):
        assert M.requirement(dt, cons) == pa.problem_table(correntes, dt).q_h_min
    # e é não-decrescente, que é o que autoriza chamá-la de exigência
    qs = [M.requirement(x, cons) for x in eixo.values]
    assert all(b - a >= -1e-9 for a, b in zip(qs, qs[1:]))
    # nenhum ponto da grade é inadmissível: não há critério a citar para recusar um
    assert all(M.case_admissible(x, cons, p) for x in eixo.values)
    assert M.ceiling_of(cons) == math.inf


def test_o_dimensionamento_reproduz_os_numeros_publicados_pelo_motor():
    cs = CaseSet([Case("Tabela 2.2", valores_kemp())])
    assert cs.corner_count() == 1
    r = size_envelope(EQ, M, cs)
    assert r.feasible
    assert r.x == 10.0 and abs(r.y - 20.0) <= 1e-9
    d = r.derivados
    assert abs(d["qcmin"] - 60.0) <= 1e-9 and abs(d["recuperacao"] - 450.0) <= 1e-9
    assert abs(d["t_pinch_deslocada"] - 85.0) <= 1e-9
    assert (d["n_quentes"], d["n_frias"], d["n_intervalos"]) == (2.0, 2.0, 5.0)
    assert governing_summary(M, r).startswith("Governa: utilidade quente (QHmin)")


def test_o_problema_limiar_chega_ao_cartao_dizendo_o_que_e():
    v = valores_kemp()
    v.update(dt_min_alvo=5.0, dt_min_min=1.0, dt_min_max=5.0, dt_min_step=1.0)
    r = size_envelope(EQ, M, CaseSet([Case("limiar", v)]))
    assert r.feasible and abs(r.y) <= 1e-9 and r.derivados["threshold"] == 1.0
    campos = {c.label: c.value for c in M.result_fields(r)}
    assert campos["Situação do pinch"] == "sem pinch (problema-limiar)"
    assert not math.isfinite(campos["T de pinch (deslocada)"])


def test_o_envelope_toma_o_pior_cenario_e_diz_qual_e():
    """Dois cenários da MESMA rede: no segundo a corrente quente 2 entrega menos calor, e menos
    calor quente disponível é MAIS utilidade quente exigida."""
    magro = valores_kemp()
    magro["corrente_2_mcp"] = 1.0
    r = size_envelope(EQ, M, CaseSet([Case("nominal", valores_kemp()), Case("quente fraca", magro)]))
    assert r.feasible and r.driver_case == "quente fraca" and r.y > 20.0
    assert len(r.slack) == 2 and abs(min(r.slack)) <= 1e-9
    assert M.governing_label(r.governing) == "utilidade quente (QHmin)"


def test_o_cartao_diz_o_que_a_tela_nao_faz():
    """O aviso de escopo é texto de domínio, logo sai de `result_fields` e não da interface."""
    r = size_envelope(EQ, M, CaseSet([Case("Tabela 2.2", valores_kemp())]))
    campos = M.result_fields(r)
    aviso = campos[0].value
    assert "NÃO dimensiona" in aviso and "NÃO sintetiza" in aviso
    # e o resíduo do balanço de entalpia é julgado, não só exibido
    residuo = next(c for c in campos if c.label.startswith("Resíduo"))
    assert residuo.status == "ok" and abs(residuo.value) <= 1e-9


def test_o_memorial_carrega_o_balanco_de_entalpia_como_conferencia():
    r = size_envelope(EQ, M, CaseSet([Case("Tabela 2.2", valores_kemp())]))
    vars_ = {e.var: e for e in r.per_case[0].trace.entries}
    assert "ΣQ quente" in vars_ and "ΣQ frio" in vars_
    conf = vars_["QCmin − QHmin"]
    assert abs(conf.value - 40.0) <= 1e-9 and "qualquer ΔTmin" in conf.formula
    assert [b for b, _ in M.trace_blocks()] == ["correntes", "selection"]


def test_a_apresentacao_conserva_o_calculo_do_nucleo_por_caso_e_dt_min():
    """`presentation_data` devolve a própria tabela e as curvas daquele ΔTmin: exigência,
    derivados, rastro e figuras leem o mesmo cálculo."""
    r = size_envelope(EQ, M, CaseSet([Case("Tabela 2.2", valores_kemp())]))
    linha = next(s for s in r.per_case[0].sweep if s.x == 10.0)
    tabela, curvas = linha.presentation
    assert isinstance(tabela, pa.PinchResult) and isinstance(curvas, pa.CompositeCurves)
    assert abs(tabela.q_h_min - 20.0) <= 1e-9 and abs(curvas.q_rec - 450.0) <= 1e-9
