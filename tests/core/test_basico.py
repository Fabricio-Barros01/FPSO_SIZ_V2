"""F5 — formato Julia, descritores, casos/cantos e corrente, contra as fixtures do Julia."""
import json
import math
import tomllib
from pathlib import Path

import pytest

from fpso_siz.core.casos import Case, CaseSet, Interval, case_set_from_config, corners
from fpso_siz.core.contrato import MetodoDimensionamento
from fpso_siz.core.corrente import STREAM_KEYS, stream_from_case, stream_parameters
from fpso_siz.core.formato_julia import jl, jl_round
from fpso_siz.core.parametros import (ParameterSpec, defaults, group_instance, group_specs, in_group, instance_key,
                                      is_template, parameter_specs, single_box, validar, validate, with_defaults)

FJ = Path(__file__).resolve().parents[1] / "fixtures" / "julia"
MANIFESTO = json.loads((FJ / "manifesto.json").read_text(encoding="utf-8"))
BOXES = [json.loads((FJ / a).read_text(encoding="utf-8")) for a in MANIFESTO["arquivos"] if a != "formatos_julia.json"]
COM_EXEMPLO = [b for b in BOXES if "exemplo" in b]


def spec_dict(s):
    return {k: getattr(s, k) for k in ("key", "label", "unit", "default", "min", "max", "advanced", "note", "group",
                                       "instance")}


# ------------------------------------------------------------------ formato
def test_numeros_como_o_julia():
    f = json.loads((FJ / "formatos_julia.json").read_text(encoding="utf-8"))
    assert [jl(x) for x, _ in f["string"]] == [s for _, s in f["string"]]
    assert [jl_round(x, 2) for x, _ in f["round2"]] == [s for _, s in f["round2"]]
    assert [jl_round(x, 0) for x, _ in f["round0"]] == [s for _, s in f["round0"]]
    assert (jl(math.nan), jl(math.inf), jl(-math.inf)) == ("NaN", "Inf", "-Inf")


# ------------------------------------------------------------------ descritores
def test_descritores_de_corrente_iguais_ao_julia():
    assert [spec_dict(s) for s in stream_parameters()] == MANIFESTO["stream_parameters"]


# knockout, tratador e bomba REETIQUETAM os campos herdados (o "óleo" do knockout é o
# condensado): isso é do método (F6/F7). O default filtra por stream_keys, na ordem do TOML.
REETIQUETAM = {"knockout-2f", "vaso-eletrostatico", "bomba-centrifuga"}


@pytest.mark.parametrize("box", BOXES, ids=lambda b: b["box"])
def test_filtragem_por_stream_keys(box):
    class M(MetodoDimensionamento):
        def stream_keys(self):
            return tuple(box["stream_keys"])
    nossos = [spec_dict(s) for s in M().stream_parameters()]
    assert [s["key"] for s in nossos] == [s["key"] for s in box["stream_parameters"]]
    if box["box"] not in REETIQUETAM:
        assert nossos == box["stream_parameters"]


def test_validacao_e_defaults():
    s = ParameterSpec("q", "Vazão", "m³/h", 10.0, 0.1, 1.0e6)
    assert validate(s, 5) is None
    assert validate(s, 0.0) == "Vazão: abaixo do mínimo (0.1 m³/h)"
    assert validate(s, 2e6) == "Vazão: acima do máximo (1.0e6 m³/h)"
    assert validate(s, math.nan) == "Vazão: valor não numérico"
    assert validar([s], {"q": -1, "outro": 3}) == ["Vazão: abaixo do mínimo (0.1 m³/h)"]
    assert defaults([s]) == {"q": 10.0}
    assert with_defaults([s], {"q": 3, "x": 9}) == {"q": 3.0}


def test_grupos():
    cfg = {"group": [{"key": "corrente", "label": "Corrente", "min": 2, "max": 12}],
           "parameter": [{"key": "t_in", "label": "T entrada", "unit": "°C", "default": 100, "min": -50, "max": 500,
                          "group": "corrente"}]}
    (s,) = parameter_specs(cfg)
    assert in_group(s) and is_template(s) and single_box(s) and group_specs(cfg)[0]["max"] == 12
    i2 = group_instance(s, 2, prefixo="Corrente")
    assert (i2.key, i2.label, i2.instance) == (instance_key("corrente", 2, "t_in"), "Corrente 2 — T entrada", 2)
    for ruim, msg in [(lambda: group_instance(i2, 3), "molde"), (lambda: group_instance(s, 0), "≥ 1")]:
        with pytest.raises(ValueError, match=msg):
            ruim()


@pytest.mark.parametrize("cfg, msg", [
    ({"parameter": [{"key": "a"}]}, "obrigatório 'label'"),
    ({"parameter": [{"key": "a", "label": "A", "unit": "", "default": 1, "min": 0, "max": 2, "group": "x"}]}, "group"),
    ({"group": [{"key": "g", "label": "G", "min": 3, "max": 2}]}, "min ≤ max"),
    ({"group": [{"key": "g"}]}, "obrigatório 'label'"),
])
def test_erros_de_configuracao(cfg, msg):
    with pytest.raises(ValueError, match=msg):
        parameter_specs(cfg)


# ------------------------------------------------------------------ casos e cantos
@pytest.mark.parametrize("box", COM_EXEMPLO, ids=lambda b: b["exemplo"])
def test_casos_e_expansao_iguais_ao_julia(box):
    cs = case_set_from_config(tomllib.loads((FJ / "casos" / f"{box['exemplo']}.toml").read_text(encoding="utf-8")))
    assert [(c.name, c.enabled, {k: [v.lo, v.hi] if isinstance(v, Interval) else v for k, v in c.values.items()})
            for c in cs.cases] == [(c["name"], c["enabled"], c["values"]) for c in box["casos"]]
    assert [(n, v) for n, v in cs.expand()] == [(e["name"], e["values"]) for e in box["expansao"]]


def test_cantos_ordem_do_julia():
    cs = CaseSet([Case("A", {"b": [1, 2], "a": (20, 10), "c": 5, "d": [7, 7]})])
    assert cs.corner_count() == 4
    assert [n for n, _ in cs.expand()] == ["A [a↓ b↓]", "A [a↑ b↓]", "A [a↓ b↑]", "A [a↑ b↑]"]
    assert cs.expand()[1][1] == {"a": 20.0, "b": 1.0, "c": 5.0, "d": 7.0}
    assert corners(Interval(3, 3)) == (3.0,) and Interval(5, 1) == Interval(1, 5)
    assert CaseSet([Case("x", {"a": 1}, enabled=False)]).expand() == []


def test_limites_da_expansao():
    cs = CaseSet([Case("A", {k: [0, 1] for k in "abcde"})])
    with pytest.raises(ValueError, match=r"geraria 32 casos de canto \(limite 8\)"):
        cs.expand(max_corners=8)
    with pytest.raises(ValueError, match="exatamente 2"):
        Case("A", {"a": [1, 2, 3]})
    with pytest.raises(ValueError, match="name"):
        case_set_from_config({"case": [{"a": 1}]})


# ------------------------------------------------------------------ corrente
def test_corrente_em_si_e_nan_no_que_nao_se_exige():
    vals = {k: 1.0 for k in STREAM_KEYS} | {"q_oil": 3600.0, "mu_oil": 2.0, "pressure": 101.3, "temperature": 25.0}
    s = stream_from_case(vals)
    assert (s.oil.volumetric_flow, s.oil.viscosity, s.pressure, s.temperature) == (1.0, 0.002, 101300.0, 298.15)
    parcial = stream_from_case({"q_oil": 36.0}, required=("q_oil",))
    assert parcial.oil.volumetric_flow == 0.01 and math.isnan(parcial.water.volumetric_flow)
    with pytest.raises(ValueError, match="q_water, q_gas"):
        stream_from_case({"q_oil": 1.0}, required=("q_oil", "q_water", "q_gas"))
