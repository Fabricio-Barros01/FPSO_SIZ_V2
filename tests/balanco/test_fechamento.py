"""F2 — fechamento de massa e energia por bloco e global, nos 16 casos."""
import dataclasses

from fpso_siz.balanco.balancos import balanco_bloco, balanco_global, balancos_por_bloco, topologia
from fpso_siz.balanco.dados import premissas
import pytest

from fpso_siz.balanco.estado import ETAPA_PRELIMINAR, ETAPA_RATING
from fpso_siz.balanco.modelo import CARGAS_RATING, COMP, CORRENTES_RATING, aplicar_rating_termico, corrente


def test_topologia_16_blocos_26_correntes():
    t = topologia()
    assert len(t["blocos"]) == 16 and len(t["correntes"]) == 26
    ids = {c["id"] for c in t["correntes"]}
    for b in t["blocos"]:
        assert set(b["entradas"]) | set(b["saidas"]) <= ids


def test_cada_bloco_fecha_massa_e_energia(resultados):
    for r in resultados:
        for bid, b in balancos_por_bloco(r).items():
            assert b["em"] < 1e-12, (r.num, bid)
            assert b["eE"] < 1e-12, (r.num, bid)
            # M-01 carrega o resíduo do laço de reciclo (C-02 é da iteração anterior)
            lim = 1e-9 if bid == "M-01" else 1e-10
            assert all(abs(v) < lim for v in b["comp"].values()), (r.num, bid, b["comp"])


def test_fechamento_global(resultados):
    for r in resultados:
        g = balanco_global(r)
        assert g["em"] < 1e-12 and g["eE"] < 1e-12, r.num
        assert g["W"] == r.duties["W_Bo"] + r.duties["W_B1"] + r.duties["W_B2"]


def test_segunda_etapa_termica_fecha_energia_em_cada_caso(resultados, dados):
    """Uma recuperação física menor redistribui energia para as duas utilidades."""
    prem = premissas(dados)
    for original in resultados:
        realizado = aplicar_rating_termico(original, original.duties["Q_pre"] / 2, prem)
        assert balanco_global(realizado)["eE"] < 1e-12, original.num
        for bloco in ("P-001", "P-002", "P-003"):
            assert balancos_por_bloco(realizado)[bloco]["eE"] < 1e-12, (original.num, bloco)
        assert realizado.trace.passo("carga_preaquecedor", "P-001").valor == realizado.duties["Q_pre"]
        assert realizado.trace.passo("carga_aquecedor", "P-002").valor == realizado.duties["Q_H"]
        assert realizado.trace.passo("carga_resfriador", "P-003").valor == realizado.duties["Q_C"]


def test_segunda_etapa_preserva_o_preliminar_e_so_muda_o_declarado(resultados, dados):
    """O estado pós-rating identifica a etapa, guarda o preliminar que substituiu e não toca em
    massa, pressão nem nas temperaturas fora de CORRENTES_RATING; refazer sobre ele é recusado."""
    prem = premissas(dados)
    for original in resultados:
        assert original.etapa == ETAPA_PRELIMINAR and original.antes_do_rating == {}
        realizado = aplicar_rating_termico(original, original.duties["Q_pre"] / 2, prem)
        assert realizado.etapa == ETAPA_RATING
        assert realizado.antes_do_rating == {"T": {k: original.T[k] for k in CORRENTES_RATING},
                                        "duties": {k: original.duties[k] for k in CARGAS_RATING}}
        assert realizado.streams == original.streams and realizado.P == original.P
        assert {k for k in original.T if original.T[k] != realizado.T[k]} <= set(CORRENTES_RATING)
        assert {k for k in original.duties if original.duties[k] != realizado.duties[k]} <= set(CARGAS_RATING)
        with pytest.raises(ValueError):
            aplicar_rating_termico(realizado, 0.0, prem)


def test_bloco_sem_vazao_nao_divide_por_zero(resultados):
    r = resultados[0]
    streams = dict(r.streams, **{"C-25": corrente(), "C-26": corrente()})
    vazio = dataclasses.replace(r, streams=streams)
    b = balanco_bloco(vazio, {"entradas": ["C-26"], "saidas": ["C-25"], "Q_in": [], "Q_out": [], "W": []})
    assert b["em"] == 0.0 and b["eE"] == 0.0
    assert set(b["comp"]) == set(COMP)


def test_reciclo_convergiu_abaixo_da_tolerancia(resultados):
    for r in resultados:
        assert r.iters < 499
        assert r.residuo_reciclo < 1e-10


def test_convergiu_explicito(resultados):
    assert all(r.convergiu for r in resultados)


def test_sem_convergencia_e_sinalizado(dados, monkeypatch):
    import dataclasses
    from types import MappingProxyType

    from fpso_siz.balanco import modelo

    const = modelo.constantes()
    curto = dataclasses.replace(const, numerico=MappingProxyType({**const.numerico, "reciclo_max_iter": 2}))
    monkeypatch.setattr(modelo, "constantes", lambda: curto)
    r = modelo.resolver_caso(dados.caso(8), dados)
    assert r.iters == 1
    monkeypatch.undo()
    assert not r.convergiu and r.residuo_reciclo > 1e-10


def test_capacidade_e_volume(resultados):
    r = resultados[7]
    s = r.streams["C-21"]
    assert r.C(s) == sum(s[c] * r.cp[c] for c in "OWDG")
    assert r.vol(s, "O") == s["O"] / r.rho["O"] / (1 / 86400)
    assert r.H(s, r.T_ref) == 0.0
