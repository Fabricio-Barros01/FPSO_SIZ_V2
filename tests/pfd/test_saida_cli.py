import csv
import json
from pathlib import Path

import pytest

from fpso_siz.cli import main
from fpso_siz.output import pfd

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CASOS = FIXTURES / "python_ref" / "design_cases_bot.json"
AJUSTES = FIXTURES / "pfd" / "ajustes_sinteticos.toml"


@pytest.mark.parametrize("nome", ["planta_base", "planta_propostas"])
def test_exportacao_estrita_com_lacunas_e_inviabilidade(request, nome, tmp_path):
    """Sem as propostas a planta tem lacunas (aguardando entrada); com elas, os 11 TAGs são
    dimensionados. O JSON é estrito nos dois estados."""
    p = request.getfixturevalue(nome)
    arquivos = pfd.gravar(p, tmp_path)
    # JSON + CSV de varredura por TAG, planta.csv e a integração térmica realizada (JSON + CSV)
    assert len(arquivos) == 25
    for t in p.tags:
        texto = (tmp_path / f"{t.tag.tag}.json").read_text(encoding="utf-8")
        obj = json.loads(texto, parse_constant=lambda x: pytest.fail(f"JSON não estrito: {x}"))
        assert obj["schema_version"] == 2 and obj["modo"] == "automatico" and not obj["avulso"]
        assert obj["status"] == t.status and obj["preliminar"] == bool(obj["revisoes"])
        assert obj["proveniencia"]["sha256"] == p.dados.sha256
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
    esperado = {"aguardando_entrada", "dimensionado"} if nome == "planta_base" else {"dimensionado"}
    assert {x["status"] for x in linhas} == esperado


def test_cli_sem_ajustes_e_sem_saida(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["pfd", "--sem-propostas", "--casos", str(CASOS)]) == 1
    out = capsys.readouterr().out
    assert "aguardando entrada" in out and "t_agua_out" in out
    assert "revisão pendente" in out and "M-01" in out
    assert not list(tmp_path.iterdir())


def test_cli_exporta_os_mesmos_bytes(planta_ajustada, tmp_path, capsys):
    a, b = tmp_path/"api", tmp_path/"cli"
    pfd.gravar(planta_ajustada, a)
    assert main(["pfd", "--sem-propostas", "--casos", str(CASOS), "--ajustes", str(AJUSTES),
                 "--saida", str(b)]) == 1   # o P-002 e o P-003 esperam as temperaturas da utilidade
    assert "gravados:" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    for caminho in b.glob("*.json"):
        obj = json.loads(caminho.read_text(encoding="utf-8"))
        if "envelope" not in obj:          # integracao_termica.json não é o JSON de um TAG
            assert caminho.name == pfd.ARQ_INTEGRACAO
            continue
        if obj["envelope"] is not None:
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
    # 0 = planta completa (ADR 0005); o que o teste cobra é a premissa alterada no JSON
    assert main(["pfd", "--casos", str(CASOS), "--premissa", "eta_pump=0.8", "--saida", str(tmp_path)]) == 0
    capsys.readouterr()
    obj = json.loads((tmp_path/"B-001.json").read_text(encoding="utf-8"))
    assert obj["premissas"]["eta_pump"] == 0.8
    assert obj["casos"][0]["valores"]["rendimento"]["valor"] == 0.8
