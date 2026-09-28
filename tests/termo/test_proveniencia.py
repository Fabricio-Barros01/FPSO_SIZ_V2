"""Contrato único de proveniência (config/termo/proveniencia.toml, termo/proveniencia.py).

`validade` e `origem` são independentes; `consumidores` diz quem usa o valor hoje. Estes testes
provam que o contrato descreve o código — e não o contrário —, e fixam a correção de semântica
da consolidação: uma propriedade nunca aparece como vinda do flash só porque é "validada"; o
que o cálculo consumiu é o que a proveniência diz.
"""
import pytest

from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd.entradas import REGRAS, especificacoes
from fpso_siz.pfd.tags import tags
from fpso_siz.termo import proveniencia as pv
from fpso_siz.termo import servico as termo


def test_o_contrato_e_valido():
    assert pv.conferir() == []


def test_nada_nao_validado_e_consumido():
    for i, d in pv.declaracoes().items():
        if d["validade"] != pv.VALIDADA:
            assert d["consumidores"] == [], i


def test_toda_regra_de_propriedade_esta_no_contrato():
    de_propriedade = {r for r in REGRAS if r.startswith(("densidade", "viscosidade", "compressibilidade",
                                                          "condutividade", "cp_utilidade", "pressao_vapor"))}
    declaradas = {d["regra"] for d in pv.declaracoes().values() if "regra" in d}
    assert declaradas == de_propriedade and declaradas <= set(REGRAS)


def test_funcoes_e_fontes_existem():
    for i, d in pv.declaracoes().items():
        if "funcao" in d:
            assert callable(getattr(termo, d["funcao"], None)), i
        for chave in d.get("fonte", []):
            secao, campo = chave.split(".")
            assert termo.cfg()[secao][campo].strip(), (i, chave)


def test_unidade_do_contrato_e_a_do_metodo_que_consome():
    desc = {d["regra"]: d for d in pv.declaracoes().values() if "regra" in d}
    for t in tags():
        _, _, specs = especificacoes(t)
        for chave, regra in t.entradas.items():
            d = desc.get(regra["regra"])
            if d is not None:
                assert specs[chave].unit == d["unidade"], (t.tag, chave)


def test_nenhuma_propriedade_consumida_vem_do_flash():
    """A correção da F5: o flash do trem é diagnóstico. Nada que o balanço, o dimensionamento ou a
    otimização consome é atribuído a ele."""
    for i, d in pv.declaracoes().items():
        if d["consumidores"]:
            assert d.get("funcao") not in ("flash_tp", "mw_mistura"), i


@pytest.fixture(scope="module")
def estados(planta_base):
    dados = planta_base.dados
    return resolver_todos(dados, premissas(dados))


def test_o_estado_declara_o_que_o_balanco_consumiu(estados):
    for r in estados:
        assert r.proveniencia == pv.consumidas("balanco")


def test_cada_propriedade_do_balanco_esta_no_rastro(estados):
    """Declarar no contrato não basta: a equação que produz a propriedade tem de estar no rastro de
    todo caso — senão a proveniência descreveria um cálculo que não aconteceu."""
    for i, d in pv.consumidas("balanco").items():
        eq = pv.de(i).get("rastro")
        assert eq, i
        for r in estados:
            assert eq in {equacao for equacao, _ in r.trace.pares()}, (i, r.num)


def test_entrada_de_tag_carrega_a_propriedade(planta_propostas):
    """Toda entrada de TAG que sai de uma regra de propriedade aponta para o contrato, e o
    contrato a declara consumida pelo dimensionamento."""
    consumidas = pv.consumidas("dimensionamento")
    vistas = set()
    for rt in planta_propostas.tags:
        for c in rt.entradas.casos:
            for chave, v in c.valores.items():
                regra = rt.tag.entradas.get(chave, {}).get("regra")
                if regra and pv.da_regra(regra) and not v.lacuna:
                    assert v.propriedade == pv.da_regra(regra) and v.propriedade in consumidas
                    vistas.add(v.propriedade)
    assert {"densidade_gas", "viscosidade_fase", "cp_utilidade"} <= vistas


def test_consultas_recusam_o_que_nao_existe():
    with pytest.raises(ValueError, match="fora do contrato"):
        pv.de("inexistente")
    assert pv.da_regra("temperatura") is None
