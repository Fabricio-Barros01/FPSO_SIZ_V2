"""F15 — avaliador e otimização multiobjetivo (`pfd/otimizacao.py`, `_otim.py`).

Cobre os quatro critérios de validação do `docs/decisoes/0003-otimizacao-pymoo.md`, na escala em
que a suíte pode pagar: o ponto do projeto atual reproduzido pelo avaliador, a frente do NSGA-II
conferida contra uma varredura exaustiva (grade grossa, declarada no teste), a reprodutibilidade
pela semente, e o isolamento — a otimização não altera o dimensionamento padrão.

Também se fixa o que a rodada NÃO pode fazer: variável sem limite de origem declarada, valor
apenas proposto como variável de decisão, e lacuna ou caso inativo contando como violação.
"""
import math
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


@pytest.fixture(scope="module")
def dados():
    return carregar_casos(CASOS)


def x_do_projeto(dados, sub=None):
    base = premissas(dados)
    x = []
    for v in ot.variaveis(sub):
        if v["destino"] == "premissa":
            x.append(float(base[v["chave"]]))
        elif v["destino"] == "fator_vazao":
            x.append(1.0)
        else:
            rec = tag(v["tag"]).recomendadas.get(v["chave"])
            x.append(float(rec["valor"]) if rec else float(v["min"]))
    return tuple(x)


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
    # só o P-001 ainda viola: P-002 e P-003 fecharam quando a película do lado tubo passou a ter os
    # três regimes (docs/validacao/24-pelicula-baixo-reynolds.md)
    assert not a.viavel and {t for t, g in a.restricoes.items() if g > 0} == {"P-001"}


def test_a_decodificacao_respeita_destino_e_tipo(dados):
    prem, geral, trens = ot.decodificar((0.87, 2.4, 1.0, 2.0))
    assert prem == {"eta_F": 0.87}          # real passa como está
    assert trens == {"SG-001": (2, ["q_oil", "q_water", "q_gas"])}   # inteiro é arredondado
    assert geral == {"P-002": {"passes_tubo": 1.0}, "P-003": {"passes_tubo": 2.0}}
    lo, hi, inteiros = ot.limites()
    assert inteiros == [False, True, True, True] and len(lo) == len(hi) == 4


def test_lacuna_e_caso_inativo_nao_contam_como_violacao(dados):
    """Estado de dado não é violação de projeto: sem as propostas, os TAGs com lacuna ficam
    "aguardando entrada", e a restrição os ignora."""
    a = ot.avaliar(dados, x_do_projeto(dados), propostas=mod_propostas.NENHUMA)
    aguardando = [t for t, e in a.estados.items() if e in ot.cfg()["restricoes"]["estados_neutros"]]
    assert aguardando
    assert all(a.restricoes[t] == 0.0 for t in aguardando)


def test_a_violacao_soma_so_os_tags_que_violam(dados):
    """A métrica de violação é a distância ao admissível: quem está dimensionado não entra, e o
    total é a soma do que violou. Com os alarmes dos trocadores fechados, sobra o P-001."""
    a = ot.avaliar(dados, x_do_projeto(dados))
    assert a.restricoes["P-002"] == 0.0 and a.restricoes["P-003"] == 0.0
    assert a.restricoes["P-001"] > 0
    assert a.violacao_total == sum(g for g in a.restricoes.values() if g > 0)


@pytest.mark.otim
def test_criterio_2_a_frente_do_nsga2_nao_e_dominada_pela_varredura_exaustiva(dados):
    """A frente do algoritmo tem de bater com a da grade: nenhum ponto da varredura exaustiva
    domina um ponto da frente. É o critério 2 do 0003, em grade grossa."""
    from fpso_siz import _otim
    ids = [o["id"] for o in ot.objetivos(SUB)]
    ref = [a for a in ot.varredura(dados, SUB, PASSOS) if a.viavel]
    assert ref, "a grade do subproblema tem de ter pontos viáveis"
    frente_ref = ot.nao_dominados([a.objetivos for a in ref], ids)
    _, hist, meta = _otim.otimizar(dados, populacao=6, geracoes=2, sub=SUB)
    viaveis = [a for a in hist if a.viavel]
    assert viaveis and meta["algoritmo"] == "NSGA-II"
    frente_alg = ot.nao_dominados([a.objetivos for a in viaveis], ids)
    tol = 1e-9
    assert not [p for p in frente_alg if any(ot.domina(q, p, ids, tol) for q in frente_ref)]


@pytest.mark.otim
def test_criterio_3_mesma_semente_mesma_frente(dados):
    from fpso_siz import _otim
    a = _otim.otimizar(dados, populacao=4, geracoes=2, semente=7, sub=SUB)
    b = _otim.otimizar(dados, populacao=4, geracoes=2, semente=7, sub=SUB)
    assert [p[0] for p in a[0]] == [p[0] for p in b[0]]
    assert [p[1] for p in a[0]] == [p[1] for p in b[0]]


def test_criterio_4_a_otimizacao_nao_altera_o_dimensionamento_padrao(dados):
    """Isolamento: avaliar pontos fora do projeto não muda o resultado padrão de nenhum TAG."""
    from fpso_siz.pfd import equipamento as servico
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())
    antes = {rt.tag.tag: (rt.status, rt.resultado.x if rt.resultado else None)
             for rt in dimensionar(contexto=ctx).tags}
    ot.avaliar(dados, (0.9, 3.0, 1.0, 2.0))
    depois = {rt.tag.tag: (rt.status, rt.resultado.x if rt.resultado else None)
              for rt in dimensionar(contexto=ctx).tags}
    for ident, (estado, x) in antes.items():
        e2, x2 = depois[ident]
        assert estado == e2 and (x == x2 or (x != x and x2 != x2)), ident


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
