"""F10x.7 — reotimização discreta dos trocadores (pfd/reotimizacao.py) e o que continua
governando no P-002 e no P-003 (docs/validacao/18-trocadores.md)."""
import re
from pathlib import Path

import pytest

from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd import reotimizacao as ro
from fpso_siz.pfd.tags import tag

DOC = Path(__file__).resolve().parents[2] / "docs" / "validacao" / "18-trocadores.md"


def _escolhido_no_doc(ident):
    secao = DOC.read_text(encoding="utf-8").split(f"## {ident}")[1]
    linha = next(li for li in secao.splitlines() if li.startswith("**Escolhido**"))
    return {k: float(v) for k, v in re.findall(r"`(\w+)` = (\d+(?:\.\d+)?)", linha)}


@pytest.mark.parametrize("ident", ["P-002", "P-003"])
def test_recomendacoes_do_tag_sao_as_do_relatorio(ident):
    """O TAG carrega, como recomendação com fonte, o candidato escolhido pela ferramenta."""
    rec = {k: v["valor"] for k, v in tag(ident).recomendadas.items()}
    for chave, valor in _escolhido_no_doc(ident).items():
        if valor == 1.0 and chave.startswith("cascos_"):
            assert rec.get(chave, 1.0) == 1.0
        else:
            assert rec[chave] == valor, chave


def test_grade_vem_da_fonte_de_cada_descritor():
    for chave, g in ro.cfg()["grade"].items():
        assert g["valores"] and g["fonte"].strip(), chave
    assert len(ro.grade("P-002")) == 96


def test_busca_reduzida_do_p002_divide_em_serie_pelo_comprimento(planta_propostas):
    """Com a grade reduzida ao candidato escolhido: um casco é barrado pelo comprimento; com
    dois em série o comprimento cabe em 6 m e sobra só Dittus-Boelter no turndown (BOT 06)."""
    esc = _escolhido_no_doc("P-002")
    grade = {k: [v] for k, v in esc.items() if k in ro.cfg()["grade"]}
    etapas = ro.buscar(planta_propostas.contexto, "P-002", grade)
    assert [e.cascos for e in etapas] == [1, 2]
    um, dois = etapas[0].melhor, etapas[1].melhor
    assert "comprimento" in {c for c, _ in um.bloqueios}
    nomes = [n for n, _ in dois.rt.entradas.case_set().expand()]
    assert [(c, nomes[i][:6]) for c, i in dois.bloqueios] == [("dittus_boelter", "BOT 06")]
    assert dois.y <= 6.0 and ro.escolhido(etapas) is dois


def test_mc_do_p002_mostra_o_feixe_mais_proximo(planta_propostas):
    rt = planta_propostas.tag("P-002")
    assert rt.status == "inviavel"
    s = mc.documento(planta_propostas.contexto, rt)["calculo"]["series"]
    fp = s["feixe_proximo"]
    assert [b["caso"][:6] for b in fp["bloqueios"]] == ["BOT 06"] and fp["l"] <= 6.0
    assert s["v2"]["cascos_serie"] == 2.0
    papel = {o["caso"][:6]: o for o in s["operacao"]}
    assert not papel["BOT 06"]["nu_valido"] and papel["BOT 06"]["papel"] == "turndown"
    assert all(o["nu_valido"] for k, o in papel.items() if k != "BOT 06")


def test_p003_casco_dentro_do_limite_logo_sem_paralelo(planta_propostas):
    """O casco do melhor feixe fica abaixo de 2.500 mm: a divisão em paralelo não é acionada; o
    que governa é Dittus-Boelter nos casos de baixa carga (e o comprimento)."""
    rt = planta_propostas.tag("P-003")
    s = mc.documento(planta_propostas.contexto, rt)["calculo"]["series"]
    fp = s["feixe_proximo"]
    rot = mc.cfg()["bloqueios"]
    assert fp["d_shell"] <= 2500.0 and rot["casco"] not in [b["criterio"] for b in fp["bloqueios"]]
    fora = sorted(b["caso"][:6] for b in fp["bloqueios"] if b["criterio"] == rot["dittus_boelter"])
    assert fora == ["BOT 04", "BOT 05", "BOT 06"]
    assert tag("P-003").recomendadas.get("cascos_paralelo") is None
