"""F10c — `dimensionar --tag/--avulso`, `pfd --ajustes` (esquema 2) e `--ascii`: mesmos
bytes pelo TAG isolado, pela planta e pela sessão; erros de uso e de contexto (código 2)."""
import json

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.cli import main
from fpso_siz.output import ajustes as saida_ajustes
from fpso_siz.pfd import ajustes as A
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import manual

from conftest import FIXTURES

CASOS = FIXTURES / "python_ref" / "design_cases_bot.json"
AJUSTES_LEGADO = FIXTURES / "pfd" / "ajustes_sinteticos.toml"


@pytest.fixture
def arquivo_misto(tmp_path):
    """Modos mistos: V-001 manual parcial (pendências salvas), TO-001 automático com lacuna
    preenchida e recomendações não revisadas, SG-001 com revisão, e um avulso."""
    ctx = servico.Contexto(carregar_casos(CASOS), alteracoes={"eta_pump": 0.8})
    aj = A.Ajustes()
    v1 = servico.estado_inicial("V-001", A.MANUAL)
    v1.editar("q_oil", 250.0)
    to = servico.estado_inicial("TO-001")
    to.editar("dm_water", 800.0, anteriores={n: ("lacuna", "", None) for n in range(1, 17)})
    sg = servico.estado_inicial("SG-001")
    sg.confirmar("tr_water", {n: (10.0, "Stewart & Arnold (2008) §4.7.4: 'a water retention time of 10 min is "
                                        "recommended for design'") for n in range(1, 17)})
    cfg, origem = manual.ler_exemplo("knockout")
    imp = manual.importar(cfg, origem, "knockout", "stewart_arnold_2f",
                          servico.especificacoes_de("knockout", "stewart_arnold_2f", pfd=False))
    ko = manual.avulso("ko", "knockout", "stewart_arnold_2f", imp=imp)
    ko.editar("tr_liquid", 3.0)
    ko2 = manual.avulso("ko2", "knockout", "stewart_arnold_2f", imp=imp)
    ko2.editar("tr_liquid", 3.0)
    ko2.editar("d_step", 50.0)  # vaso pequeno: com o passo de 150 mm, nenhum d cai na banda de SR
    aj.tags = {"V-001": v1, "TO-001": to, "SG-001": sg}
    aj.avulsos = {"ko": ko, "ko2": ko2}
    return saida_ajustes.gravar(aj, ctx, tmp_path / "ajustes_pfd.toml")


def _bytes(pasta):
    return {p.name: p.read_bytes() for p in sorted(pasta.iterdir())}


def test_tag_isolado_planta_e_modos_mistos_mesmos_bytes(arquivo_misto, tmp_path, capsys):
    planta, tag_ = tmp_path / "planta", tmp_path / "tag"
    base = ["--casos", str(CASOS), "--ajustes", str(arquivo_misto), "--premissa", "eta_pump=0.8"]
    assert main(["pfd", *base, "--saida", str(planta)]) == 1
    for ident, rc in (("V-001", 1), ("TO-001", 0), ("SG-001", 0), ("B-001", 1)):
        auto = ["--auto-balanco"] if ident == "B-001" else []
        assert main(["dimensionar", "--tag", ident, *base, *auto, "--saida", str(tag_)]) == rc, ident
        for nome in (f"{ident}.json", f"{ident}_varredura.csv"):
            assert (tag_ / nome).read_bytes() == (planta / nome).read_bytes(), nome
    capsys.readouterr()
    v1 = json.loads((planta / "V-001.json").read_text(encoding="utf-8"))
    assert v1["modo"] == "manual" and v1["status"] == "aguardando_entrada" and v1["ajustes"]["entradas"] == {"q_oil": 250.0}
    to = json.loads((planta / "TO-001.json").read_text(encoding="utf-8"))
    assert to["status"] == "dimensionado" and to["preliminar"] and to["revisoes"]
    assert to["casos"][0]["valores"]["dm_water"]["anterior"] == {"origem": "lacuna", "fonte": "", "valor": None}
    sg = json.loads((planta / "SG-001.json").read_text(encoding="utf-8"))
    tr_w = {c["num"]: c["valores"]["tr_water"] for c in sg["casos"]}
    assert {tr_w[n]["revisao"] for n in (2, 3, *range(8, 17))} == {"confirmada"}
    assert all(tr_w[n]["origem"] == "nao_aplicavel" and not tr_w[n]["revisao"] for n in (1, 4, 5, 6, 7))  # P-42
    b1 = json.loads((planta / "B-001.json").read_text(encoding="utf-8"))
    assert b1["casos"][0]["valores"]["rendimento"]["valor"] == 0.8


def test_estado_dos_outros_tags_nao_altera_o_artefato(arquivo_misto, tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    comum = ["dimensionar", "--tag", "TO-001", "--casos", str(CASOS), "--premissa", "eta_pump=0.8", "--auto-balanco"]
    assert main([*comum, "--ajustes", str(arquivo_misto), "--saida", str(a)]) == 0
    so_to = tmp_path / "so_to.toml"
    aj = A.ler(__import__("tomllib").loads(arquivo_misto.read_text(encoding="utf-8")))
    aj.tags = {"TO-001": aj.tags["TO-001"]}
    aj.avulsos = {}
    saida_ajustes.gravar(aj, servico.Contexto(carregar_casos(CASOS), alteracoes={"eta_pump": 0.8}), so_to)
    assert main([*comum, "--ajustes", str(so_to), "--saida", str(b)]) == 0
    capsys.readouterr()
    assert _bytes(a) == _bytes(b)


def test_avulso_salvo_e_reproduzido(arquivo_misto, tmp_path, capsys):
    assert main(["dimensionar", "--avulso", "ko", "--ajustes", str(arquivo_misto), "--saida", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "Equipamento avulso" in out and "✗ Inviável" in out and "banda 3.0–4.0" in out
    assert main(["dimensionar", "--avulso", "ko2", "--ajustes", str(arquivo_misto), "--saida", str(tmp_path)]) == 0
    assert "✓ Viável" in capsys.readouterr().out
    j = json.loads((tmp_path / "ko2.json").read_text(encoding="utf-8"))
    assert j["avulso"] and j["tag"]["bloco"] == "" and j["premissas"] is None and j["status"] == "dimensionado"
    assert j["envelope"]["entrada"]["origem"] == "exemplo:knockout" and j["envelope"]["resultado"]["x"] == 900


def test_legado_f10b_com_tag_implica_automatico(tmp_path, capsys):
    assert main(["dimensionar", "--tag", "P-001", "--casos", str(CASOS), "--ajustes", str(AJUSTES_LEGADO),
                 "--saida", str(tmp_path)]) == 0
    assert "dimensionado" in capsys.readouterr().out


@pytest.mark.parametrize("args, trecho", [
    (["--tag", "V-001"], "--tag exige --casos"),
    (["--tag", "V-001", "--exemplo", "knockout"], "--exemplo não se combina"),
    (["--auto-balanco", "--exemplo", "knockout"], "--exemplo não se combina"),
    (["--auto-balanco", "--casos", "{casos}"], "--auto-balanco exige --tag"),
    (["--tag", "V-001", "--avulso", "x"], "não os dois"),
    (["--avulso", "x"], "--avulso exige --ajustes"),
    (["--avulso", "x", "--ajustes", "{aj}", "--casos", "{casos}"], "não usa --casos"),
    (["--avulso", "nada", "--ajustes", "{aj}"], "não está em"),
    (["--casos", "{casos}", "--ajustes", "{aj}"], "valem com --tag"),
    (["--equipamento", "pump"], "informe --casos, --exemplo"),
    (["--tag", "XX-9", "--casos", "{casos}", "--auto-balanco"], "TAG desconhecido 'XX-9'"),
    (["--tag", "V-001", "--casos", "{casos}"], "não tem modo salvo; use --auto-balanco"),
    (["--tag", "V-001", "--casos", "{casos}", "--ajustes", "{aj}", "--auto-balanco", "--premissa", "eta_pump=0.8"],
     "salvo em modo manual"),
    (["--tag", "V-001", "--casos", "{casos}", "--auto-balanco", "--equipamento", "pump"], "--equipamento = 'pump'"),
    (["--tag", "V-001", "--casos", "{casos}", "--auto-balanco", "--metodo", "x"], "--metodo = 'x'"),
    (["--tag", "TO-001", "--casos", "{casos}", "--ajustes", "{aj}"], "erro de contexto: premissas alteradas"),
])
def test_erros_de_uso_e_de_contexto(arquivo_misto, capsys, args, trecho):
    subst = {"{casos}": str(CASOS), "{aj}": str(arquivo_misto)}
    assert main(["dimensionar", *[subst.get(a, a) for a in args]]) == 2
    assert trecho in capsys.readouterr().err


def test_pfd_contexto_de_outro_arquivo_de_casos(arquivo_misto, tmp_path, capsys):
    bruto = json.loads(CASOS.read_text(encoding="utf-8"))
    bruto["cases"][0]["T_C"] += 1
    outro = tmp_path / "outro.json"
    outro.write_text(json.dumps(bruto), encoding="utf-8")
    assert main(["pfd", "--casos", str(outro), "--ajustes", str(arquivo_misto), "--premissa", "eta_pump=0.8"]) == 2
    err = capsys.readouterr().err
    assert "erro de contexto" in err and "sha256" in err and not list(tmp_path.glob("*.json"))[1:]


def test_pfd_avisa_versao_diferente_sem_bloquear(arquivo_misto, capsys):
    texto = arquivo_misto.read_text(encoding="utf-8").replace('fpso_siz = "', 'fpso_siz = "velha-')
    arquivo_misto.write_text(texto, encoding="utf-8")
    assert main(["pfd", "--casos", str(CASOS), "--ajustes", str(arquivo_misto), "--premissa", "eta_pump=0.8"]) == 1
    assert "aviso: fpso_siz dos ajustes difere" in capsys.readouterr().err


@pytest.mark.parametrize("comando", [
    ["pfd", "--casos", str(CASOS)],
    ["dimensionar", "--tag", "TO-001", "--casos", str(CASOS), "--auto-balanco"],
    ["dimensionar", "--exemplo", "alves_komesu"],
])
def test_ascii_forcado(comando, capsys):
    main([*comando, "--ascii"])
    out = capsys.readouterr().out
    assert out and all(ord(c) < 128 for c in out)
    assert "->" in out or "Viavel" in out
