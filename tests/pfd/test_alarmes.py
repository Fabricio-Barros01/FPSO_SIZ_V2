"""Alarmes de inviabilidade (config/pfd/alarmes.toml, pfd/investigacao.py).

A unidade do BOT é um projeto básico real: TAG inviável é alarme (premissa, numérico ou modelo)
e tem de estar anotado. As variantes de estudo rodam pelo mesmo serviço, só por ferramenta
(`tools/investigar_alarmes.py`) e nos testes — nunca dentro do memorial — e não mudam o
resultado padrão."""
import pytest

from fpso_siz.pfd import investigacao as inv
from fpso_siz.pfd import memorial as mc


@pytest.mark.parametrize("planta", ["planta_base", "planta_propostas"])
def test_todo_tag_inviavel_tem_alarme_anotado(request, planta):
    p = request.getfixturevalue(planta)
    for rt, ev, reg in inv.alarmes(p):
        assert reg is not None, f"{rt.tag.tag} inviável sem investigação anotada em alarmes.toml"
        assert reg["hipoteses"] and ev.mensagem
        assert {h["classe"] for h in reg["hipoteses"]} <= set(inv.cfg()["classes"])


def test_variantes_tem_origem_e_existem():
    for a in inv.cfg()["alarme"]:
        for h in a["hipoteses"]:
            for nome in h.get("variantes", []):
                assert inv.variante(nome)["origem"].strip()


def test_p001_dimensionado_e_alarme_fechado(planta_propostas):
    """O P-001 é dimensionado pela regra da ADR 0005 — DESIGN no caso de projeto, RATING nos
    demais, a diferença para a carga do balanço compensada pelas utilidades —, e o registro do
    alarme diz isso, sem variante de estudo pendurada."""
    from fpso_siz.pfd import equipamento as servico

    assert planta_propostas.tag("P-001").status == servico.DIMENSIONADO
    reg = inv.registro("P-001")
    assert reg["estado"].startswith("fechada") and "ADR 0005" in reg["resumo"]
    assert all(not h.get("variantes") for h in reg["hipoteses"])


# ------------------------------------------------------------------ P-44 (F10x.6)
def test_p44_resolve_as_bombas(planta_propostas):
    """Com a P-44 as três bombas têm linha: DN pelo caso de maior vazão, com a banda nele; os
    demais casos abaixo do teto. Sem ela (variante sem_p44), o alarme anterior volta."""
    ctx = planta_propostas.contexto
    esperado = {"B-001": 600.0, "B-002": 250.0, "B-003": 125.0}
    for ident, dn in esperado.items():
        rt = planta_propostas.tag(ident)
        assert rt.status == "dimensionado" and rt.resultado.x == dn
        op = mc.documento(ctx, rt)["calculo"]["series"]["operacao"]
        projeto = [o for o in op if o["papel"] == "projeto"]
        assert len(projeto) == 1 and projeto[0]["q"] == max(o["q"] for o in op)
        casos = rt.entradas.casos
        v_min = next(c.valores["v_min"].valor for c in casos if c.ativo)
        assert v_min <= projeto[0]["v"] <= next(c.valores["v_max"].valor for c in casos if c.ativo)
        assert all(o["v"] <= projeto[0]["v"] for o in op)
        assert inv.executar_variante(ctx, ident, inv.variante("sem_p44")).status == "inviavel"
        assert inv.registro(ident)["estado"] == "explicada"


def test_p44_piso_nulo_so_no_oleo_limpo(planta_propostas):
    for ident, v_min in (("B-001", 0.0), ("B-002", 1.0), ("B-003", 1.0)):
        c = next(c for c in planta_propostas.tag(ident).entradas.casos if c.ativo)
        assert c.valores["v_min"].valor == v_min
        assert c.valores["piso_caso_projeto"].valor == 1.0 and c.valores["transicao_turndown"].valor == 1.0
        assert all("P-44" in c.valores[k].fonte for k in ("piso_caso_projeto", "transicao_turndown"))
    c = next(c for c in planta_propostas.tag("B-001").entradas.casos if c.ativo)
    assert c.valores["v_min"].origem == "recomendada" and "P-44" in c.valores["v_min"].fonte


def test_p44b_so_no_caso_6_do_b001(planta_propostas):
    """A política de transição (P-44b) só entra no turndown mais profundo (caso 6, ~4 % da vazão de projeto)."""
    op = mc.documento(planta_propostas.contexto, planta_propostas.tag("B-001"))["calculo"]["series"]["operacao"]
    assert [o["caso"][:6] for o in op if o["politica_transicao"]] == ["BOT 06"]
    assert all(not o["politica_transicao"] for o in op if o["papel"] == "projeto")


def test_a_planta_produtiva_nao_tem_alarme_aberto(planta_propostas):
    """Nenhum TAG da planta produtiva fica inviável: não há seção de alarme em MC nenhum."""
    ctx = planta_propostas.contexto
    assert list(inv.alarmes(planta_propostas)) == []
    for rt in planta_propostas.tags:
        assert mc.documento(ctx, rt)["alarme"] is None, rt.tag.tag


def test_alarme_no_memorial_e_registro_sem_execucao(planta_propostas):
    """A mecânica do alarme continua exercitada: num TAG forçado a inviável (B-001 com a banda
    de velocidade em todos os casos, o estado anterior à P-44), o MC traz o alarme como está
    REGISTRADO, com as variantes identificadas por rótulo e origem e NENHUM resultado de
    variante — o memorial não recalcula engenharia."""
    from fpso_siz.pfd import equipamento as servico

    ctx = planta_propostas.contexto
    est = servico.estado_inicial("B-001")
    for chave, valor in inv.variante("sem_p44")["geral"].items():
        est.editar(chave, float(valor))
    rt = servico.dimensionar(servico.preparar(ctx, est), est)
    assert rt.status == servico.INVIAVEL
    a = mc.documento(ctx, rt)["alarme"]
    assert a["registrado"] and a["estado"] == inv.registro("B-001")["estado"]
    variantes = [v for h in a["hipoteses"] for v in h["variantes"]]
    assert {v["nome"] for v in variantes} == {"vmin_0"}
    assert all(set(v) == {"nome", "rotulo", "origem"} for v in variantes)


def test_variante_de_premissa_nao_toca_o_contexto(planta_propostas):
    ctx = planta_propostas.contexto
    antes = dict(ctx.alteracoes)
    rt = inv.executar_variante(ctx, "SG-001", {"rotulo": "η 80 %", "premissas": {"eta_F": 0.80}, "origem": "teste"})
    assert ctx.alteracoes == antes and rt.status == "dimensionado"
    assert rt.resultado.x != planta_propostas.tag("SG-001").resultado.x or rt.resultado.y != planta_propostas.tag(
        "SG-001").resultado.y


def test_trens_dividem_a_vazao_pelo_mesmo_servico(planta_propostas):
    """Variante de trens: a vazão de cada caso vai dividida — a mesma função que a otimização usa."""
    rt = inv.executar_variante(planta_propostas.contexto, "SG-001",
                               {"rotulo": "2 trens", "fator_vazao": 2, "chaves_vazao": ["q_oil", "q_water", "q_gas"],
                                "origem": "teste"})
    base = planta_propostas.tag("SG-001")
    for c2, c1 in zip(rt.entradas.casos, base.entradas.casos, strict=True):
        if c1.ativo:
            assert c2.valores["q_oil"].valor == c1.valores["q_oil"].valor / 2


@pytest.mark.parametrize("ident", ["P-002", "P-003"])
def test_p46_oleo_no_casco_e_agua_nos_tubos(planta_propostas, ident):
    """P-46: no P-002 e no P-003 o óleo vai no casco e a água de utilidade nos tubos, com a vazão
    da utilidade fechando a carga do balanço."""
    from fpso_siz.pfd.tags import tag
    t = tag(ident)
    assert t.entradas["m_tubo"]["regra"] == "vazao_utilidade"
    rt = planta_propostas.tag(ident)
    assert rt.status == "dimensionado"
    for c in rt.entradas.casos:
        if c.ativo:
            assert "IAPWS" in c.valores["rho_tubo"].fonte
