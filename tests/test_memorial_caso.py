"""F11b — memorial do balanço por caso (MC_Caso01 … MC_Caso16) nos dois layouts: seleção
dos casos, folha de rosto, P-42 ("—" sem fase aquosa), isolado × lote e compilação."""
import shutil
import subprocess

import pytest
from roteiro import CASOS, op, repetir_comando, rodar

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import REFERENCIA, resolver_todos
from fpso_siz.cli import main
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.caso import memorial as mc

DATA = "26/09/2026"
GIT = ("0123456789ab", False)
SEM_AGUA = [1, 4, 5, 6, 7]


@pytest.fixture(scope="module")
def base():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    return dados, prem, resolver_todos(dados, prem)


def test_selecao_de_casos():
    nums = list(range(1, 17))
    assert mc.selecionar("todos", nums) == nums
    assert mc.selecionar("3", nums) == [3] and mc.selecionar("1,4-7", nums) == [1, 4, 5, 6, 7]
    for ruim in ("0", "17", "a", "2-x"):
        with pytest.raises(ValueError):
            mc.selecionar(ruim, nums)


def test_nome_e_numero_por_caso():
    assert [mc.nome_arquivo(n) for n in (1, 16)] == ["MC_Caso01", "MC_Caso16"]


@pytest.mark.parametrize("layout", mc.LAYOUTS)
def test_folha_de_rosto_e_fase_aquosa(base, layout):
    dados, prem, R = base
    for num in (1, 2):
        tex = mc.gerar(dados, prem, R, num, layout, DATA, GIT)
        assert "commit \\texttt{0123456789ab}" in tex and DATA in tex and "P-43, F10w" in tex
        assert "Premissas diferentes do padrão & nenhuma" in tex
        linha = next(li for li in tex.splitlines() if li.startswith("C-03 &"))
        assert ("---" in linha) == (num in SEM_AGUA)
    assert r"\eta_{A,\mbox{SG-001}}$ & ---" in mc.gerar(dados, prem, R, 4, layout, DATA, GIT)


def test_regra_de_referencia_e_premissa_alterada_na_folha_de_rosto(base):
    dados, _, _ = base
    prem = premissas(dados, eta_F=0.8)
    tex = mc.gerar(dados, prem, resolver_todos(dados, prem, REFERENCIA), 2, "senai", DATA, GIT)
    assert "modo de paridade" in tex and "P-43 \\texttt{eta\\_F} = 0{,}8" in tex


def test_isolado_igual_ao_lote(base, tmp_path):
    dados, prem, R = base
    nums = [r.num for r in R]
    mc.exportar_lote(dados, prem, R, nums, tmp_path / "lote", mc.LAYOUTS, DATA, GIT)
    for num in nums:
        mc.exportar_lote(dados, prem, R, [num], tmp_path / "um", mc.LAYOUTS, DATA, GIT)
        for lay in mc.LAYOUTS:
            nome = f"{lay}/{mc.nome_arquivo(num)}/{mc.nome_arquivo(num)}.tex"
            assert (tmp_path / "um" / nome).read_bytes() == (tmp_path / "lote" / nome).read_bytes()
    assert len(list((tmp_path / "lote").rglob("MC_Caso*.tex"))) == 2 * len(nums)


def test_cli_por_caso(tmp_path, monkeypatch, capsys):
    assert main(["memorial", "--casos", str(CASOS), "--caso", "3", "--layout", "senai", "--saida", str(tmp_path),
                 "--data", DATA]) == 0
    assert (tmp_path / "MC_Caso03" / "MC_Caso03.tex").exists() and (tmp_path / "MC_Caso03" / "logo-senai.png").exists()
    assert main(["memorial", "--casos", str(CASOS), "--layout", "ambos", "--saida", str(tmp_path)]) == 2
    assert "--layout ambos vale com --caso" in capsys.readouterr().err
    # `memorial --casos todos`: o arquivo padrão da pasta corrente, os dois layouts
    monkeypatch.chdir(tmp_path)
    shutil.copy(CASOS, tmp_path / "design_cases_bot.json")
    assert main(["memorial", "--casos", "todos", "--data", DATA]) == 0
    assert len(list((tmp_path / "saida" / "memorial").rglob("MC_Caso*.tex"))) == 32


def test_interativo_itera_os_casos_e_o_comando_repete(tmp_path):
    pasta = tmp_path / "mem"
    rc, out, _ = rodar(op("principal", "balanco"), op("balanco", "memorial_caso"), "1,2", "ambos", str(pasta), "n",
                       "0", "0")
    assert rc == 0
    antes = {p: p.read_bytes() for p in pasta.rglob("*.tex")}
    assert len(antes) == 4
    assert repetir_comando(out) == [0]
    assert {p: p.read_bytes() for p in pasta.rglob("*.tex")} == antes


def _texto(pdf):
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel() or not shutil.which("pdftotext"), reason="latexmk/pdftotext ausentes")
def test_os_16_pdfs_compilam_nos_dois_layouts(base, tmp_path):
    dados, prem, R = base
    nums = [r.num for r in R]
    arquivos, erros = mc.exportar_lote(dados, prem, R, nums, tmp_path / "lote", mc.LAYOUTS, DATA, GIT, pdf=True)
    assert erros == [] and len([a for a in arquivos if a.suffix == ".pdf"]) == 32
    # isolado × lote no PDF, ignorando a data de criação: o texto extraído é o mesmo
    um, _ = mc.exportar_lote(dados, prem, R, [2], tmp_path / "um", ("senai",), DATA, GIT, pdf=True)
    assert _texto(um[-1]) == _texto(tmp_path / "lote" / "senai" / "MC_Caso02" / "MC_Caso02.pdf")
