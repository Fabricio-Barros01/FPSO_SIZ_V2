"""Busca discreta de layout do pré-aquecedor (ADR 0005; docs/validacao/43).

A busca inteira é caríssima (é ferramenta, `tools/buscar_layout_trocador.py`); o que a suíte
cobra aqui é o CONTRATO dela: os eixos são declarados com fonte, a avaliação de um candidato é
o caminho produtivo inteiro, a viabilidade só é declarada com o conjunto integrado, a frente de
Pareto é física e a regra de seleção é a declarada.
"""
import math

import pytest

from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import layout
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.tags import tag
from fpso_siz.sizing.servico import ConfiguracaoServico


@pytest.fixture(scope="module")
def ctx(planta_base):
    return servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                            propostas=mod_propostas.padrao())


@pytest.fixture(scope="module")
def registrada():
    """A geometria REGISTRADA no TAG: especificação vazia, porque é o próprio catálogo."""
    return layout.Especificacao(())


def test_cada_eixo_tem_rotulo_fonte_e_valores_do_descritor():
    """Nenhum valor de eixo pode estar fora da faixa que a fonte do descritor declara."""
    c = layout.cfg()
    specs = servico.especificacoes_de(tag(c["tag"]).equipamento, tag(c["tag"]).metodo)
    assert c["tag"] and c["tags_integrados"] and c["fonte"]
    for chave, eixo in c["eixo"].items():
        assert eixo["rotulo"] and eixo["fonte"] and eixo["valores"]
        if chave in layout.EIXOS_DE_SERVICO:
            continue
        s = specs[chave]
        assert all(s.min <= v <= s.max for v in eixo["valores"]), (chave, s.min, s.max)


def test_verificacoes_finais_sao_premissas_do_balanco(ctx):
    for v in layout.cfg()["verificacao_final"]:
        assert v["premissa"] in ctx.prem and v["sentido"] in ("minimo", "maximo")
        assert v["corrente"] and v["rotulo"] and v["fonte"]


def test_comprimento_de_tubo_vai_de_6_a_9_m():
    """Faixa pedida pelo usuário em 2026-10-02, com a fonte registrada no eixo."""
    assert layout.eixos()["l_tubo_max"] == [6.0, 7.0, 8.0, 9.0]


def test_a_reserva_instalada_e_exigida_e_nao_recebe_carga():
    exigida = layout.reserva_exigida()
    assert exigida >= 1
    confs = list(layout.configuracoes_de_servico(2))
    assert ConfiguracaoServico(3, 2, 1, 0.5) in confs
    com_reserva = next(c for c in confs if c.standby >= exigida)
    assert com_reserva.instaladas == com_reserva.duty_projeto + com_reserva.standby
    totais = com_reserva.totais_extensivos(100.0, com_reserva.duty_projeto)
    assert totais["operando"] == 100.0 * com_reserva.duty_projeto
    assert totais["instalado"] == 100.0 * com_reserva.instaladas


def test_candidatos_cobrem_o_produto_dos_eixos():
    eixos = layout.eixos()
    esperado = math.prod(len(v) for v in eixos.values())
    assert len(layout.especificacoes()) == esperado
    assert all(set(dict(e.valores)) == set(eixos) for e in layout.especificacoes())


def test_geometria_registrada_e_viavel_no_conjunto_integrado(ctx, registrada):
    """A geometria que o TAG registra tem de passar por TUDO: rating avaliável em todos os
    casos, aquecedor e resfriador dimensionados com as cargas residuais, temperaturas finais da
    ET alcançadas e a reserva que a ET exige."""
    conf = next(c for c in layout.configuracoes_de_servico(1)
                if c.standby >= layout.reserva_exigida())
    av = layout.avaliar(ctx, registrada, conf)
    assert av.viavel, av.motivo
    assert av.geometria.integracao.convergiu
    assert all(v.atende for v in av.verificacoes)
    assert all(rt.concluido for rt in av.geometria.residuais.values())
    assert 0 < av.fracao_realizada <= 1
    assert av.area_instalada == conf.instaladas * av.geometria.area_unitaria
    assert av.area_operacional < av.area_instalada   # a reserva não opera


def test_sem_a_reserva_a_et_reprova(ctx, registrada):
    sem = next(c for c in layout.configuracoes_de_servico(1) if c.standby == 0)
    av = layout.avaliar(ctx, registrada, sem)
    assert not av.viavel and "reserva" in av.motivo
    assert av.geometria is not None   # a física foi avaliada; o que reprova é a filosofia


def test_viabilidade_exige_o_conjunto_nao_so_o_recuperador(ctx, registrada):
    """Mesmo com o pré-aquecedor dimensionado, um aquecedor que não fecha com a carga residual
    reprova o candidato: a declaração de viabilidade é do conjunto."""
    conf = next(c for c in layout.configuracoes_de_servico(1)
                if c.standby >= layout.reserva_exigida())
    residual = layout.cfg()["tags_integrados"][0]
    est = servico.estado_inicial(residual)
    est.editar("l_tubo_max", 0.5)   # nenhum feixe do aquecedor cabe nisso
    ctx.fixar_estado(est)
    av = layout.avaliar(ctx, registrada, conf)
    ctx.ajustes.tags.pop(residual, None)
    ctx.fixar_estado(servico.estado_inicial(layout.cfg()["tag"]))
    assert not av.viavel and residual in av.motivo


def _falso(area, qh, qc, recuperacao, cascos):
    conf = ConfiguracaoServico(2, 1, 1, 1.0)
    geo = layout.Geometria(layout.Especificacao(()), 10.0, 6.0, cascos, 1000.0, area / 2,
                           (layout.CasoAvaliado(1, "c", True, "x", True, "", 100.0, recuperacao,
                                                qh, qc, 1.0, 1.0, 1e4, 300.0, False),))
    return layout.Avaliacao(geo.especificacao, conf, True, "", geo)


def test_frente_de_pareto_e_fisica():
    """Área instalada, utilidade quente e utilidade fria; nenhum dado econômico."""
    a = _falso(100.0, 10.0, 10.0, 90.0, 2)     # domina b
    b = _falso(200.0, 20.0, 20.0, 80.0, 2)
    c = _falso(400.0, 5.0, 5.0, 95.0, 4)       # não dominado: gasta área, poupa utilidade
    f = layout.frente([a, b, c])
    assert a in f and c in f and b not in f


def test_as_duas_regras_de_selecao_estao_declaradas_e_sao_diferentes():
    """A troca entre área instalada e recuperação é decisão de projeto: as duas leituras estão
    declaradas no TOML e escolhem candidatos DIFERENTES na mesma frente."""
    assert layout.cfg()["selecao"]["regra"] in layout.REGRAS
    assert layout.cfg()["selecao"]["fonte"].strip()
    barato = _falso(100.0, 10.0, 10.0, 90.0, 2)    # 1,11 m²/kW
    caro = _falso(400.0, 5.0, 5.0, 95.0, 4)        # 4,21 m²/kW, mas recupera mais
    f = layout.frente([barato, caro])
    assert set(f) == {barato, caro}
    assert layout.selecionar(f, "area_especifica") is barato
    assert layout.selecionar(f, "maior_recuperacao") is caro
    assert layout.area_especifica(barato) < layout.area_especifica(caro)


def test_candidato_sem_recuperacao_nao_ganha_por_divisao_por_zero():
    vazio = _falso(100.0, 10.0, 10.0, 0.0, 2)
    assert layout.area_especifica(vazio) == math.inf


def test_selecionar_sem_viavel_devolve_nada():
    assert layout.selecionar([]) is None
    assert layout.frente([]) == []
