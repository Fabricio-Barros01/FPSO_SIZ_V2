"""Mapeamento real, lacunas, precedência, inatividade e proveniência (F10b)."""
import math
from dataclasses import replace

import pytest

from fpso_siz.balanco.balancos import topologia
from fpso_siz.core.parametros import defaults
from fpso_siz.core.motor import size_single
from fpso_siz.termo import servico as termo
from fpso_siz.pfd.entradas import conferir_tag, montar
from fpso_siz.pfd.planta import dimensionar
from fpso_siz.pfd.tags import tag, tags
from fpso_siz.sizing import CentrifugalPump, MoranPumpSizing


def montagem(p, nome, ajustes=None, casos=None, config=None):
    return montar(config or tag(nome), p.balanco if casos is None else casos, p.dados, p.prem, ajustes)


def test_topologia_e_metodos():
    blocos = {b["id"]: b for b in topologia()["blocos"]}
    assert len(tags()) == 11
    for t in tags():
        eq, m = t.resolver()
        assert eq.method_id == m.applies_to().method_id == t.equipamento
        b = blocos[t.bloco]
        correntes = set(b["entradas"]) | set(b["saidas"])
        assert not t.condicao or t.condicao in correntes
        assert all(r["corrente"] in correntes for r in t.entradas.values() if "corrente" in r)
    with pytest.raises(KeyError, match="TAG desconhecido"):
        tag("XXX")


def test_lacunas_exatas(planta_base):
    bombas = {"h_geometrica", "h_sucao", "l_sucao", "k_sucao", "l_recalque", "k_recalque",
              "npsh_requerido", "npsh_margem"}
    troca = {"k_tubo", "k_parede", "rf_tubo", "rf_casco"}
    esperadas = {**{t: bombas for t in ("B-001", "B-002", "B-003")},
                 "P-001": troca | {"k_casco"},
                 # P-46: o óleo no casco (k_casco é lacuna); a água nos tubos sai da IAPWS
                 **{t: troca - {"k_tubo"} | {"k_casco", "t_agua_in", "t_agua_out"} for t in ("P-002", "P-003")},
                 **{t: {"dm_water"} for t in ("TO-001", "TO-002")},
                 **{t: set() for t in ("SG-001", "V-001", "V-002")}}
    for t in planta_base.tags:
        assert {x.chave for x in t.entradas.lacunas} == esperadas[t.tag.tag]
        assert (t.resultado is None) == bool(esperadas[t.tag.tag])
        for l in t.entradas.lacunas:
            assert l.rotulo and l.unidade and l.dica and l.casos
    assert not planta_base.completa
    # P-42: os casos sem fase aquosa (1, 4–7) não pedem a gotícula de água nem impõem teto
    for nome in ("TO-001", "TO-002"):
        assert planta_base.tag(nome).entradas.lacunas[0].casos == (2, 3, 8, 9, 10, 11, 12, 13, 14, 15, 16)
    # com óleo vivo (padrão) o SG-001 tem solução; o teto segue no caso 2 (com água)
    sg = planta_base.tag("SG-001")
    assert sg.status == "dimensionado" and sg.resultado.ceiling_case == "BOT 02 — Early Life"


def test_inativos_sem_vazao_e_sem_carga(planta_base):
    for nome, nums in {"B-002": {1, 4, 5, 6, 7}, "B-003": {1, 4, 5, 6, 7},
                       "P-001": {10, 12, 13, 14, 15, 16}, "P-002": {10, 12, 13, 14, 15, 16}}.items():
        e = planta_base.tag(nome).entradas
        assert {c.num for c in e.casos if not c.ativo} == nums
        assert all(c.motivo and not c.avisos for c in e.casos if not c.ativo)
        assert all(not (set(l.casos) & nums) for l in e.lacunas)
        if nome.startswith("B"):
            assert all(c.valores["q_oil"].valor == 0 for c in e.casos if not c.ativo)


def test_todas_entradas_tem_fonte_e_rastro(planta_base, planta_ajustada):
    for p in (planta_base, planta_ajustada):
        for t in p.tags:
            for c in t.entradas.casos:
                entradas = {e.var: e for e in c.rastro if e.block == "entradas"}
                assert set(c.valores) <= set(entradas)
                for k, v in c.valores.items():
                    if v.lacuna:
                        assert math.isnan(v.valor) and v.pendente
                    elif v.nao_aplicavel:  # P-42: sem fase aquosa no caso; fonte citada, sem número
                        assert math.isnan(v.valor) and not v.pendente and "P-42" in v.fonte
                        assert c.valores["q_water"].valor == 0 and not v.revisao
                    else:
                        assert v.fonte and math.isfinite(v.valor)
                        assert entradas[k].value == v.valor
                assert all(e.eq and e.formula and e.unit for e in c.rastro if e.block == "propriedades")


def test_11_envelopes(planta_ajustada, planta_propostas):
    """Os 11 TAGs dimensionam: com as entradas sintéticas (o P-002 e o P-003 esperam as
    temperaturas da utilidade, que só as propostas dão) e na planta produtiva (onde os 11 TAGs
    são dimensionados)."""
    for t in planta_ajustada.tags:
        esperado = "aguardando_entrada" if t.tag.tag in ("P-002", "P-003") else "dimensionado"
        assert t.status == esperado, t.tag.tag
    for t in planta_propostas.tags:
        assert t.status == "dimensionado", t.tag.tag
    for p in (planta_ajustada, planta_propostas):
        for t in p.tags:
            if t.status != "dimensionado":
                continue
            assert t.resultado.driver_case in t.resultado.case_names
            assert t.resultado.x > 0 and t.resultado.y > 0
            assert len(t.resultado.per_case) == sum(c.ativo for c in t.entradas.casos)
    assert planta_propostas.sem_dimensionamento == ["M-01", "DWH-001", "M-02", "M-03", "MED-001"]


def test_precedencia_e_dependencias(planta_base):
    e = montagem(planta_base, "V-001", {"tr_liquid": 6, "q_oil": 10, "caso": {"1": {"q_oil": 12}}})
    assert e.casos[0].valores["q_oil"].valor == 12
    assert e.casos[1].valores["q_oil"].valor == 10
    assert all(c.valores["tr_liquid"].origem == "usuario" for c in e.casos)
    base = planta_base.tag("V-001").entradas
    assert base.casos[0].valores["tr_liquid"].valor == 5
    assert not base.avisos()  # μ do óleo não é usada pelo knockout
    assert base.casos[0].valores["q_oil"].valor != 12
    f = montagem(planta_base, "P-002", {"t_agua_in": 120})
    assert "t_agua_in" not in {l.chave for l in f.lacunas}
    assert "t_agua_out" in {l.chave for l in f.lacunas}


def test_balanco_energia_utilidades_e_pv(planta_propostas):
    """P-46: a utilidade vai nos tubos; a vazão dela fecha a carga do estado que preparou o TAG.

    Esse estado é o REALIZADO (ADR 0005): a carga do aquecedor e do resfriador é a residual, a
    que o processo ainda exige depois do que a geometria do pré-aquecedor recuperou de fato. É
    por isso que a comparação é com `balanco_do_tag`, e não com o balanço preliminar."""
    ctx = planta_propostas.contexto
    for nome, carga, sinal in (("P-002", "Q_H", 1), ("P-003", "Q_C", -1)):
        for c, r in zip(planta_propostas.tag(nome).entradas.casos, ctx.balanco_do_tag(nome)):
            if not c.ativo:
                continue
            vs = c.valores
            delta = c.insumos["t_agua_in"].valor - c.insumos["t_agua_out"].valor
            assert vs["m_tubo"].valor * vs["cp_tubo"].valor * delta * sinal == pytest.approx(r.duties[carga]*1000)
            assert set(c.insumos) == {"t_agua_in", "t_agua_out"}
            # e a residual é maior ou igual à preliminar: o que não foi recuperado vira utilidade
            preliminar = next(x for x in planta_propostas.balanco if x.num == r.num)
            assert r.duties[carga] >= preliminar.duties[carga] - 1e-9
    for nome in ("B-001", "B-002", "B-003"):
        for c in planta_propostas.tag(nome).entradas.casos:
            assert c.valores["pv_informada"].valor == c.valores["pressure"].valor


def test_mistura_salinidade_e_vazao(planta_base):
    e = planta_base.tag("TO-002").entradas
    c, r = e.casos[7], planta_base.balanco[7]
    s = r.streams["C-18"]
    pr = planta_base.prem
    sal = sum(s[k] * termo.fracao_sal(pr[a], pr[b]) for k, a, b in (("W", "S_W", "rho_W"), ("D", "S_D", "rho_D")))
    w = sal/(s["W"]+s["D"])
    prop = termo.salmoura_fracao(r.T["C-18"], w)
    assert c.valores["rho_water"].valor == prop.rho
    assert c.valores["q_water"].valor == (s["W"]+s["D"])/prop.rho*3600
    assert c.valores["mu_water"].valor == prop.mu
    assert e.specs["rho_water"].max == 1500
    assert e.metodo.stream_parameters() != list(e.specs.values())


@pytest.mark.parametrize("ajuste, mensagem", [
    ({"nao_existe": 1}, "desconhecida"), ({"q_oil": True}, "finito"),
    ({"q_oil": math.nan}, "finito"), ({"q_oil": "1"}, "finito"),
    ({"caso": {"99": {}}}, "não existe"), ({"caso": {"1": 2}}, "tabela"),
    ({"caso": []}, "tabela"), ({"caso": {"1": {}, "01": {}}}, "duplicado"),
    (1, "tabela"),
])
def test_ajustes_invalidos(planta_base, ajuste, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        montagem(planta_base, "B-001", ajuste)


@pytest.mark.parametrize("entrada,saida", [(100, 120), (100, 100)])
def test_utilidade_com_sentido_invalido(planta_base, entrada, saida):
    with pytest.raises(ValueError, match="sentido da troca"):
        montagem(planta_base, "P-002", {"t_agua_in": entrada, "t_agua_out": saida})


def test_limite_bot_e_dominio_grade(planta_base):
    e = montagem(planta_base, "P-002", {"t_agua_in": 125, "t_agua_out": 100})
    assert any("acima do limite" in a for a, _ in e.avisos())
    e = montagem(planta_base, "P-001", {"v_min": 0})
    assert "n_max" in {l.chave for l in e.lacunas}


def test_tag_todo_inativo_e_balanco_invalido(planta_base):
    p = dimensionar(planta_base.dados, ajustes={"B-001": {"q_oil": 0}}, balanco=planta_base.balanco)
    assert p.tag("B-001").status == "inativo" and p.tag("B-001").resultado is None
    e = montagem(planta_base, "SG-001", {"q_oil": 0, "q_water": 0, "q_gas": 0})
    assert e.pronto and not any(c.ativo for c in e.casos)
    for balanco, mensagem in (([], "sem casos"), ([planta_base.balanco[0]]*2, "duplicados"),
                              (planta_base.balanco[:1], "não correspondem"),
                              ([replace(r, residuo_reciclo=math.inf) for r in planta_base.balanco], "não convergiu")):
        with pytest.raises(ValueError, match=mensagem):
            dimensionar(planta_base.dados, balanco=balanco)
    with pytest.raises(ValueError, match="desconhecidos"):
        dimensionar(planta_base.dados, ajustes={"XYZ": {}})
    with pytest.raises(ValueError, match="tabela"):
        dimensionar(planta_base.dados, ajustes=[1])


@pytest.mark.parametrize("regra,mensagem", [
    ({"regra": "desconhecida"}, "regra desconhecida"),
    ({"regra": "vazao_fase", "fase": "nada"}, "fase desconhecida"),
    ({"regra": "viscosidade_fase", "fase": "liquido", "continua": "nada"}, "continua"),
])
def test_tag_config_invalida(planta_base, regra, mensagem):
    t = replace(tag("B-001"), entradas={"q_oil": regra})
    with pytest.raises(ValueError, match=mensagem):
        conferir_tag(t, planta_base.tag("B-001").entradas.specs)


def test_bomba_pv_informada_e_antoine():
    m = MoranPumpSizing()
    vals = defaults([*m.parameters(), *m.stream_parameters()])
    vals.update(q_oil=60, h_sucao=10, pv_informada=101.3)
    r = size_single(CentrifugalPump(), m, m.case_input(vals), vals)
    assert r.feasible
    assert next(x.value for x in r.trace if x.var == "NPSH sem atrito") == 10
    assert not any(x.eq == "Eq. 5" for x in r.trace)
    vals["pv_informada"] = math.nan
    r = size_single(CentrifugalPump(), m, m.case_input(vals), vals)
    assert any(x.eq == "Eq. 5" for x in r.trace)
    for pv in (-1, math.inf):
        vals["pv_informada"] = pv
        r = size_single(CentrifugalPump(), m, m.case_input(vals), vals)
        assert not r.feasible and "Pressão de vapor" in r.message
