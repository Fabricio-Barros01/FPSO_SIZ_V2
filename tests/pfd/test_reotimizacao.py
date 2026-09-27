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


def test_busca_reduzida_do_p002_para_em_um_casco(planta_propostas):
    """Com a grade reduzida ao candidato escolhido, a busca PARA no primeiro estágio: um casco já é
    viável, então o gatilho de divisão em série não é acionado. Era o comprimento que acionava a
    divisão, e ele deixou de bloquear quando a película do lado tubo passou a ter os três regimes e
    a reotimização pôde escolher o tubo de 12,7 mm."""
    esc = _escolhido_no_doc("P-002")
    grade = {k: [v] for k, v in esc.items() if k in ro.cfg()["grade"]}
    etapas = ro.buscar(planta_propostas.contexto, "P-002", grade)
    assert [e.cascos for e in etapas] == [1]
    um = etapas[0].melhor
    assert um.viavel and um.bloqueios == () and um.y <= 6.0
    assert ro.escolhido(etapas) is um


def test_mc_do_p002_dimensionado_mostra_a_operacao_de_todos_os_casos(planta_propostas):
    """O P-002 ficou VIÁVEL quando a película do lado tubo passou a ter os três regimes: não há
    mais feixe mais próximo a exibir, e todos os casos — inclusive o BOT 06, no laminar (Re ≈
    1.416) — entram na tabela de operação com a correlação válida, num casco só."""
    rt = planta_propostas.tag("P-002")
    assert rt.status == "dimensionado"
    s = mc.documento(planta_propostas.contexto, rt)["calculo"]["series"]
    assert not s.get("feixe_proximo")
    assert s["v2"]["cascos_serie"] == 1.0 and s["v2"]["cascos_paralelo"] == 1.0
    papel = {o["caso"][:6]: o for o in s["operacao"]}
    assert all(o["nu_valido"] for o in papel.values())
    assert papel["BOT 06"]["papel"] == "turndown" and papel["BOT 06"]["regime"] == "laminar"


def test_p003_dimensionado_com_um_casco_dentro_dos_limites(planta_propostas):
    """O P-003 também fechou: com a película nos três regimes e o tubo de 12,7 mm, o melhor feixe
    cabe em 6 m com o casco abaixo de 2.500 mm, então nem a divisão em paralelo nem a em série são
    acionadas — e a premissa original (série só no P-002) não precisou ser estendida."""
    rt = planta_propostas.tag("P-003")
    assert rt.status == "dimensionado"
    s = mc.documento(planta_propostas.contexto, rt)["calculo"]["series"]
    assert not s.get("feixe_proximo")
    assert all(o["nu_valido"] for o in s["operacao"])
    assert rt.resultado.y <= 6.0 and rt.resultado.derivados["d_shell"] <= 2500.0
    assert tag("P-003").recomendadas.get("cascos_paralelo") is None
    assert tag("P-003").recomendadas.get("cascos_serie") is None
