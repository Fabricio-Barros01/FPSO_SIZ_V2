"""F11.5 — MC pela CLI (`dimensionar --tag … --mc`, `pfd --mc`) e pelo modo interativo:
o TAG isolado e o lote gravam o mesmo número de documento e os mesmos bytes."""
import json

import pytest
from roteiro import CASOS, RAIZ, abrir_tag, op, repetir_comando, rodar

from fpso_siz.cli import main
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd.tags import tags

DATA = "26/09/2026"


def _arquivos(pasta):
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in sorted(pasta.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def lote(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("lote")
    assert main(["pfd", "--casos", str(CASOS), "--saida", str(pasta), "--mc", "--data", DATA]) == 1
    return pasta


def test_lote_grava_um_mc_por_tag_pelo_numero(lote):
    pastas = sorted(p.name for p in (lote / "mc").iterdir())
    assert pastas == sorted(mc.numero(t.tag)[1] for t in tags())
    for p in (lote / "mc").iterdir():
        assert (p / f"{p.name}.tex").exists() and (p / f"{p.name}.json").exists()


@pytest.mark.parametrize("ident", ["SG-001", "V-001", "B-002"])
def test_tag_isolado_igual_ao_lote(lote, tmp_path, ident):
    assert main(["dimensionar", "--tag", ident, "--casos", str(CASOS), "--auto-balanco", "--saida", str(tmp_path),
                 "--mc", "--data", DATA]) in (0, 1)
    numero = mc.numero(ident)[1]
    assert _arquivos(tmp_path / "mc" / numero) == _arquivos(lote / "mc" / numero)


@pytest.mark.parametrize("args, msg", [
    (["pfd", "--casos", str(CASOS), "--pdf"], "--pdf exige --mc"),
    (["pfd", "--casos", str(CASOS), "--mc"], "--mc exige --saida"),
    (["dimensionar", "--exemplo", "alves_komesu", "--mc", "--saida", "x"], "--mc vale com --tag"),
])
def test_opcoes_do_mc_validadas(capsys, args, msg):
    assert main(args) == 2
    assert msg in capsys.readouterr().err


def test_falha_de_compilacao_devolve_codigo_3(tmp_path, monkeypatch, capsys):
    from fpso_siz.output.latex import compilacao

    def falha(tex):
        raise compilacao.ErroCompilacao("latexmk não encontrado no PATH")
    monkeypatch.setattr(compilacao, "compilar", falha)
    assert main(["dimensionar", "--tag", "V-001", "--casos", str(CASOS), "--auto-balanco", "--saida", str(tmp_path),
                 "--mc", "--pdf"]) == 3
    assert "V-001: latexmk não encontrado" in capsys.readouterr().err


def test_interativo_gera_o_mc_e_o_comando_repete(tmp_path):
    pasta = tmp_path / "v1"
    rc, out, _ = rodar(*abrir_tag("V-001", "automatico"), op("tag", "memorial"), str(pasta), "", "n", "0", "0", "0")
    assert rc == 0
    numero = mc.numero("V-001")[1]
    antes = _arquivos(pasta / "mc" / numero)
    assert f"{numero}.tex" in antes and "--mc" in out
    assert repetir_comando(out) == [0]
    assert _arquivos(pasta / "mc" / numero) == antes


def test_interativo_gera_os_mcs_da_planta(tmp_path, monkeypatch):
    from fpso_siz.output.latex import compilacao
    monkeypatch.setattr(compilacao, "compilar", lambda tex: tex.with_suffix(".pdf"))
    pasta = tmp_path / "planta"
    rc, out, _ = rodar(op("principal", "planta"), op("planta", "memoriais"), str(pasta), "", "s", "0", "0")
    assert rc == 0
    assert len(list((pasta / "mc").iterdir())) == len(tags())
    assert "fpso-siz pfd" in out and "--mc --pdf" in out


def test_interativo_com_propostas_repete_o_comando(tmp_path):
    import io

    from fpso_siz.output.terminal.estilo import Estilo
    from fpso_siz.output.terminal.sessao import Sessao

    ARQ = RAIZ / "src" / "fpso_siz" / "config" / "pfd" / "pendencias_propostas.toml"
    fila = [*abrir_tag("TO-001", "automatico"), op("tag", "exportar"), str(tmp_path / "to"), "", "0", "0", "0"]
    out = io.StringIO()
    s = Sessao(casos=CASOS, entrada=lambda _: fila.pop(0) if fila else (_ for _ in ()).throw(EOFError),
               saida=out, estilo=Estilo(False, True), colunas=100, propostas=ARQ)
    assert s.rodar() == 0
    assert f"--propostas {ARQ}" in out.getvalue()
    assert json.loads((tmp_path / "to" / "TO-001.json").read_text(encoding="utf-8"))["status"] == "dimensionado"
