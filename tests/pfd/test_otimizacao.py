"""F15 — avaliador e otimização multiobjetivo (`pfd/otimizacao.py`, `_otim.py`).

Cobre os quatro critérios de validação do `docs/decisoes/0003-otimizacao-pymoo.md`, na escala em
que a suíte pode pagar: o ponto do projeto atual reproduzido pelo avaliador, a frente do NSGA-II
conferida contra uma varredura exaustiva (grade grossa, declarada no teste), a reprodutibilidade
pela semente, e o isolamento — a otimização não altera o dimensionamento padrão.

Também se fixa o que a rodada NÃO pode fazer: variável sem limite de origem declarada, valor
apenas proposto como variável de decisão, e lacuna ou caso inativo contando como violação.
"""
import os
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar
from fpso_siz.pfd.tags import tag

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"
SUB = "sg_001"
# grade grossa só para o teste: a da ferramenta é a declarada no TOML
PASSOS = {"eta_F": 0.05}
# Uma avaliação deste subproblema custa dezenas de segundos (balanço + TAGs, com o SG-001
# redimensionado por causa dos trens), e os critérios 2 e 3 pedem dezenas delas. Avaliar em
# processos dá EXATAMENTE o mesmo resultado (tests/pfd/test_otimizacao_paralela.py prova a
# equivalência), então o que estes testes verificam não muda — só o tempo de parede. O número é
# conservador de propósito: a suíte já roda com workers do xdist em volta.
PROCESSOS = max(2, (os.cpu_count() or 4) // 4)


@pytest.fixture(scope="module")
def dados():
    return carregar_casos(CASOS)


def x_do_projeto(dados, sub=None):
    return ot.ponto_referencia(dados, sub)


def test_o_ponto_de_referencia_e_o_projeto_atual(dados):
    base = premissas(dados)
    assert ot.ponto_referencia(dados) == (
        float(base["eta_F"]), 1.0, *(float(tag(t).recomendadas["passes_tubo"]["valor"]) for t in ("P-002", "P-003")))


def test_toda_variavel_tem_limite_com_origem_declarada():
    """A regra do 0003: variável de decisão só com limite de origem declarada. E valor apenas
    PROPOSTO (pendencias_propostas.toml) não é variável de decisão."""
    propostas = mod_propostas.padrao()
    for v in ot.variaveis():
        assert v["fonte"].strip() and float(v["min"]) < float(v["max"]), v["id"]
        assert v["tipo"] in ("real", "inteiro") and v["destino"] in ("premissa", "tag_geral", "fator_vazao")
        if v["destino"] == "tag_geral":
            assert propostas.de(v["tag"], v["chave"], 1) is None, f"{v['id']} é valor proposto"
    for o in ot.objetivos():
        assert o["fonte"].strip() and o["sentido"] == "minimizar" and o["unidade"]


def test_o_subproblema_e_um_recorte_declarado():
    s = ot.subproblema(SUB)
    assert s["fonte"].strip()
    assert [v["id"] for v in ot.variaveis(SUB)] == list(s["variaveis"])
    assert [o["id"] for o in ot.objetivos(SUB)] == list(s["objetivos"])
    assert ot.tags_restritas(SUB) == list(s["tags"])
    assert set(ot.tags_restritas(SUB)) <= set(ot.tags_restritas())
    with pytest.raises(ValueError, match="subproblema desconhecido"):
        ot.subproblema("nao_existe")


def test_criterio_1_o_avaliador_reproduz_o_ponto_do_projeto_atual(dados):
    """O ponto do projeto atual avaliado pela otimização dá os MESMOS estados por TAG que o
    dimensionamento padrão da planta."""
    a = ot.avaliar(dados, x_do_projeto(dados))
    from fpso_siz.pfd import equipamento as servico
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())
    planta = dimensionar(contexto=ctx)
    assert a.convergiu
    for ident, estado in a.estados.items():
        assert planta.tag(ident).status == estado, ident
    # Nenhum TAG viola requisito obrigatório: o P-001 é a geometria instalada (ADR 0005), não um
    # DESIGN inviável. Mas o ponto NÃO é aprovado: o comprimento do tubo é decisão pendente
    # (nota 46) e a hidráulica do P-001 está incompleta (perdas de carga sem critério vigente).
    assert all(g == 0 for g in a.restricoes.values()) and a.admissivel and not a.viavel
    assert a.situacao == "decisao_pendente"
    assert a.pendencias == {"P-001": ["comprimento_tubo"]}
    assert set(a.incompletas) == {"P-001"} and a.incompletas["P-001"]
    assert "recuperacao_parcial" in a.limitacoes["P-001"]
    assert [m["tipo"] for m in a.motivos()] == ["decisao_pendente", "verificacao_incompleta"]
    # objetivos pelas regras centrais: área INSTALADA (o P-001 com a reserva) e utilidade no
    # estado operacional depois do rating — não no preliminar
    areas = {t: servico.areas_troca(planta.tag(t)) for t in ("P-001", "P-002", "P-003")}
    assert areas["P-001"]["instalada_m2"] == planta.tag("P-001").operacao.areas["instalada_m2"]
    assert a.objetivos["area_trocadores"] == sum(x["instalada_m2"] for x in areas.values())
    def q(estados):
        return max(r.duties["Q_H"] + r.duties["Q_D"] for r in estados)
    assert a.objetivos["carga_aquecimento"] == q(planta.balanco_operacional)
    assert a.objetivos["carga_aquecimento"] > q(planta.balanco)


def test_a_decodificacao_respeita_destino_e_tipo(dados):
    prem, geral, trens = ot.decodificar((0.87, 2.4, 1.0, 2.0))
    assert prem == {"eta_F": 0.87}          # real passa como está
    assert trens == {"SG-001": (2, ["q_oil", "q_water", "q_gas"])}   # inteiro é arredondado
    assert geral == {"P-002": {"passes_tubo": 1.0}, "P-003": {"passes_tubo": 2.0}}
    lo, hi, inteiros = ot.limites()
    assert inteiros == [False, True, True, True] and len(lo) == len(hi) == 4


def test_lacuna_e_caso_inativo_nao_contam_como_violacao(dados):
    """Estado de dado não é violação de projeto: sem as propostas, os TAGs com lacuna ficam
    "aguardando entrada", e a MEDIDA DE VIOLAÇÃO os ignora."""
    a = ot.avaliar(dados, x_do_projeto(dados), propostas=mod_propostas.NENHUMA)
    aguardando = [t for t, e in a.estados.items() if e in ot.cfg()["restricoes"]["estados_neutros"]]
    assert aguardando
    assert all(a.restricoes[t] == 0.0 for t in aguardando)


def test_falta_de_dado_nao_produz_candidato_viavel(dados):
    """Neutro na violação NÃO é projeto avaliado. Sem as propostas há TAG esperando entrada:
    o ponto é "não avaliável" e não pode sair como viável — não se sabe se aquele TAG atende."""
    sem_dado_declarados = set(ot.cfg()["restricoes"]["estados_sem_dado"])
    assert sem_dado_declarados <= set(ot.cfg()["restricoes"]["estados_neutros"])
    a = ot.avaliar(dados, x_do_projeto(dados), propostas=mod_propostas.NENHUMA)
    esperado = {t for t, e in a.estados.items() if e in sem_dado_declarados}
    assert esperado and a.sem_dado == esperado
    assert all(a.restricoes[t] == 0.0 for t in a.sem_dado)   # continua não sendo violação
    assert not a.avaliavel and not a.viavel and a.situacao == "nao_avaliavel"


def test_as_quatro_situacoes_de_um_ponto_sao_distintas():
    """`dimensionado`, `inviável`, `inativo` e `não avaliável` são estados diferentes. O status
    por TAG fica em `estados`; `situacao` classifica o PONTO, e nunca chama de viável um ponto
    de que falta dado."""
    def av(estados, restricoes, convergiu=True, sem_dado=frozenset()):
        return ot.Avaliacao((), {}, restricoes, estados, convergiu, sem_dado)

    # TAG inativo é estado de dado como a lacuna, mas o ponto segue julgável: nada falta.
    inativo = av({"A": "dimensionado", "B": "inativo"}, {"A": 0.0, "B": 0.0})
    assert inativo.avaliavel and inativo.viavel and inativo.situacao == "viavel"

    aguardando = av({"A": "dimensionado", "B": "aguardando_entrada"}, {"A": 0.0, "B": 0.0},
                    sem_dado=frozenset({"B"}))
    assert not aguardando.avaliavel and not aguardando.viavel
    assert aguardando.situacao == "nao_avaliavel" and aguardando.violacao_total == 0.0

    inviavel = av({"A": "inviavel"}, {"A": 0.4})
    assert inviavel.avaliavel and not inviavel.viavel and inviavel.situacao == "inviavel"

    # falta de dado E violação: o que falta primeiro é o dado
    ambos = av({"A": "inviavel", "B": "aguardando_entrada"}, {"A": 0.4, "B": 0.0},
               sem_dado=frozenset({"B"}))
    assert ambos.situacao == "nao_avaliavel"

    nao_convergiu = av({"A": ""}, {"A": 1.0}, convergiu=False)
    assert nao_convergiu.situacao == "nao_convergiu" and not nao_convergiu.avaliavel


def test_o_algoritmo_recebe_o_dado_ausente_como_restricao_a_mais():
    """Em `_otim`, G tem uma posição além dos TAGs: a contagem dos que esperam entrada. É o que
    impede o pymoo de devolver como viável um ponto não avaliável."""
    from fpso_siz import _otim
    tags = ["A", "B"]
    completo = ot.Avaliacao((), {"o": 1.0}, {"A": 0.0, "B": 0.0}, {"A": "dimensionado", "B": "inativo"},
                            True, frozenset())
    faltando = ot.Avaliacao((), {"o": 1.0}, {"A": 0.0, "B": 0.0},
                            {"A": "dimensionado", "B": "aguardando_entrada"}, True, frozenset({"B"}))
    f1, g1 = _otim._saidas(completo, ["o"], tags, 1e9)
    f2, g2 = _otim._saidas(faltando, ["o"], tags, 1e9)
    assert f1 == f2 == [1.0]
    assert len(g1) == len(tags) + 1
    assert g1 == [0.0, 0.0, 0.0] and max(g1) <= 0
    assert g2 == [0.0, 0.0, 1.0] and max(g2) > 0


def test_a_violacao_soma_so_os_tags_que_violam():
    """A métrica de violação é a distância ao admissível: dimensionado sem restrição não entra;
    dimensionado com requisito obrigatório não atendido conta um por critério (o P-001 instalado
    classifica os dele); decisão pendente não é violação; e o total é a soma do que violou."""
    from types import SimpleNamespace
    neutros = ot.cfg()["restricoes"]["estados_neutros"]
    assert ot._violacao(SimpleNamespace(status="dimensionado", restricoes=[]), neutros) == 0.0
    assert ot._violacao(SimpleNamespace(status="dimensionado", restricoes=["comprimento_tubo", "velocidade_tubo"]),
                        neutros) == 2.0
    assert ot._violacao(SimpleNamespace(status="inviavel", resultado=None), neutros) == 1.0
    a = ot.Avaliacao((), {}, {"A": 0.0, "B": 2.0, "C": 0.5}, {"A": "dimensionado", "B": "dimensionado",
                                                            "C": "inviavel"}, True,
                     violados={"B": ["comprimento_tubo", "velocidade_tubo"]})
    assert a.violacao_total == 2.5 and a.situacao == "inviavel"
    assert [(m["id"], m["criterios"]) for m in a.motivos()] == [("B", ["comprimento_tubo", "velocidade_tubo"]),
                                                                 ("C", ["inviavel"])]


def test_pendencia_e_verificacao_incompleta_nao_sao_aprovacao():
    """Sem violação, o ponto é admissível; mas decisão pendente ou verificação incompleta
    impedem o `viavel` — e a precedência é a pendência."""
    def av(pend=None, inc=None):
        return ot.Avaliacao((), {}, {"A": 0.0}, {"A": "dimensionado"}, True, pendencias=pend or {},
                            incompletas=inc or {})
    assert av().situacao == "viavel" and av().viavel
    assert av(inc={"A": ["perda_carga_tubo"]}).situacao == "verificacao_incompleta"
    pendente = av({"A": ["comprimento_tubo"]}, {"A": ["perda_carga_tubo"]})
    assert pendente.situacao == "decisao_pendente" and pendente.admissivel and not pendente.viavel


def test_areas_e_multiplicidade_coincidem_com_o_dimensionamento(planta_propostas):
    """Uma regra de área: a otimização lê o que o JSON e o memorial leem. Por unidade × unidades
    em operação = em operação (a que entra no U·A do rating); por unidade × instaladas = instalada
    (com a reserva, que não troca calor). Replicar um TAG que já tem multiplicidade é recusado."""
    from fpso_siz.pfd import equipamento as servico
    rt = planta_propostas.tag("P-001")
    a, g = servico.areas_troca(rt), rt.operacao.geometria
    assert {k: a[k] for k in rt.operacao.areas} == rt.operacao.areas and a["origem"] == "geometria_instalada"
    assert a["por_unidade_m2"] == g.area_unitaria and g.instaladas == g.duty + g.standby
    assert a["em_operacao_m2"] == pytest.approx(g.duty * g.area_unitaria, rel=1e-12)
    assert a["instalada_m2"] == pytest.approx(g.instaladas * g.area_unitaria, rel=1e-12)
    assert (a["unidades_em_operacao"], a["unidades_reserva"]) == (g.duty, g.standby)
    for c in rt.operacao.casos:   # avaliação térmica pela área em serviço
        d = c.diagnosticos
        if d.get("U_W_m2K") and d.get("UA_W_K"):
            assert d["UA_W_K"] / d["U_W_m2K"] == pytest.approx(a["em_operacao_m2"], rel=1e-9), c.num
    for ident in ("P-002", "P-003"):
        r = planta_propostas.tag(ident).resultado
        b = servico.areas_troca(planta_propostas.tag(ident))
        assert b["em_operacao_m2"] == b["instalada_m2"] == r.derivados_v2.get("area_total", r.derivados["area"])
        assert b["unidades_reserva"] == 0 and b["origem"] == "envelope_design"
    assert servico.areas_troca(planta_propostas.tag("V-001")) is None
    o = next(o for o in ot.objetivos() if o["id"] == "area_trocadores")
    assert o["base"] == "instalada_m2"
    with pytest.raises(ValueError, match="duas vezes"):
        ot._objetivo(o, planta_propostas, {"P-001": 2})


def test_p002_e_p003_continuam_no_estado_pos_rating(planta_propostas):
    from fpso_siz.balanco.estado import ETAPA_RATING
    for ident in ("P-002", "P-003"):
        assert planta_propostas.tag(ident).etapa_balanco == ETAPA_RATING
    op = planta_propostas.tag("P-001").operacao
    estados = {r.num: r for r in planta_propostas.balanco_operacional}
    assert len(op.casos) == len(estados) == 16
    for c in op.casos:
        assert (c.q_p002, c.q_p003) == (estados[c.num].duties["Q_H"], estados[c.num].duties["Q_C"])


@pytest.mark.otim
def test_criterio_2_a_frente_do_nsga2_nao_e_dominada_pela_varredura_exaustiva(dados):
    """A frente do algoritmo tem de bater com a da grade: nenhum ponto da varredura exaustiva
    domina um ponto da frente. É o critério 2 do 0003, em grade grossa."""
    from fpso_siz import _otim
    ids = [o["id"] for o in ot.objetivos(SUB)]
    ref = [a for a in _otim.avaliar_pontos(dados, ot.grade(SUB, PASSOS), sub=SUB, processos=PROCESSOS)
           if a.viavel]
    assert ref, "a grade do subproblema tem de ter pontos viáveis"
    frente_ref = ot.nao_dominados([a.objetivos for a in ref], ids)
    _, hist, meta = _otim.otimizar(dados, populacao=6, geracoes=2, sub=SUB, processos=PROCESSOS)
    viaveis = [a for a in hist if a.viavel]
    assert viaveis and meta["algoritmo"] == "NSGA-II"
    frente_alg = ot.nao_dominados([a.objetivos for a in viaveis], ids)
    tol = 1e-9
    assert not [p for p in frente_alg if any(ot.domina(q, p, ids, tol) for q in frente_ref)]


@pytest.mark.otim
def test_criterio_3_mesma_semente_mesma_frente(dados):
    from fpso_siz import _otim
    a = _otim.otimizar(dados, populacao=4, geracoes=2, semente=7, sub=SUB, processos=PROCESSOS)
    b = _otim.otimizar(dados, populacao=4, geracoes=2, semente=7, sub=SUB, processos=PROCESSOS)
    assert [p[0] for p in a[0]] == [p[0] for p in b[0]]
    assert [p[1] for p in a[0]] == [p[1] for p in b[0]]


def test_criterio_4_a_otimizacao_nao_altera_o_dimensionamento_padrao(dados):
    """Isolamento: avaliar pontos fora do projeto não muda o resultado padrão de nenhum TAG."""
    from fpso_siz.pfd import equipamento as servico
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())

    def foto(planta):
        return {rt.tag.tag: (rt.status, rt.resultado.x if rt.resultado else None, servico.areas_troca(rt),
                             rt.operacao.estrutura() if rt.operacao is not None else None,
                             rt.etapa_balanco) for rt in planta.tags}
    antes = foto(dimensionar(contexto=ctx))
    ot.avaliar(dados, (0.9, 3.0, 1.0, 2.0))
    depois = foto(dimensionar(contexto=ctx))
    for ident, (estado, x, areas, op, etapa) in antes.items():
        e2, x2, areas2, op2, etapa2 = depois[ident]
        assert estado == e2 and (x == x2 or (x != x and x2 != x2)), ident
        assert (areas, op, etapa) == (areas2, op2, etapa2), ident


def test_dominancia_e_nao_dominados_sao_minimizacao_estrita():
    ids = ["a", "b"]
    p1, p2, p3 = {"a": 1.0, "b": 2.0}, {"a": 2.0, "b": 3.0}, {"a": 2.0, "b": 1.0}
    assert ot.domina(p1, p2, ids) and not ot.domina(p2, p1, ids)
    assert not ot.domina(p1, p3, ids) and not ot.domina(p3, p1, ids)
    assert ot.nao_dominados([p1, p2, p3], ids) == [p1, p3]
    # objetivo não calculável (NaN) não domina nem é dominado
    nan = {"a": float("nan"), "b": 0.0}
    assert not ot.domina(nan, p1, ids) and not ot.domina(p1, nan, ids)


def test_a_grade_da_varredura_cobre_os_limites_e_as_inteiras(dados):
    g = ot.grade(SUB, PASSOS)
    etas = sorted({x[0] for x in g})
    trens = sorted({x[1] for x in g})
    assert etas[0] == 0.80 and abs(etas[-1] - 0.90) <= 1e-12
    assert trens == [1.0, 2.0, 3.0]
    assert len(g) == len(etas) * len(trens)


def test_comparacao_finita_rastreavel_e_parcial(dados):
    """Comparação de configurações: domínio explícito (a referência primeiro), limite de
    avaliações, cada candidato classificado com os motivos, e resultado parcial utilizável quando
    o limite corta o domínio. Duas avaliações bastam para o comportamento (cada uma é a planta)."""
    from fpso_siz import _otim
    sub = "configuracao"
    assert len(ot.grade(sub)) == 12
    c = ot.comparar(dados, sub, limite=2, avaliar_pontos=lambda pts: _otim.avaliar_pontos(
        dados, pts, sub=sub, processos=PROCESSOS))
    assert c.dominio[0] == ot.ponto_referencia(dados, sub) and len(set(c.dominio)) == 12
    assert len(c.avaliacoes) == 2 and c.limite_atingido and len(c.nao_avaliados) == 10
    assert [a.x for a in c.avaliacoes] == list(c.dominio[:2])
    for a in c.avaliacoes:
        assert a.situacao in ("inviavel", "decisao_pendente", "verificacao_incompleta", "viavel",
                              "nao_avaliavel", "nao_convergiu")
        assert a.viavel or a.motivos()
    assert c.referencia.situacao == "decisao_pendente" and not c.com_situacao("viavel")
    assert all(a.admissivel for a in c.frente())
    with pytest.raises(ValueError, match="ao menos uma"):
        ot.comparar(dados, sub, limite=0)
