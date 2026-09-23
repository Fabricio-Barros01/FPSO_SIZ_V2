"""F5 — motor de dimensionamento genérico, provado com métodos-brinquedo declarados aqui
(fora de src/): um "vaso" com teto por caso e um equipamento que não é vaso nenhum."""
import math

import pytest

from fpso_siz.core import registro
from fpso_siz.core.casos import Case, CaseSet
from fpso_siz.core.contrato import (Equipamento, MetodoDimensionamento, ResultField, SweepAxis, SweepColumn,
                                    column_value, der)
from fpso_siz.core.motor import governing_summary, size_envelope, size_single
from fpso_siz.core.parametros import ParameterSpec
from fpso_siz.core.trace import Rastro


class Tanque(Equipamento):
    method_id, label = "tanque", "Tanque de brinquedo"


class MetodoTanque(MetodoDimensionamento):
    """y(x) = fator·Q/x (exigência cai com x); derivado r = y/x deve ficar na banda;
    teto por caso; piso por caso (case_admissible); objetivo |r − alvo|."""
    method_id, label = "tanque_brinquedo", "Método de brinquedo"

    def applies_to(self):
        return Tanque()

    def parameters(self):
        return [ParameterSpec(*a) for a in [("x_min", "x mínimo", "mm", 100.0, 1.0, 1e5),
                                            ("x_max", "x máximo", "mm", 1000.0, 1.0, 1e5),
                                            ("x_step", "passo", "mm", 100.0, 1.0, 1e4),
                                            ("r_min", "r mínimo", "-", 0.0, 0.0, 1e9),
                                            ("r_max", "r máximo", "-", 1e9, 0.0, 1e9),
                                            ("alvo", "r alvo", "-", 0.0, 0.0, 1e9),
                                            ("fator", "fator", "-", 1.0, 0.0, 1e9),
                                            ("teto", "teto", "mm", math.inf, 0.0, math.inf),
                                            ("piso", "piso", "mm", 0.0, 0.0, 1e9)]]

    def stream_keys(self):
        return ("q_oil", "q_water")

    def method_config(self):
        return {"constants": {"escala": 3600.0}}

    def sizing_constraints(self, s, p, k):
        tr = Rastro()
        q = tr.trace("vazao", "Eq. 1", "Q", "Q_o + Q_w", (s.oil.volumetric_flow + s.water.volumetric_flow) * k["escala"], "m³/h")
        if q <= 0:
            return False, "vazão nula", tr
        return True, dict(q=q, fator=p["fator"], teto=p["teto"], piso=p["piso"]), tr

    def sweep_axis(self, p):
        n = int((p["x_max"] - p["x_min"]) // p["x_step"]) + 1 if p["x_max"] >= p["x_min"] else 0
        return SweepAxis("x", "diâmetro", "mm", tuple(p["x_min"] + i * p["x_step"] for i in range(n)))

    def requirement(self, x, c):
        return c["fator"] * c["q"] / x

    def governing_of(self, x, c):
        return "vazao"

    def ceiling_of(self, c):
        return c["teto"]

    def ceiling_mechanism_of(self, c):
        return "teto_de_brinquedo" if math.isfinite(c["teto"]) else "none"

    def case_admissible(self, x, c, p):
        return x >= c["piso"]

    def derived(self, x, y, gov, c, k, p):
        return {"r": y / x}

    def admissible(self, x, d, p):
        return p["r_min"] <= d["r"] <= p["r_max"]

    def objective(self, x, d, p):
        return abs(d["r"] - p["alvo"])

    def envelope_params(self, params):
        r_min = max(p["r_min"] for p in params)
        r_max = min(p["r_max"] for p in params)
        if r_min > r_max:
            return False, "bandas de r não se cruzam"
        return True, dict(x_min=min(p["x_min"] for p in params), x_max=max(p["x_max"] for p in params),
                          x_step=min(p["x_step"] for p in params), r_min=r_min, r_max=r_max,
                          alvo=min(max(sum(p["alvo"] for p in params) / len(params), r_min), r_max))

    def selection_message(self, rows, ceiling, p, mechanism="none"):
        return f"Nenhum x admissível (teto {ceiling}, mecanismo {mechanism})."

    def governing_label(self, g):
        return {"vazao": "capacidade de vazão"}.get(g, g)

    def result_fields(self, r):
        return [ResultField("x", r.x, unit="mm", digits=0, highlight=True), ResultField("governa", r.governing)]

    def sweep_columns(self):
        return [SweepColumn("x (mm)", "x", 0), SweepColumn("y", "y"), SweepColumn("r", "r", 4), SweepColumn("?", "nada")]


class Linha(Equipamento):
    method_id, label = "linha", "Linha (não é vaso)"


class MetodoLinha(MetodoTanque):
    """Outro equipamento, outra escolha: o menor x admissível (como o DN de uma bomba)."""
    method_id, label = "linha_brinquedo", "Linha de brinquedo"

    def applies_to(self):
        return Linha()

    def objective(self, x, d, p):
        return x


EQ, M = Tanque(), MetodoTanque()
BASE = {"q_oil": 36.0, "q_water": 36.0}   # Q = 72 m³/h


def env(*casos, m=M, eq=EQ, **kw):
    return size_envelope(eq, m, CaseSet([Case(n, v) for n, v in casos]), **kw)


def test_um_caso_e_o_dimensionamento_simples():
    vals = BASE | {"alvo": 0.001}
    s = size_single(EQ, M, M.case_input(vals), vals)
    e = env(("A", vals))
    assert e.feasible and s.feasible
    assert (e.x, e.y, e.derivados, e.governing) == (s.x, s.y, s.derivados, s.governing)
    assert e.driver_case == "A" and e.case_names == ["A"] and e.slack == [0.0]
    assert len(e.rows) == len(s.sweep) == 10
    assert e.per_case[0].trace.entries[0].var == "Q" and e.per_case[0].method_id == "tanque_brinquedo"


def test_envelope_cobre_todos_e_nomeia_o_governante():
    e = env(("leve", BASE), ("pesado", BASE | {"q_water": 360.0}))
    assert e.feasible and e.driver_case == "pesado"
    for row in e.rows:
        assert row.y == max(row.per_case_y) and len(row.per_case_y) == 2
    escolhida = next(r for r in e.rows if r.x == e.x)
    assert all(v <= escolhida.y for v in escolhida.per_case_y)
    assert e.slack[e.case_names.index("pesado")] == 0.0 and e.slack[0] > 0
    assert e.y > env(("leve", BASE)).y


def test_faixas_viram_cantos_e_o_pior_governa():
    e = env(("faixa", BASE | {"q_oil": [10.0, 100.0]}))
    assert e.case_names == ["faixa [q_oil↓]", "faixa [q_oil↑]"] and e.driver_case == "faixa [q_oil↑]"
    ref = env(("pior", BASE | {"q_oil": 100.0}))
    assert (e.x, e.y) == (ref.x, ref.y)


def test_teto_e_o_menor_entre_os_casos():
    e = env(("A", BASE | {"teto": 700.0}), ("B", BASE | {"teto": 500.0}))
    assert e.feasible and e.ceiling == 500.0 and e.ceiling_case == "B" and e.ceiling_mechanism == "teto_de_brinquedo"
    assert e.x <= 500.0 and all(not r.ok for r in e.rows if r.x > 500.0)
    # exigências empatadas: governa o primeiro caso (como o findmax do Julia); o teto é de outro
    assert governing_summary(M, e) == ("Governa: capacidade de vazão, pelo caso 'A'. Teto de decantação: 500 mm, "
                                       "imposto pelo caso 'B'.")
    assert governing_summary(M, env(("A", BASE))).endswith("pelo caso 'A'.")


def test_equipamento_que_nao_e_vaso_escolhe_pelo_proprio_objetivo():
    e = env(("A", BASE | {"piso": 300.0}), ("B", BASE | {"piso": 400.0}), m=MetodoLinha(), eq=Linha())
    assert e.feasible and e.x == 400.0          # o menor x que TODOS os casos aceitam


@pytest.mark.parametrize("casos, kw, trecho", [
    ((), {}, "Nenhum caso ativo. Adicione ao menos uma corrente."),
    ((("X", BASE | {"q_oil": [1, 2], "q_water": [1, 2]}),), {"max_corners": 2},
     "ArgumentError: expansão geraria 4 casos de canto (limite 2)."),
    ((("X", {"q_oil": 1.0}),), {}, "Caso 'X': ArgumentError: caso sem as entradas de corrente: q_water"),
    ((("X", {"q_oil": 0.0, "q_water": 0.0}),), {}, "Caso 'X': vazão nula"),
    ((("A", BASE | {"r_min": 5.0}), ("B", BASE | {"r_max": 1.0})), {}, "bandas de r não se cruzam"),
    ((("A", BASE | {"x_min": 900.0, "x_max": 100.0}),), {}, "Grade de diâmetro vazia."),
    ((("A", BASE | {"teto": 50.0}),), {}, "Não há equipamento que atenda simultaneamente aos 1 casos. Nenhum x"),
])
def test_inviabilidade_e_estado(casos, kw, trecho):
    e = env(*casos, **kw)
    assert not e.feasible and e.message.startswith(trecho) and math.isnan(e.x)
    assert governing_summary(M, e) == e.message


def test_so_o_motor_sabe_que_as_faixas_nao_se_cruzam():
    e = env(("baixo", BASE | {"teto": 300.0}), ("alto", BASE | {"piso": 500.0}))
    assert not e.feasible
    assert e.message.endswith("Isolado, cada caso tem diâmetro admissível, mas as faixas não se cruzam: "
                              "'baixo' aceita 100.0–300.0 mm; 'alto' aceita 500.0–1000.0 mm. Como o equipamento é "
                              "um só, amplie a banda, ou trate os casos em equipamentos separados.")
    assert env(("baixo", BASE | {"teto": 100.0}), ("alto", BASE | {"piso": 1000.0})).message.count("'baixo' aceita 100.0 mm")


def test_erro_aritmetico_vira_inviabilidade_nunca_excecao():
    class Quebra(MetodoTanque):
        def requirement(self, x, c):
            return 1.0 / 0.0
    e = env(("A", BASE), m=Quebra())
    assert not e.feasible and e.message.startswith("Erro numérico no cálculo (ZeroDivisionError")
    s = size_single(EQ, Quebra(), Quebra().case_input(BASE), BASE)
    assert not s.feasible and "Erro numérico" in s.message


def test_metodo_de_outro_equipamento():
    e = env(("A", BASE), eq=Linha())
    assert not e.feasible and e.message == "O método 'Método de brinquedo' não se aplica a 'Linha (não é vaso)'."


def test_caso_unico_inviavel():
    s = size_single(EQ, M, M.case_input(BASE), BASE | {"teto": 50.0})
    assert not s.feasible and s.message.startswith("Nenhum x") and len(s.sweep) == 10
    assert size_single(EQ, M, M.case_input(BASE), BASE | {"x_min": 5.0, "x_max": 1.0}).message == "Grade de diâmetro vazia."
    z = size_single(EQ, M, M.case_input({"q_oil": 0.0, "q_water": 0.0}), {})
    assert z.message == "vazão nula" and len(z.trace) == 1


def test_colunas_e_campos():
    e = env(("A", BASE))
    linha = e.rows[0]
    assert [column_value(linha, c) for c in M.sweep_columns()][:3] == [linha.x, linha.y, linha.derivados["r"]]
    assert math.isnan(column_value(linha, M.sweep_columns()[3])) and math.isnan(der(e, "nada"))
    assert M.result_fields(e)[0].value == e.x and M.result_fields(e)[1].value == "vazao"
    assert (M.requirement_spec(), M.action_label(), M.trace_blocks(), M.global_keys()) == \
        (("exigência", ""), "Dimensionar", [], [])


def test_rastro_sequencial():
    t = Rastro()
    assert t.trace("b", "Eq. 1", "a", "f", 2.0, "m") == 2.0
    t.trace("c", "Eq. 2", "b", "g", 3.0, "m")
    t.trace("b", "Eq. 3", "c", "h", 4.0, "m")
    assert t.block_order() == ["b", "c"] and [e.eq for e in t.block_entries("b")] == ["Eq. 1", "Eq. 3"]
    assert len(t) == 3 and [e.value for e in t] == [2.0, 3.0, 4.0]


def test_registro():
    registro._reset()
    try:
        registro.register(Tanque())
        registro.register(M)
        registro.register(MetodoTanque())            # mesmo id: substitui
        registro.register(Linha())
        assert [e.method_id for e in registro.equipments()] == ["linha", "tanque"]
        assert len(registro.methods_for("tanque")) == 1 and registro.methods_for(Linha()) == []
        assert registro.sizing_method("tanque", "tanque_brinquedo").label == "Método de brinquedo"
        assert registro.sizing_method("tanque", "outro") is None and registro.equipment("x") is None
        with pytest.raises(TypeError):
            registro.register(object())
    finally:
        registro._reset()


def test_hooks_sem_default_exigem_implementacao():
    m = MetodoDimensionamento()
    for chamada in (m.applies_to, m.parameters, m.method_config, lambda: m.sweep_axis({}), lambda: m.requirement(1, {}),
                    lambda: m.governing_of(1, {}), lambda: m.derived(1, 1, "", {}, {}, {}), lambda: m.admissible(1, {}, {}),
                    lambda: m.objective(1, {}, {}), lambda: m.envelope_params([]), lambda: m.result_fields(None),
                    m.sweep_columns, lambda: m.sizing_constraints(None, {}, {}),
                    lambda: m.selection_message([], 0, {})):
        with pytest.raises(NotImplementedError):
            chamada()
    assert (m.ceiling_of({}), m.per_constraint(1, {}), m.presentation_data(1, {}, {}, {}), m.grid_hint({}),
            m.governing_label("g"), m.parameter_groups()) == (math.inf, {}, None, "", "g", [])
