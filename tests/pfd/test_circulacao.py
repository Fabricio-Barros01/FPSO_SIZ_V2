"""F13/Etapa 2 — estudo de circulação fixa da utilidade (pfd/circulacao.py).

O estudo é variante: fixa a vazão da utilidade no valor do caso de projeto (P-45) e RESOLVE a
temperatura de saída de cada caso, sem supor nenhuma. Estes testes cobrem a conservação de
energia, a procedência da vazão, a temperatura resolvida, a atualização da grade de tubos, a
condição da P-32, os casos inativos, a falha como estado e o isolamento do cálculo padrão.
As grades são reduzidas: nenhum teste roda a busca completa (isso é da ferramenta).
"""
import math

import pytest


from fpso_siz.pfd import circulacao
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import investigacao as inv
from fpso_siz.pfd import reotimizacao as ro

TAGS = ["P-002", "P-003"]


def variante(ident):
    return inv.variante(f"{ident.lower().replace('-', '_')}_circulacao_fixa")


@pytest.fixture(scope="module")
def estudos(planta_propostas):
    """(rt, estudo) de cada TAG, uma vez por módulo (cada execução é um dimensionamento)."""
    ctx = planta_propostas.contexto
    return {ident: circulacao.executar(ctx, ident, variante(ident)) for ident in TAGS}


def _chaves(ident):
    return variante(ident)["circulacao_fixa"]


def _tol_vazao(r):
    """Tolerância relativa admissível da vazão resolvida. A bisseção para pela vazão ou pelo
    intervalo de temperatura (config/pfd/circulacao.toml); como dṁ/dT ≈ ṁ/ΔT, o segundo critério
    deixa um resíduo relativo de até tol_T/|ΔT| — nos casos de turndown profundo o ΔT é pequeno,
    e é esse termo que governa."""
    k = circulacao.cfg()["bissecao"]
    return k["tol_vazao"] + k["tol_temperatura"] / abs(r.t_saida - r.t_entrada)


def _mesmo_numero(a, b):
    return (math.isnan(a) and math.isnan(b)) or a == b


def _base(planta_propostas, ident):
    e = servico.estado_inicial(ident)
    return servico.dimensionar(servico.preparar(planta_propostas.contexto, e), e)


@pytest.mark.parametrize("ident", TAGS)
def test_conservacao_de_energia_em_cada_caso(estudos, ident):
    """A carga de cada caso é a mesma do cálculo padrão, e a vazão resolvida a fecha com o cp na
    temperatura média resultante: ṁ·cp(T̄)·|ΔT| = q."""
    _, est = estudos[ident]
    assert est.ok and est.resolucoes
    for r in est.resolucoes:
        q = r.vazao * r.cp * abs(r.t_entrada - r.t_saida)
        assert r.carga > 0 and abs(q - r.carga) <= 1e-6 * r.carga, r.num


@pytest.mark.parametrize("ident", TAGS)
def test_vazao_vem_do_caso_de_projeto_da_configuracao_base(planta_propostas, estudos, ident):
    """A vazão fixa é a do caso de maior vazão volumétrica no tubo (P-45) da configuração-base, e
    todo caso ativo é resolvido com ela."""
    rt_base = _base(planta_propostas, ident)
    ch = _chaves(ident)
    i = circulacao.caso_de_projeto(rt_base, ch)
    ativos = [c for c in rt_base.entradas.casos if c.ativo]
    esperado = max(ativos, key=lambda c: c.valores[ch["vazao"]].valor / c.valores[ch["densidade"]].valor)
    assert rt_base.entradas.casos[i].num == esperado.num
    _, est = estudos[ident]
    assert est.caso_projeto == esperado.num
    assert est.vazao_fixa == esperado.valores[ch["vazao"]].valor
    for r in est.resolucoes:
        assert abs(r.vazao - est.vazao_fixa) <= _tol_vazao(r) * est.vazao_fixa, r.num


@pytest.mark.parametrize("ident", TAGS)
def test_o_caso_de_projeto_nao_muda_de_temperatura(estudos, ident):
    """No próprio caso de projeto a circulação fixa é a do cálculo padrão: a saída resolvida
    coincide com o insumo (ponto fixo da bisseção)."""
    _, est = estudos[ident]
    r = next(r for r in est.resolucoes if r.projeto)
    assert abs(r.t_saida - r.t_saida_base) <= 1e-6


@pytest.mark.parametrize("ident", TAGS)
def test_temperatura_resolvida_no_sentido_fisico(estudos, ident):
    """No turndown a utilidade troca menos calor com a mesma vazão: a saída se aproxima da
    entrada, sem nunca atravessá-la (aquecimento no P-002, resfriamento no P-003)."""
    _, est = estudos[ident]
    for r in est.resolucoes:
        if r.projeto:
            continue
        assert abs(r.t_saida - r.t_entrada) < abs(r.t_saida_base - r.t_entrada), r.num
        assert min(r.t_entrada, r.t_saida_base) <= r.t_saida <= max(r.t_entrada, r.t_saida_base), r.num


@pytest.mark.parametrize("ident", TAGS)
def test_grade_de_tubos_consome_a_vazao_fixa_e_a_densidade_reavaliada(estudos, ident):
    """As entradas são preparadas outra vez depois de resolver: a grade de tubos por passe
    (n = ṁ/(ρ·v·A_i)) sai da vazão fixa e da densidade da temperatura média resultante."""
    rt, est = estudos[ident]
    ch = _chaves(ident)
    res = {r.num: r for r in est.resolucoes}
    for c in rt.entradas.casos:
        if not c.ativo:
            continue
        r = res[c.num]
        assert abs(c.valores[ch["vazao"]].valor - est.vazao_fixa) <= _tol_vazao(r) * est.vazao_fixa, c.num
        assert abs(c.valores[ch["densidade"]].valor - r.rho) <= 1e-9 * r.rho, c.num
        d_i = (c.valores["d_externo"].valor - 2 * c.valores["espessura"].valor) / 1000
        area = math.pi * d_i * d_i / 4
        n_min = c.valores[ch["vazao"]].valor / (r.rho * c.valores["v_max"].valor * area)
        assert c.valores["n_min"].valor == max(1, math.floor(n_min)), c.num


@pytest.mark.parametrize("ident", TAGS)
def test_condicao_p32_das_duas_aproximacoes(planta_propostas, estudos, ident):
    """A P-32 é condição DO ESTUDO: as duas aproximações terminais de cada caso ativo são lidas do
    rastro que o método já emitiu e comparadas com o ΔT de aproximação do balanço."""
    rt, _ = estudos[ident]
    dt_app = float(planta_propostas.contexto.prem["dT_app"])
    ap = circulacao.aproximacoes(rt, dt_app)
    assert len(ap) == len([c for c in rt.entradas.casos if c.ativo])
    folga = circulacao.cfg()["p32"]["tol_relativa"] * max(1.0, abs(dt_app))
    for a in ap:
        assert a["dt_app"] == dt_app
        assert a["dt1"] is not None and a["dt2"] is not None, a["caso"]
        # a igualdade conta como atendida: no P-003 a aproximação do lado frio cai exatamente no
        # ΔT_app por construção (água a 30 °C, óleo a 40 °C), e o ruído da cadeia não a reprova
        assert a["atende"] == (min(a["dt1"], a["dt2"]) >= dt_app - folga), a["caso"]
        assert a["menor"] == min(a["dt1"], a["dt2"])


@pytest.mark.parametrize("ident", TAGS)
def test_casos_inativos_continuam_inativos(planta_propostas, estudos, ident):
    """O estudo não ativa caso nenhum: quem está inativo (carga nula) continua inativo, com o
    mesmo motivo, e não é resolvido."""
    rt_base, (rt, est) = _base(planta_propostas, ident), estudos[ident]
    inativos_base = {c.num: c.motivo for c in rt_base.entradas.casos if not c.ativo}
    assert {c.num: c.motivo for c in rt.entradas.casos if not c.ativo} == inativos_base
    assert not {r.num for r in est.resolucoes} & set(inativos_base)


def test_falha_de_convergencia_volta_como_estado(planta_propostas, monkeypatch):
    """Falha de convergência é inviabilidade com mensagem, não exceção: com uma iteração só a
    bisseção não fecha, e o TAG volta inviável."""
    original = circulacao.cfg()
    apertado = {**original, "bissecao": {**original["bissecao"], "max_iteracoes": 1, "tol_temperatura": 0.0,
                                         "tol_vazao": 0.0}}
    monkeypatch.setattr(circulacao, "cfg", lambda: apertado)
    rt, est = circulacao.executar(planta_propostas.contexto, "P-002", variante("P-002"))
    assert not est.ok and rt.status == servico.INVIAVEL
    assert "bisseção" in rt.resultado.message and not rt.resultado.feasible


def test_variante_nao_altera_o_calculo_padrao(planta_propostas, estudos):
    """Isolamento: o resultado padrão do TAG é o mesmo antes e depois do estudo (o estudo não
    toca o contexto nem o estado do TAG)."""
    ctx = planta_propostas.contexto
    antes = _base(planta_propostas, "P-002")
    circulacao.executar(ctx, "P-002", variante("P-002"))
    depois = _base(planta_propostas, "P-002")
    assert antes.status == depois.status
    assert (antes.resultado.feasible, antes.resultado.message) == (depois.resultado.feasible,
                                                                   depois.resultado.message)
    assert _mesmo_numero(antes.resultado.x, depois.resultado.x)


def test_p002_viavel_com_circulacao_fixa_e_inviavel_sem_ela(planta_propostas, estudos):
    """O que o estudo mostra: mantida a circulação, o turndown do P-002 deixa de sair da faixa de
    Dittus-Boelter e o TAG passa a ter solução — com a mesma física e os mesmos limites."""
    rt, _ = estudos["P-002"]
    assert _base(planta_propostas, "P-002").status == servico.INVIAVEL
    assert rt.status == servico.DIMENSIONADO and rt.resultado.feasible


def test_busca_aceita_politica_e_variante_de_estudo(planta_propostas):
    """`buscar` sem as opções continua idêntica; com elas, aplica a política de série e a variante
    a cada candidato. Grade reduzida a um candidato."""
    assert ro.politica("P-003") == ro.cfg()["tags"]["P-003"]
    serie = {"divisao": "cascos_serie", "gatilho": "comprimento", "n_cascos_max": 3}
    assert ro.politica("P-003", serie)["divisao"] == "cascos_serie"
    g = {k: [v] for k, v in ro.grade("P-003")[0].items()}
    etapas = ro.buscar(planta_propostas.contexto, "P-003", g, politica_estudo=serie, variante=variante("P-003"))
    c = ro.escolhido(etapas)
    assert "cascos_serie" in c.valores and c.rt.resultado is not None
