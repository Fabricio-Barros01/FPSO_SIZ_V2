"""O caminho PFD normal não pode voltar a deixar DESIGN/RATING como API paralela."""
import json
from pathlib import Path
from fpso_siz.pfd import equipamento
from fpso_siz.pfd.planta import dimensionar


def test_pfd_bot_alcanca_busca_rating_e_propaga_cargas(monkeypatch, planta_base):
    chamadas = {"rating": 0, "busca": 0, "design_p001": 0}
    rating_original = equipamento.rating.rating
    busca_original = equipamento.buscar_layouts
    dimensionar_original = equipamento.dimensionar

    def contar_rating(*args, **kwargs):
        chamadas["rating"] += 1
        return rating_original(*args, **kwargs)

    def contar_busca(*args, **kwargs):
        chamadas["busca"] += 1
        return busca_original(*args, **kwargs)

    def contar_design(entradas, estado=None):
        # a geometria do P-001 é a do rating: nenhum DESIGN refeito sobre o estado pós-rating
        chamadas["design_p001"] += entradas.tag.tag == "P-001"
        return dimensionar_original(entradas, estado)

    monkeypatch.setattr(equipamento.rating, "rating", contar_rating)
    monkeypatch.setattr(equipamento, "buscar_layouts", contar_busca)
    monkeypatch.setattr(equipamento, "dimensionar", contar_design)
    ctx = equipamento.Contexto(planta_base.dados, balanco=planta_base.balanco,
                               propostas=__import__("fpso_siz.pfd.propostas", fromlist=["padrao"]).padrao())
    planta = dimensionar(contexto=ctx)

    p001 = planta.tag("P-001")
    assert chamadas["busca"] == 1 and chamadas["design_p001"] == 0 and p001.resultado is None
    assert chamadas["rating"] >= len(planta.balanco)
    assert chamadas["rating"] % len(planta.balanco) == 0
    assert len(p001.operacao.casos) == len(planta.balanco)
    for op, estado in zip(p001.operacao.casos, planta.balanco_operacional):
        assert estado.duties["Q_pre"] == op.Q_real
        assert estado.duties["Q_H"] == op.q_p002
        assert estado.duties["Q_C"] == op.q_p003
        assert estado.T["C-07"] == op.t_fria_out
        assert estado.T["C-23"] == op.t_quente_out
    operacional = planta.balanco_operacional
    assert planta.tag("P-002").entradas.caso(2).valores["t_casco_in"].valor == operacional[1].T["C-07"]
    assert planta.tag("P-003").entradas.caso(2).valores["t_casco_in"].valor == operacional[1].T["C-23"]
    esperado = json.loads((Path(__file__).parents[1] / "fixtures/pfd/p001_busca_regressao.json").read_text())
    atual = p001.operacao.estrutura()
    assert atual["geometria"] == esperado["geometria"]
    assert atual["criterio_desempate"] == esperado["criterio_desempate"]
    assert [c["Q_real"] for c in atual["casos"]] == esperado["q_real_kW"]
