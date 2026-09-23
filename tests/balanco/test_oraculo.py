"""F1 — o oráculo do balanço é íntegro, reproduzível e coincide com o snapshot Julia.

Os testes que dependem de `references/` (fora do git) são pulados quando o acervo
local não existe; os estruturais rodam sempre, só com a fixture versionada.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "tests" / "fixtures" / "python_ref"
REFS = RAIZ / "references"
SNAPSHOT_JULIA = REFS / "bot" / "balanco_python.json"

precisa_refs = pytest.mark.skipif(
    not (REFS / "Balanço_Preliminar.py").exists(), reason="acervo local references/ ausente"
)


@pytest.fixture(scope="module")
def oraculo():
    return json.loads((FIXTURES / "oraculo_balanco.json").read_text(encoding="utf-8"))


def carregar_gerador():
    spec = importlib.util.spec_from_file_location("gerador", RAIZ / "tools" / "gerar_oraculo_balanco.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ estrutura
def test_dimensoes(oraculo):
    assert len(oraculo["casos"]) == 16
    assert [c["num"] for c in oraculo["casos"]] == list(range(1, 17))
    assert len(oraculo["topologia"]["blocos"]) == 16
    assert len(oraculo["topologia"]["correntes"]) == 26
    for c in oraculo["casos"]:
        assert len(c["streams"]) == 26
        assert all(set(s) == {"O", "W", "D", "G"} for s in c["streams"].values())
        assert set(c["block_balance"]) == {b["id"] for b in oraculo["topologia"]["blocos"]}


def test_reciclo_convergiu_em_todos_os_casos(oraculo):
    assert all(c["reciclo"]["convergiu"] for c in oraculo["casos"])
    assert all(c["reciclo"]["convergiu"] for c in (s["resultado"] for s in oraculo["sensibilidade"]))


def test_stdout_e_main_tex(oraculo):
    prov = oraculo["proveniencia"]
    assert prov["stdout"] == "ok 1658"
    main = (FIXTURES / "main_ref.tex").read_bytes()
    assert hashlib.sha256(main).hexdigest() == prov["main_tex_sha256"]
    assert len(main) == prov["main_tex_bytes"]


def test_sensibilidade_cobre_casos_e_variacoes(oraculo):
    sens = oraculo["sensibilidade"]
    assert len(sens) == len(oraculo["casos_sensibilidade"]) * 8
    base = {s["num"]: s["resultado"] for s in sens if not s["premissas_alteradas"]}
    casos = {c["num"]: c for c in oraculo["casos"]}
    for n, r in base.items():  # variação "Base" == resultado do caso
        assert r["streams"] == casos[n]["streams"]
        assert r["duties"] == casos[n]["duties"]


# ------------------------------------------------------------ proveniência
@precisa_refs
def test_hashes_batem_com_o_acervo(oraculo):
    prov = oraculo["proveniencia"]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(REFS / prov["script"]) == prov["script_sha256"]
    assert sha(REFS / prov["entrada"]) == prov["entrada_sha256"]


@precisa_refs
def test_regeneracao_e_byte_identica(tmp_path):
    carregar_gerador().main(["--referencias", str(REFS), "--saida", str(tmp_path)])
    for nome in ("oraculo_balanco.json", "main_ref.tex"):
        assert (tmp_path / nome).read_bytes() == (FIXTURES / nome).read_bytes(), nome


# --------------------------------------------------- snapshot do Julia
@pytest.mark.skipif(not SNAPSHOT_JULIA.exists(), reason="snapshot Julia ausente")
def test_coincide_com_snapshot_julia(oraculo):
    j = json.loads(SNAPSHOT_JULIA.read_text(encoding="utf-8"))
    prov = oraculo["proveniencia"]
    assert j["provenance"]["python_sha256"] == prov["script_sha256"]
    assert j["provenance"]["input_json_sha256"] == prov["entrada_sha256"]
    assert j["original_main_tex_sha256"] == prov["main_tex_sha256"]
    assert j["original_stdout"] == prov["stdout"]
    assert j["premises"] == oraculo["premissas"]
    assert j["original_audit"] == [
        [a["verificacao"], a["base"], a["max_desvio_abs"], a["unidade"]] for a in oraculo["auditoria"]
    ]
    campos = ("fluid", "well", "api", "rho", "cp", "gp", "Wv", "BSW01", "BSW_F",
              "streams", "T", "P", "duties", "gas")
    for co, cj in zip(oraculo["casos"], j["cases"], strict=True):
        assert cj["case"]["num"] == co["num"]
        for k in campos:  # igualdade exata: mesmo script, mesma aritmética
            assert cj[k] == co[k], (co["num"], k)
        assert cj["iters"] == co["reciclo"]["iters"]
        assert cj["mu"] == [co["mu"]["valor"], co["mu"]["flag"]]
        assert cj["global_balance"] == co["global_balance"]
        assert cj["block_balances"] == co["block_balance"]
