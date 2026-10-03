"""P-001: uma geometria só, do rating ao memorial, e o mesmo estado operacional no TAG isolado e na
planta (docs/validacao/45). Os números da auditoria não são fixados aqui: o que se prova é a
coerência entre resultado, JSON, CSV e memorial e a classificação explícita das restrições."""
import csv
import json

import pytest

from fpso_siz.balanco.balancos import balanco_global, balancos_por_bloco
from fpso_siz.balanco.estado import ETAPA_PRELIMINAR, ETAPA_RATING
from fpso_siz.output import pfd as saida
from fpso_siz.output.latex import formatacao
from fpso_siz.output.latex.tag import memorial as saida_mc
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd.tags import tags


def test_so_p002_e_p003_dependem_do_rating():
    assert {t.tag for t in tags() if servico.depende_do_rating(t)} == {"P-002", "P-003"}


def test_resultado_do_p001_e_a_geometria_do_rating(planta_propostas):
    rt = planta_propostas.tag("P-001")
    op = rt.operacao
    assert rt.resultado is None, "nenhum envelope DESIGN paralelo à geometria do rating"
    assert rt.status == servico.DIMENSIONADO and op.geometria is not None
    assert rt.etapa_balanco == ETAPA_PRELIMINAR
    g, a = op.geometria, op.areas
    assert a["por_unidade_m2"] == g.area_unitaria
    assert a["em_operacao_m2"] == g.duty * g.area_unitaria
    assert a["instalada_m2"] == g.instaladas * g.area_unitaria
    assert g.instaladas == g.duty + g.standby
    # a planta.csv mostra a mesma geometria
    linha = next(li for li in saida.linhas(planta_propostas.tags) if li["tag"] == "P-001")
    assert (linha["x"], linha["y"]) == (g.tubos_por_passe, g.comprimento_tubo)
    assert linha["restricoes"] == "; ".join(rt.restricoes)


def test_p002_p003_recebem_as_cargas_do_estado_operacional(planta_propostas):
    op = planta_propostas.tag("P-001").operacao
    operacional = {r.num: r for r in planta_propostas.balanco_operacional}
    for ident, carga in (("P-002", "q_p002"), ("P-003", "q_p003")):
        rt = planta_propostas.tag(ident)
        assert rt.etapa_balanco == ETAPA_RATING
        for c in op.casos:
            r = operacional[c.num]
            assert r.etapa == ETAPA_RATING
            assert getattr(c, carga) == r.duties["Q_H" if ident == "P-002" else "Q_C"]
            # o preliminar continua identificado e preservado ao lado
            assert c.preliminar["Q_H_kW"] == r.antes_do_rating["duties"]["Q_H"]
            assert c.preliminar["Q_C_kW"] == r.antes_do_rating["duties"]["Q_C"]
            assert c.Q_Pinch == r.antes_do_rating["duties"]["Q_pre"]


def test_estado_operacional_fecha_massa_e_energia(planta_propostas):
    """Com o Q_real do rating, cada bloco e a fronteira fecham como no balanço preliminar."""
    for r in planta_propostas.balanco_operacional:
        g = balanco_global(r)
        assert g["em"] < 1e-12 and g["eE"] < 1e-12, r.num
        for bloco, b in balancos_por_bloco(r).items():
            assert b["em"] < 1e-12 and b["eE"] < 1e-12, (r.num, bloco)


def test_tag_isolado_le_o_mesmo_estado_que_a_planta(planta_propostas):
    """`dimensionar --tag P-002` não pode cair no balanço preliminar por ignorar o P-001."""
    ctx = servico.Contexto(planta_propostas.dados, balanco=planta_propostas.balanco,
                           propostas=planta_propostas.contexto.propostas)
    for ident in ("P-002", "P-003"):
        rt = servico.executar(ctx, servico.estado_inicial(ident))
        ref = planta_propostas.tag(ident)
        assert rt.etapa_balanco == ref.etapa_balanco == ETAPA_RATING
        for a, b in zip(rt.entradas.casos, ref.entradas.casos):
            assert {k: v.valor for k, v in a.valores.items()} == {k: v.valor for k, v in b.valores.items()}
        assert (rt.resultado.x, rt.resultado.y) == (ref.resultado.x, ref.resultado.y)


def test_json_csv_e_memorial_concordam(planta_propostas, tmp_path):
    ctx, rt = planta_propostas.contexto, planta_propostas.tag("P-001")
    op = rt.operacao
    saida.gravar_tag(ctx, rt, tmp_path)
    js = json.loads((tmp_path / "P-001.json").read_text(encoding="utf-8"))
    assert js["envelope"] is None and js["restricoes"] == rt.restricoes
    assert js["operacao_integrada"] == op.estrutura() == mc.documento(ctx, rt)["operacao_integrada"]
    with (tmp_path / "P-001_operacao.csv").open(encoding="utf-8", newline="") as f:
        linhas = {int(li["num"]): li for li in csv.DictReader(f)}
    tex = saida_mc.gerar(ctx, rt, "02/10/2026", ("0123456789ab", False))[1]
    g = op.geometria
    for valor in (g.tubos_por_passe, g.comprimento_tubo, op.areas["em_operacao_m2"], op.areas["instalada_m2"]):
        assert formatacao.sigt(valor) in tex
    for num in sorted({3, op.caso_projeto}):
        c, li = op.caso(num), linhas[num]
        pares = (("Q_preliminar_kW", c.Q_Pinch), ("Q_apos_rating_kW", c.Q_real),
                 ("T_C07_preliminar_C", c.preliminar["T_C07"]), ("T_C07_apos_rating_C", c.t_fria_out),
                 ("Q_P002_preliminar_kW", c.preliminar["Q_H_kW"]), ("Q_P002_apos_rating_kW", c.q_p002),
                 ("Q_P003_preliminar_kW", c.preliminar["Q_C_kW"]), ("Q_P003_apos_rating_kW", c.q_p003))
        for coluna, valor in pares:
            assert float(li[coluna]) == pytest.approx(valor, rel=1e-12), (num, coluna)
            assert formatacao.sigt(valor) in tex, (num, coluna)


def test_ausencias_e_restricoes_sao_explicitas(planta_propostas):
    rt = planta_propostas.tag("P-001")
    est = rt.operacao.estrutura()
    der = est["geometria_derivada"]
    # diâmetro em mm (o avaliador devolve metros): casco = feixe + 2·d_o
    assert der["diametro_casco_mm"] - der["diametro_feixe_mm"] == pytest.approx(
        2 * est["geometria"]["diametro_externo_mm"])
    for c in est["casos"]:
        # só a ausência de vazão torna a hidráulica não aplicável; carga térmica nula não (nota 46)
        if c["papel"] == servico.SEM_VAZAO:
            assert c["hidraulico"]["atendimento"] == servico.NAO_APLICAVEL and c["hidraulico"]["motivo"]
            continue
        assert c["diagnosticos"]["diametro_casco_mm"] == der["diametro_casco_mm"]
        criterios = {k["criterio"]: k for k in c["hidraulico"]["criterios"]}
        for k in criterios.values():
            if k["valor"] is None:
                assert k["status"] in (servico.NAO_AVALIADO, servico.NAO_APLICAVEL) and k["motivo"], \
                    (c["num"], k["criterio"])
            if k["status"] == servico.ATENDE:
                assert k["valor"] is not None
        # P-45: piso de velocidade reprova só no caso de projeto; no turndown é alerta
        piso = criterios["velocidade_minima_tubo"]
        esperado = ({servico.ATENDE, servico.NAO_ATENDE} if c["papel"] == servico.PROJETO
                    else {servico.ATENDE, servico.ALERTA})
        assert piso["status"] in esperado
    av = est["avaliacao"]
    geo = {r["criterio"]: r for r in av["restricoes_geometricas"]}
    # acima do limite: reprova se for limite do projeto; decisão pendente se for default do método
    acima = geo["comprimento_tubo"]["valor"] > geo["comprimento_tubo"]["limite"]
    assert (geo["comprimento_tubo"]["status"] in (servico.NAO_ATENDE, servico.DECISAO_PENDENTE)) == acima
    assert av["restricoes"] == rt.restricoes and av["decisoes_pendentes"] == rt.decisoes_pendentes
    assert (av["situacao"] == "com_restricoes") == bool(av["restricoes"])


def test_sem_geometria_e_diagnostico_com_termino_normal(planta_propostas, monkeypatch):
    """Nenhum candidato admissível: o P-001 fica inviável com mensagem, e os dependentes seguem
    do balanço preliminar, identificado como tal."""
    monkeypatch.setattr(servico, "buscar_layouts", lambda *a, **k: ())
    ctx = servico.Contexto(planta_propostas.dados, balanco=planta_propostas.balanco,
                           propostas=planta_propostas.contexto.propostas)
    rt = servico.executar(ctx, servico.estado_inicial("P-001"))
    assert rt.status == servico.INVIAVEL and rt.operacao.mensagem and rt.resultado is None
    assert rt.operacao.avaliacao()["situacao"] == "inviavel"
    p002 = servico.executar(ctx, servico.estado_inicial("P-002"))
    assert p002.etapa_balanco == ETAPA_PRELIMINAR
