"""Fase C (docs/validacao/46): geometria congelada, violações reportadas por natureza, refino local
da grade e ΔP do lado casco no caminho produtivo.

Geometria congelada = `l_instalado` > 0 com `n_min = n_max`: nenhum caso dimensiona, TODOS são
classificados no feixe dado. Com o feixe que a produção escolheu, isso tem de reproduzir o rating
da produção — é a prova de que congelar não muda a física, só quem dimensiona.
"""
import math

import pytest

from fpso_siz.core import memoria
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import integracao_termica as itg


def congelar(ctx, ident, r, **extra):
    est = servico.estado_inicial(ident)
    for k, v in {"n_min": r.x, "n_max": r.x, "n_step": 1.0, "l_instalado": r.y, **extra}.items():
        est.editar(k, float(v))
    return est


@pytest.fixture(scope="module")
def p001(planta_propostas):
    return planta_propostas.tag("P-001").resultado


def test_congelar_a_geometria_da_producao_reproduz_o_rating(planta_propostas, p001):
    ctx = planta_propostas.contexto
    est = congelar(ctx, "P-001", p001)
    r = servico.dimensionar(servico.preparar(ctx, est), est).resultado
    assert r.feasible and r.x == p001.x and r.y == pytest.approx(p001.y, rel=1e-12)
    v2, v0 = r.derivados_v2, p001.derivados_v2
    assert v2["geometria_congelada"] == 1.0
    # o caso de projeto, que dimensionava, agora é classificado e realiza a sua carga inteira
    assert v2["fracao_realizada_por_caso"] == pytest.approx(v0["fracao_realizada_por_caso"], abs=1e-9)
    assert v2["area_total"] == pytest.approx(v0["area_total"], rel=1e-12)


def test_violacoes_sao_reportadas_e_nao_recusam_o_feixe_congelado(planta_propostas, p001):
    """Com o teto de velocidade abaixo da do feixe, o feixe congelado continua classificado: a
    violação aparece por caso, com a natureza (hidráulica), e não some numa recusa genérica."""
    ctx = planta_propostas.contexto
    est = congelar(ctx, "P-001", p001, v_max=0.5)
    r = servico.dimensionar(servico.preparar(ctx, est), est).resultado
    assert r.feasible
    op = [o for _, o in memoria.operacao(r)]
    assert all(any(nat == "hidraulica" and "teto" in t for nat, t in o["violacoes"]) for o in op)
    assert all(o["rating"]["estado"] for o in op)


def test_dp_do_casco_no_caminho_produtivo(planta_propostas):
    """A ΔP do casco é calculada para os três trocadores e reportada por caso; sem limite
    declarado (`dp_max_casco = 0`) ela não aprova nem reprova (nota 46: as geometrias registradas
    passam da P-17 no casco, e a consolidação é decisão do usuário)."""
    for ident in ("P-001", "P-002", "P-003"):
        r = planta_propostas.tag(ident).resultado
        dps = r.derivados_v2["dp_casco_por_caso"]
        assert dps and all(math.isfinite(x) and x > 0 for x in dps), ident
        assert r.derivados["dp_max_casco"] == 0.0


@pytest.mark.parametrize("ident", ["P-002", "P-003"])
def test_limite_do_casco_cobrado_em_todos_os_casos_no_comprimento_instalado(planta_propostas, ident):
    """Regra do Julia (todo caso dimensiona) com limite de ΔP no casco: o feixe aceito respeita o
    limite em TODOS os casos, no comprimento instalado — não só no governante, no comprimento que
    ele pediria sozinho (era o furo que deixava 534 kPa passar como viável na busca residual)."""
    ctx = planta_propostas.contexto
    est = servico.estado_inicial(ident)
    for k, v in {"dp_max_casco": 100.0, "espacamento_chicana": 1.0, "cascos_serie": 1.0}.items():
        est.editar(k, v)
    r = servico.dimensionar(servico.preparar(ctx, est), est).resultado
    if not r.feasible:
        return
    op = [o for _, o in memoria.operacao(r)]
    assert all(o["dp_casco_validado"] and o["dp_casco"] <= 100.0 for o in op)


def test_refino_local_nunca_piora_a_area(planta_propostas):
    ctx = planta_propostas.contexto
    base = planta_propostas.tag("P-002").resultado
    est = servico.estado_inicial("P-002")
    est.editar("refino_local", 1.0)
    r = servico.dimensionar(servico.preparar(ctx, est), est).resultado
    assert r.feasible and r.derivados["area"] <= base.derivados["area"]
    assert abs(r.x - base.x) < 5    # dentro dos vizinhos da grade de passo 5


def test_integracao_da_producao_e_valida(planta_propostas):
    i = planta_propostas.contexto.integracao
    assert i.valida and i.cenario == itg.REALIZADA
