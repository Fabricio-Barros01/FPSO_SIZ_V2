import csv
import json
from pathlib import Path

import pytest

from fpso_siz.cli import main
from fpso_siz.output import pfd

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CASOS = FIXTURES / "python_ref" / "design_cases_bot.json"
AJUSTES = FIXTURES / "pfd" / "ajustes_sinteticos.toml"


def test_exportacao_estrita_com_lacunas_e_inviabilidade(planta_base, tmp_path):
    arquivos = pfd.gravar(planta_base, tmp_path)
    assert len(arquivos) == 23  # JSON + CSV de varredura por TAG, e planta.csv
    for t in planta_base.tags:
        texto = (tmp_path / f"{t.tag.tag}.json").read_text(encoding="utf-8")
        obj = json.loads(texto, parse_constant=lambda x: pytest.fail(f"JSON não estrito: {x}"))
        assert obj["schema_version"] == 2 and obj["modo"] == "automatico" and not obj["avulso"]
        assert obj["status"] == t.status and obj["preliminar"] == bool(obj["revisoes"])
        assert obj["proveniencia"]["sha256"] == planta_base.dados.sha256
        assert len(obj["casos"]) == 16 and obj["limitacoes"]
        for c in obj["casos"]:
            assert all(v["valor"] is None for v in c["valores"].values() if v["origem"] == "lacuna")
            assert all(v["revisao"] == "pendente" for v in c["valores"].values()
                       if v["origem"] == "recomendada") or not c["ativo"]
        with (tmp_path / f"{t.tag.tag}_varredura.csv").open(encoding="utf-8", newline="") as f:
            varredura = list(csv.DictReader(f))
        assert len(varredura) == (len(t.resultado.rows) if t.resultado is not None else 0)
    with (tmp_path / "planta.csv").open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 11 and tuple(linhas[0]) == pfd.COLUNAS
    assert {x["status"] for x in linhas} == {"aguardando_entrada", "inviavel", "dimensionado"}


def test_cli_sem_ajustes_e_sem_saida(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["pfd", "--sem-propostas", "--casos", str(CASOS)]) == 1
    out = capsys.readouterr().out
    assert "aguardando entrada" in out and "t_agua_out" in out and "inviável" in out
    assert "revisão pendente" in out and "M-01" in out and "[SG-001  X]" in out
    assert not list(tmp_path.iterdir())


def test_cli_exporta_os_mesmos_bytes(planta_ajustada, tmp_path, capsys):
    a, b = tmp_path/"api", tmp_path/"cli"
    pfd.gravar(planta_ajustada, a)
    assert main(["pfd", "--sem-propostas", "--casos", str(CASOS), "--ajustes", str(AJUSTES), "--saida", str(b)]) == 0
    assert "gravados:" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    for caminho in b.glob("*.json"):
        obj = json.loads(caminho.read_text(encoding="utf-8"))
        assert obj["envelope"]["resultado"]["caso_governante"]
        assert obj["envelope"]["rastros"] and obj["envelope"]["varredura"]


@pytest.mark.parametrize("texto,mensagem", [
    ('["X"]\na = 1', "TAGs desconhecidos"),
    ('["B-001"]\nq_oil = nan', "finito"),
    ('["B-001"]\nabc = 1', "desconhecida"),
    ('[', "erro:"),
    ('"B-001" = 1', "tabela"),
])
def test_erro_ajustes_claro(tmp_path, capsys, texto, mensagem):
    arq = tmp_path/"ajustes.toml"
    arq.write_text(texto, encoding="utf-8")
    assert main(["pfd", "--casos", str(CASOS), "--ajustes", str(arq)]) == 2
    assert mensagem in capsys.readouterr().err


def test_cli_premissa_registrada(tmp_path, capsys):
    assert main(["pfd", "--casos", str(CASOS), "--premissa", "eta_pump=0.8", "--saida", str(tmp_path)]) == 1
    capsys.readouterr()
    obj = json.loads((tmp_path/"B-001.json").read_text(encoding="utf-8"))
    assert obj["premissas"]["eta_pump"] == 0.8
    assert obj["casos"][0]["valores"]["rendimento"]["valor"] == 0.8
