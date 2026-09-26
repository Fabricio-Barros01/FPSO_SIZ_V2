"""F11 — memorial de cálculo (MC) por TAG: numeração, conteúdo do núcleo, determinismo,
exportação dos CSV e igualdade PDF × JSON (compilação com `-m latex`)."""
import json
import math
import re
import shutil
import subprocess
from dataclasses import asdict

import pytest

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.trace import Rastro, TraceEntry
from fpso_siz.output.latex import compilacao, formatacao
from fpso_siz.output.latex.tag import memorial as saida_mc
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd.tags import tags

DATA = "26/09/2026"
GIT = ("0123456789ab", False)   # proveniência fixada: os bytes não dependem do checkout


def test_numeracao_cobre_os_11_tags_sem_repeticao():
    tab = carregar("memorial_tag.toml")["numeracao"]
    assert set(tab) == {t.tag for t in tags()}
    assert sorted(tab.values()) == list(range(1, len(tab) + 1))
    assert [k for k, _ in sorted(tab.items(), key=lambda kv: kv[1])][:3] == ["SG-001", "P-001", "P-002"]
    assert mc.numero("V-001") == (4, "MC-SEN-SEP-EQP-004-0")
    assert mc.numero("nao-e-tag") == (None, None)


def test_rastro_documental_nao_muda_a_projecao():
    """Os operandos ficam fora de `entries`: a projeção (JSON, fixtures do Julia) é a mesma."""
    tr = Rastro()
    tr.anotar("gas", "V_t", coef=1.0)
    tr.iteracoes["gas"] = [{"i": 1}]
    tr.trace("gas", "Eq.", "V_t", "f", 2.0, "m/s")
    assert [asdict(e) for e in tr] == [asdict(TraceEntry("gas", "Eq.", "V_t", "f", 2.0, "m/s"))]
    assert tr.operandos[("gas", "V_t")] == {"coef": 1.0}


@pytest.fixture(scope="module")
def docs(planta_base):
    ctx = planta_base.contexto
    return {t.tag.tag: (t, mc.documento(ctx, t)) for t in planta_base.tags}


def test_documento_de_cada_tag_tem_as_secoes(docs):
    for tag, (rt, d) in docs.items():
        assert d["identificacao"]["numero"] == mc.numero(tag)[1]
        assert d["identificacao"]["status"] == rt.status
        assert d["conteudo"]["objetivo"] and d["conteudo"]["referencias"]
        assert [c["num"] for c in d["casos"]] == list(range(1, 17))
        assert (d["calculo"] is None) == (rt.resultado is None)


def test_lacunas_do_mc_batem_com_as_do_pfd(docs):
    for rt, d in docs.values():
        assert [(l["chave"], tuple(l["casos"])) for l in d["lacunas"]] == \
            [(l.chave, l.casos) for l in rt.entradas.lacunas]
        assert all(l["origem_esperada"] for l in d["lacunas"])


def test_regra_do_fwko_e_p43_no_mc(docs):
    _, d = docs["V-001"]
    assert d["identificacao"]["regra_fwko"] == "eficiencia"
    assert "P-43" in [p["id"] for p in d["premissas"]]
    _, sg = docs["SG-001"]
    assert "P-42" in [p["id"] for p in sg["premissas"]]


def test_tex_deterministico_e_sem_numero_de_dado_digitado(planta_base, tmp_path):
    ctx = planta_base.contexto
    rt = planta_base.tag("V-001")
    a = saida_mc.gravar(ctx, rt, tmp_path / "a", data=DATA, git=GIT)
    b = saida_mc.gravar(ctx, rt, tmp_path / "b", data=DATA, git=GIT)
    assert a.read_bytes() == b.read_bytes()
    for arq in (tmp_path / "a").glob("*.csv"):
        assert arq.read_bytes() == (tmp_path / "b" / arq.name).read_bytes()
    tex = a.read_text(encoding="utf-8")
    # os gráficos leem CSV: o d escolhido não aparece em nenhum \addplot
    assert all(".csv}" in li for li in tex.splitlines() if li.startswith(r"\addplot") and "fill between" not in li)
    assert "MC-SEN-SEP-EQP-004-0_diagrama.csv" in tex


def test_csv_do_diagrama_contem_o_ponto_escolhido(planta_base, tmp_path):
    rt = planta_base.tag("V-001")
    saida_mc.gravar(planta_base.contexto, rt, tmp_path, data=DATA, git=GIT)
    linhas = (tmp_path / "MC-SEN-SEP-EQP-004-0_diagrama.csv").read_text(encoding="utf-8").splitlines()
    cab = linhas[0].split(",")
    assert cab[:2] == ["x", "y"] and "banda_min" in cab and "cap_gas" in cab
    ponto = (tmp_path / "MC-SEN-SEP-EQP-004-0_ponto.csv").read_text(encoding="utf-8").splitlines()[1]
    assert ponto == f"{rt.resultado.x!r},{rt.resultado.y!r}"


def test_formatacao_4_algarismos():
    assert formatacao.sig(4700.0) == "4.700"
    assert formatacao.sig(11.743162292078477) == "11{,}74"
    assert formatacao.sig(259406455.03) == r"2{,}594\times10^{8}"
    assert formatacao.sig(9999.6) == r"1{,}000\times10^{4}"
    assert formatacao.sig(math.nan) == r"\text{--}" and formatacao.sig(0.0) == "0"
    assert formatacao.texto_sig(0.0036) == "3,600×10-3"
    assert formatacao.tx("a^b_c {x} 5%") == r"a\^{}b\_c \{x\} 5\%"
    assert formatacao.unid("kg/m^3") == "kg/m³" and formatacao.unid("–") == ""


def test_substituicao_nao_inventa_operando():
    assert saida_mc.substituir(r"@a@\cdot @k:c@", {"a": 2.0}, {"a": "m"}, {"c": 0.5}) == r"2{,}000\,\text{m}\cdot 0{,}5"
    with pytest.raises(KeyError):
        saida_mc.substituir("@falta@", {})


# ------------------------------------------------------------------ compilação (lento)
def _texto_pdf(pdf):
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def _normal(s):
    return re.sub(r"\s+", "", s).replace("−", "-")


@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel() or not shutil.which("pdftotext"), reason="latexmk/pdftotext ausentes")
@pytest.mark.parametrize("ident", [t.tag for t in tags()])
def test_pdf_compila_e_iguala_o_json(planta_base, tmp_path, ident):
    """PDF × JSON: o cartão de resultados e o teto exportados no JSON do TAG aparecem no
    PDF com a regra de 4 algarismos; as lacunas aparecem pela chave."""
    from fpso_siz.output.pfd import estrutura_tag

    ctx, rt = planta_base.contexto, planta_base.tag(ident)
    pdf = compilacao.compilar(saida_mc.gravar(ctx, rt, tmp_path, data=DATA, git=GIT))
    texto = _normal(_texto_pdf(pdf))
    js = estrutura_tag(ctx, rt)
    doc = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    assert doc["identificacao"]["numero"] in texto
    if js["envelope"] is not None:
        for campo in js["envelope"]["resultado"]["cartao"]:
            if isinstance(campo["valor"], float):
                assert _normal(formatacao.texto_sig(campo["valor"])) in texto, campo
    for lac in js["lacunas"]:
        assert _normal(lac["chave"]) in texto
