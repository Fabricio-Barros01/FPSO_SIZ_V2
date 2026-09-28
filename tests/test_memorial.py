"""Memória de cálculo LaTeX do balanço (MC-SEN-SEP-COO-001): conteúdo, bijeção com o rastro,
formatação, CLI e compilação.

O layout é um só (SENAI). A reprodução byte a byte do memorial do script de referência saiu
com a regra de referência do FWKO (docs/arquitetura/inventario.md); o que o memorial mostra
continua preso ao núcleo pela bijeção equação ↔ rastro (invariante 3).
"""
import re
import shutil
import tomllib
from importlib.resources import files
from pathlib import Path

import pytest

from fpso_siz.balanco import indicadores
from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.cli import main
from fpso_siz.core.configuracao import carregar
from fpso_siz.output.latex import compilacao, formatacao
from fpso_siz.output.latex.balanco import memorial

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


@pytest.fixture(scope="module")
def base():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    return dados, prem, resolver_todos(dados, prem)


@pytest.fixture(scope="module")
def tex(base):
    return memorial.gerar(*base)


def test_documento_identificado(tex, base):
    assert "\\pagestyle{memorial}" in tex and base[0].sha256 in tex
    assert "P-42" in tex and "Nota~11" in tex


def test_mostra_a_eficiencia_do_fwko(tex, base):
    """η_req com a substituição do caso 15 (Q_A+D,C03, Q_O,C06, 0,924), a nota de diagnóstico e
    os casos exigidos acima do padrão; a P-43 como premissa do autor."""
    _, _, res = base
    r15 = next(r for r in res if r.num == 15)
    subst = (f"\\frac{{{formatacao.mb(indicadores.q(r15, 'C-06', 'O'))}\\ \\mathrm{{m^3/d}}}}"
             f"{{{formatacao.mb(indicadores.q_agua(r15, 'C-03'))}\\ \\mathrm{{m^3/d}}}}=0{{,}}924")
    assert subst in tex and "\\label{eq:etaF}" in tex and "\\label{eq:bswF}" not in tex
    assert "vazões volumétricas na condição padrão (F-01: 15,6~\\si{\\celsius} e 101,3~\\si{\\kilo\\pascal})" in tex
    assert "\\emph{calor recuperado}" in tex and "\\dot Q_H=\\dot Q_{\\mbox{P-002}}+\\dot Q_{\\mbox{DWH-001}}" in tex
    assert "apenas diagnóstico" in tex and "Nos casos 15, 16, $\\eta_{\\mathrm{req}}>\\eta_{\\mbox{padrão}}$" in tex
    assert "P-43 & Eficiência padrão de remoção de água livre do SG-001" in tex and "Premissa do autor" in tex
    linhas = {x.split(" & ")[0]: x for x in tex.splitlines() if "(BOT 2.7.1.2)" in x or "sem fase aquosa &" in x}
    assert linhas["1"].split(" & ")[2:5] == ["---", "---", "não aplicável — sem fase aquosa"]
    assert linhas["15"].split(" & ")[3:5] == ["0,924", "exigido acima do padrão (BOT 2.7.1.2)"]


# ---------------------------------------------------------------- invariante 3
def test_bijecao_equacoes_memorial(tex):
    rotulos = set(re.findall(r"\\label\{([^}]+)\}", tex))
    catalogo = carregar("equacoes_balanco.toml")
    ancoras = {a for e in catalogo.values() for a in e["memorial"]}
    definicoes = set(tomllib.loads(files("fpso_siz.output.latex.balanco").joinpath("rastro_memorial.toml")
                                   .read_text(encoding="utf-8"))["definicoes"])
    assert ancoras <= rotulos, ancoras - rotulos                      # toda equação do motor aparece
    eqs = {r for r in rotulos if r.startswith("eq:")}
    assert eqs <= ancoras | definicoes, eqs - ancoras - definicoes    # toda equação escrita tem origem
    assert not (definicoes & ancoras) and definicoes <= eqs


def test_criticos_tem_texto_para_cada_indicador(base):
    crit = indicadores.criticos(*[base[2], base[0], base[1]])
    textos = tomllib.loads(files("fpso_siz.output.latex.balanco").joinpath("criticos_memorial.toml")
                           .read_text(encoding="utf-8"))["linhas"]
    assert [t["id"] for t in textos] == [k for k, _, _ in crit]
    assert all(casos for _, _, casos in crit)


# ---------------------------------------------------------------- formatação e CLI
def test_formatacao():
    assert formatacao.br(None) == "--" and formatacao.br(-0.0001, 2) == "0,00" and formatacao.br(1234567.891, 1) == "1.234.567,9"
    assert formatacao.sci(0) == "$0$" and formatacao.sci(-2.5e-11) == "$-2{,}5\\times10^{-11}$"
    assert [formatacao.mbn(x, d) for x, d in [(0.01, 2), (0.015, 2), (2.0, 1), (1.0, 0), (1234.5, 0)]] == \
        ["0{,}01", "0{,}015", "2{,}0", "1", "1.234{,}5"]
    assert formatacao.esc("a_b&c%#") == "a\\_b\\&c\\%\\#" and formatacao.ids([1, 2]) == "1, 2"


def test_cli_memorial(tmp_path, base):
    assert main(["memorial", "--casos", str(CASOS), "--saida", str(tmp_path / "s")]) == 0
    assert (tmp_path / "s" / "main.tex").read_text(encoding="utf-8") == memorial.gerar(*base)
    assert (tmp_path / "s" / "logo-senai.png").stat().st_size > 0


def test_cli_memorial_pdf_sem_latexmk(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert main(["memorial", "--casos", str(CASOS), "--saida", str(tmp_path), "--pdf"]) == 3
    assert "latexmk não encontrado" in capsys.readouterr().err


def test_compilacao_falha_reporta_log(tmp_path, monkeypatch):
    class R:
        returncode, stdout = 1, "linha\n! erro fatal"
    monkeypatch.setattr(shutil, "which", lambda _: "/bin/latexmk")
    monkeypatch.setattr(compilacao.subprocess, "run", lambda *a, **k: R())
    (tmp_path / "main.tex").write_text("x", encoding="utf-8")
    with pytest.raises(compilacao.ErroCompilacao, match="erro fatal"):
        compilacao.compilar(tmp_path / "main.tex")
    (tmp_path / "main.log").write_text("log\n! Undefined control sequence", encoding="utf-8")
    with pytest.raises(compilacao.ErroCompilacao, match="Undefined"):
        compilacao.compilar(tmp_path / "main.tex")


# ---------------------------------------------------------------- compilação real (lenta)
@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel(), reason="latexmk ausente")
def test_compila_em_pdf(base, tmp_path):
    pdf = compilacao.compilar(memorial.gravar(*base, tmp_path))
    log = pdf.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    assert pdf.stat().st_size > 100_000
    assert not re.search(r"^! ", log, re.M) and "undefined" not in log.lower()
