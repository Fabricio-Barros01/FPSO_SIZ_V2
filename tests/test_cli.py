"""F3 — CLI de ponta a ponta, esquema JSON e CSV."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from fpso_siz.balanco.exportacao import colunas_correntes
from fpso_siz.cli import main

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
ESQUEMA = json.loads((RAIZ / "docs" / "esquemas" / "balanco.schema.json").read_text(encoding="utf-8"))
ORACULO = json.loads((RAIZ / "tests" / "fixtures" / "python_ref" / "oraculo_balanco.json").read_text(encoding="utf-8"))
PARIDADE = ["--regra-fwko", "referencia"]  # regra do FWKO do script de referência (o oráculo)
NOVAS = {"eta_F"}                          # premissas que o script de referência não tem (F10w)


def cargas_do_oraculo(cargas):
    """Esquema 2 → chaves do oráculo: o Q_H antigo (só o P-002) é o campo do P-002; Q_pre, Q_D
    e Q_C são os campos do P-001, do DWH-001 e do P-003; as potências mantêm as chaves."""
    tag = {"Q_pre": "P-001", "Q_H": "P-002", "Q_D": "DWH-001", "Q_C": "P-003"}
    return {**{k: cargas[t] for k, t in tag.items()}, **{k: v for k, v in cargas.items() if k.startswith("W_")}}


@pytest.fixture(scope="module")
def saida(tmp_path_factory):
    d = tmp_path_factory.mktemp("saida")
    assert main(["balanco", "--casos", str(CASOS), "--saida", str(d), *PARIDADE]) == 0
    return d


def test_padrao_usa_a_eficiencia_do_fwko(tmp_path, capsys):
    """F10w: sem --regra-fwko, η_A do SG-001 = máx(η_padrão; η_req); o JSON traz o estado."""
    assert main(["balanco", "--casos", str(CASOS), "--saida", str(tmp_path)]) == 0
    capsys.readouterr()
    j = json.loads((tmp_path / "balanco.json").read_text(encoding="utf-8"))
    jsonschema.validate(j, ESQUEMA)
    fw = {c["num"]: c["FWKO"] for c in j["casos"]}
    assert {f["regra"] for f in fw.values()} == {"eficiencia"}
    assert [n for n, f in fw.items() if f["exigido_acima"]] == [15, 16]
    assert fw[2]["eta"] == 0.85 and fw[1]["eta"] is None and fw[1]["eta_req"] is None
    assert fw[1]["estado"] == "não aplicável — sem fase aquosa" and fw[15]["estado"].startswith("exigido acima")
    assert j["esquema"] == 2 and {"Q_H", "Q_C", "P-001", "P-002", "DWH-001", "P-003"} <= set(j["casos"][1]["cargas"])
    assert "eficiencia_fwko" in {a["id"] for a in j["auditoria"]}


def test_json_valida_no_esquema(saida):
    jsonschema.validate(json.loads((saida / "balanco.json").read_text(encoding="utf-8")), ESQUEMA)


def test_json_reproduz_o_oraculo_bit_a_bit(saida):
    j = json.loads((saida / "balanco.json").read_text(encoding="utf-8"))
    assert j["entrada"]["sha256"] == ORACULO["proveniencia"]["entrada_sha256"]
    assert not any(p["alterada"] for p in j["premissas"])
    assert {p["nome"]: p["valor"] for p in j["premissas"] if p["nome"] not in NOVAS} == ORACULO["premissas"]
    for c, o in zip(j["casos"], ORACULO["casos"], strict=True):
        assert c["num"] == o["num"] and c["convergiu"]
        assert {k: v["vazao_massica_kg_s"] for k, v in c["correntes"].items()} == o["streams"]
        assert {k: v["T_C"] for k, v in c["correntes"].items()} == o["T"]
        assert cargas_do_oraculo(c["cargas"]) == o["duties"] and c["gas"] == o["gas"]
        assert c["cargas"]["Q_H"] == o["duties"]["Q_H"] + o["duties"]["Q_D"]  # utilidade: P-002 + DWH-001
        assert c["cargas"]["Q_C"] == o["duties"]["Q_C"]                         # utilidade: P-003
        assert c["balancos_bloco"] == o["block_balance"] and c["balanco_global"] == o["global_balance"]
    assert [a["max_desvio_abs"] for a in j["auditoria"]] == [a["max_desvio_abs"] for a in ORACULO["auditoria"]]


def test_csv_colunas_linhas_e_valores(saida):
    with (saida / "correntes.csv").open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert list(linhas[0]) == [c["id"] for c in colunas_correntes()]
    assert len(linhas) == 16 * 26
    o = {c["num"]: c for c in ORACULO["casos"]}
    for li in linhas:
        s = o[int(li["caso"])]["streams"][li["corrente"]]
        assert [float(li[k]) for k in ("m_O_kg_s", "m_W_kg_s", "m_D_kg_s", "m_G_kg_s")] == [s["O"], s["W"], s["D"], s["G"]]
        assert float(li["T_C"]) == o[int(li["caso"])]["T"][li["corrente"]]


def test_readme_documenta_todas_as_colunas():
    readme = (RAIZ / "docs" / "esquemas" / "README.md").read_text(encoding="utf-8")
    for c in colunas_correntes():
        assert f"| `{c['id']}` | {c['unidade']} |" in readme


def test_premissa_alterada(tmp_path, capsys):
    sens = next(s for s in ORACULO["sensibilidade"] if s["premissas_alteradas"] == {"BSW_pre": 0.02})
    assert main(["balanco", "--casos", str(CASOS), "--saida", str(tmp_path), "--premissa", "BSW_pre=0.02", *PARIDADE]) == 0
    assert "premissa alterada P-28 BSW_pre = 0.02" in capsys.readouterr().out
    j = json.loads((tmp_path / "balanco.json").read_text(encoding="utf-8"))
    assert [p["nome"] for p in j["premissas"] if p["alterada"]] == ["BSW_pre"]
    caso = next(c for c in j["casos"] if c["num"] == sens["num"])
    assert cargas_do_oraculo(caso["cargas"]) == sens["resultado"]["duties"]


@pytest.mark.parametrize("args, trecho", [
    (["--premissa", "BSW_X=1"], "premissas desconhecidas"),
    (["--premissa", "BSW_pre"], "NOME=VALOR"),
    (["--premissa", "BSW_pre=abc"], "não numérico"),
])
def test_erros_de_premissa(tmp_path, capsys, args, trecho):
    assert main(["balanco", "--casos", str(CASOS), "--saida", str(tmp_path), *args]) == 2
    err = capsys.readouterr().err
    assert trecho in err and not err.startswith("erro: \"")


def test_arquivo_inexistente(tmp_path):
    assert main(["balanco", "--casos", str(tmp_path / "nao.json"), "--saida", str(tmp_path)]) == 2


def test_nao_convergencia_retorna_1(tmp_path, capsys, monkeypatch):
    import dataclasses
    from types import MappingProxyType

    from fpso_siz.balanco import modelo

    const = modelo.constantes()
    curto = dataclasses.replace(const, numerico=MappingProxyType({**const.numerico, "reciclo_max_iter": 2}))
    monkeypatch.setattr(modelo, "constantes", lambda: curto)
    assert main(["balanco", "--casos", str(CASOS), "--saida", str(tmp_path)]) == 1
    assert "ATENÇÃO caso 2: reciclo não convergiu" in capsys.readouterr().out


def test_lista_premissas(capsys):
    assert main(["premissas"]) == 0
    sem = capsys.readouterr().out
    assert "(arquivo de casos)" in sem and "P-26" in sem
    assert main(["premissas", "--casos", str(CASOS)]) == 0
    assert "2500.0" in capsys.readouterr().out.splitlines()[0]


def test_python_m_fpso_siz():
    r = subprocess.run([sys.executable, "-m", "fpso_siz", "--version"], capture_output=True, text=True, check=True)
    assert r.stdout.startswith("fpso-siz ")
