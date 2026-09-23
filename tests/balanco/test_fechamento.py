"""F2 — fechamento de massa e energia por bloco e global, nos 16 casos."""
from fpso_siz.balanco.balancos import balanco_bloco, balanco_global, balancos_por_bloco, topologia
from fpso_siz.balanco.modelo import COMP, corrente


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


def test_bloco_sem_vazao_nao_divide_por_zero(resultados):
    r = resultados[0]
    streams = dict(r.streams, **{"C-25": corrente(), "C-26": corrente()})
    vazio = type(r)(**{**r.__dict__, "streams": streams})
    b = balanco_bloco(vazio, {"entradas": ["C-26"], "saidas": ["C-25"], "Q_in": [], "Q_out": [], "W": []})
    assert b["em"] == 0.0 and b["eE"] == 0.0
    assert set(b["comp"]) == set(COMP)
