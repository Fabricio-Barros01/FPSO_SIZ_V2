"""Contrato único de proveniência (config/termo/proveniencia.toml, termo/proveniencia.py).

`validade` e `origem` são independentes; `consumidores` diz quem usa o valor hoje. Estes testes
provam que o contrato descreve o código — e não o contrário —, e fixam a correção de semântica
da consolidação: uma propriedade nunca aparece como vinda do flash só porque é "validada"; o
que o cálculo consumiu é o que a proveniência diz — e, com o trem produtivo, o que a CLASSE do
caso consumiu (avaliável: flash; não avaliável: Standing).
"""
import pytest

from fpso_siz.balanco.dados import premissas
from fpso_siz.core.configuracao import carregar
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd.entradas import REGRAS, especificacoes
from fpso_siz.pfd.tags import tags
from fpso_siz.termo import proveniencia as pv
from fpso_siz.termo import servico as termo

CATALOGO = carregar("equacoes_balanco.toml")


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
    alternativas = {d["regra_alternativa"] for d in pv.declaracoes().values() if "regra_alternativa" in d}
    assert declaradas == de_propriedade and declaradas <= set(REGRAS) and alternativas <= declaradas


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


def test_o_flash_so_e_consumido_nos_casos_avaliaveis():
    """O trem é produtivo só nos casos avaliáveis (recombinação da Nota 4): o que vem do flash e é
    consumido está validado e restrito a eles; Standing, restrito aos não avaliáveis. Nada do
    flash sem composição do caso (ρ líquida, h, cp, transporte) tem consumidor."""
    for i, d in pv.declaracoes().items():
        if d.get("funcao") == "flash_tp" and d["consumidores"]:
            assert d["validade"] == pv.VALIDADA and d.get("casos") == pv.AVALIAVEIS, i
    assert pv.de("gas_liberado_por_estagio")["casos"] == pv.NAO_AVALIAVEIS
    for i in ("rho_liquido_flash", "entalpia_fluido_de_poco", "transporte_fluido_de_poco"):
        assert pv.de(i)["consumidores"] == [], i


def test_classe_de_caso_desconhecida_e_erro(monkeypatch):
    base = pv.cfg()
    falso = {**base, "propriedade": [*base["propriedade"], dict(id="x", origem=[], validade="validada",
                                                                  consumidores=[], casos="alguns")]}
    monkeypatch.setattr(pv, "cfg", lambda: falso)
    assert any("classe de caso" in e for e in pv.conferir())


@pytest.fixture(scope="module")
def estados(planta_base):
    dados = planta_base.dados
    return resolver_todos(dados, premissas(dados))


def test_o_estado_declara_o_que_o_balanco_consumiu(estados):
    for r in estados:
        assert r.proveniencia == pv.consumidas("balanco", avaliavel=r.avaliavel)
    assert {r.avaliavel for r in estados} == {True, False}


def test_cada_propriedade_do_balanco_esta_no_rastro(estados):
    """Declarar no contrato não basta: a equação que produz a propriedade tem de estar no rastro de
    todo caso da classe que a consome — senão a proveniência descreveria um cálculo que não
    aconteceu. E o rastro de uma classe não tem a equação da outra."""
    for r in estados:
        eqs = {equacao for equacao, _ in r.trace.pares()}
        for i in pv.consumidas("balanco", avaliavel=r.avaliavel):
            eq = pv.de(i).get("rastro")
            assert eq and eq in eqs, (i, r.num)
        # equação restrita à outra classe no catálogo não pode aparecer no rastro deste caso
        for i in set(pv.consumidas("balanco")) - set(pv.consumidas("balanco", avaliavel=r.avaliavel)):
            eq = pv.de(i)["rastro"]
            if "casos" in CATALOGO[eq]:
                assert eq not in eqs, (i, r.num)


def test_entrada_de_tag_carrega_a_propriedade(planta_propostas):
    """Toda entrada de TAG que sai de uma regra de propriedade aponta para o contrato, e o
    contrato a declara consumida pelo dimensionamento."""
    consumidas = pv.consumidas("dimensionamento")
    alternativa = {d["regra_alternativa"]: i for i, d in pv.declaracoes().items() if "regra_alternativa" in d}
    avaliavel = {r.num: r.avaliavel for r in planta_propostas.balanco}
    vistas = set()
    for rt in planta_propostas.tags:
        for c in rt.entradas.casos:
            for chave, v in c.valores.items():
                regra = rt.tag.entradas.get(chave, {}).get("regra")
                if regra and pv.da_regra(regra) and not v.lacuna:
                    esperada = alternativa.get(regra) if avaliavel[c.num] and regra in alternativa else pv.da_regra(regra)
                    assert v.propriedade == esperada and v.propriedade in consumidas, (rt.tag.tag, c.num, chave)
                    assert pv.aplica(pv.de(v.propriedade), avaliavel[c.num])
                    vistas.add(v.propriedade)
    assert {"densidade_gas", "rho_vapor_estagio", "Z_vapor_estagio", "viscosidade_fase", "cp_utilidade"} <= vistas


def test_consultas_recusam_o_que_nao_existe():
    with pytest.raises(ValueError, match="fora do contrato"):
        pv.de("inexistente")
    assert pv.da_regra("temperatura") is None
