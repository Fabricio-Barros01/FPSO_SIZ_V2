import pytest

from fpso_siz.sizing.bombas_paralelo import LimitesBomba, operar
from types import SimpleNamespace

from fpso_siz.sizing.servico import (ConfiguracaoServico, buscar_layouts, configuracoes,
                                      frente_pareto, selecionar_operacao)


@pytest.mark.parametrize("cfg", [
    ConfiguracaoServico(1, 1, 0, 1.0),
    ConfiguracaoServico(2, 2, 0, 0.5),
    ConfiguracaoServico(3, 2, 1, 0.5),
    ConfiguracaoServico(2, 1, 1, 1.0),
])
def test_filosofias_explicitas_e_somatorios(cfg):
    totais = cfg.totais_extensivos(10.0, cfg.duty_projeto)
    assert totais["operando"] == 10.0 * cfg.duty_projeto
    assert totais["instalado"] == 10.0 * cfg.instaladas


def test_turndown_escolhe_menos_unidades():
    cfg = ConfiguracaoServico(3, 2, 1, 0.5)
    assert selecionar_operacao(cfg, 20.0, 20.0, 100.0).ativas == 1
    assert selecionar_operacao(cfg, 20.0, 150.0, 100.0).ativas == 2


def test_busca_nao_confunde_redundancia_e_paralelo():
    cs = tuple(configuracoes(3))
    assert ConfiguracaoServico(2, 1, 1, 1.0) in cs
    assert ConfiguracaoServico(2, 2, 0, 0.5) in cs
    assert ConfiguracaoServico(3, 2, 1, 0.5) in cs


def test_bomba_distingue_duty_de_standby_e_npsh():
    cfg = ConfiguracaoServico(2, 1, 1, 1.0)
    r = operar(cfg, 0.1, 20.0, 0.8, 1000.0, 9.81, 5.0, 0.2,
              LimitesBomba(vazao_minima=0.05, npshr=4.0))
    assert r.ativas == 1
    assert r.potencia_instalada == pytest.approx(2 * r.potencia_por_unidade)
    assert r.margem_npsh == 1.0


def test_layout_separa_energia_pico_area_duty_e_reserva_instalada():
    cfg = ConfiguracaoServico(3, 2, 1, 0.5, reserva_minima=1)
    geometria = SimpleNamespace(area_unitaria=10.0)
    casos = (
        SimpleNamespace(nome="A", admissivel=True, recuperacao=8.0, alvo_pinch=10.0,
                        utilidade_quente=2.0, utilidade_fria=7.0,
                        margens_restricoes={"velocidade_maxima": 0.2}),
        SimpleNamespace(nome="B", admissivel=True, recuperacao=9.0, alvo_pinch=10.0,
                        utilidade_quente=6.0, utilidade_fria=3.0,
                        margens_restricoes={"velocidade_maxima": 0.1}),
    )
    (layout,) = buscar_layouts((cfg,), (object(),), casos,
        lambda configuracao, especificacao, todos: geometria,
        lambda configuracao, geometria, caso: caso)
    assert layout.recuperacao_total == 17.0
    assert layout.recuperacao_por_caso == (8.0, 9.0)
    assert layout.fracao_alvo_pinch == 0.85
    assert layout.fracao_alvo_pinch_por_caso == (0.8, 0.9)
    assert layout.area_unitaria == 10.0 and layout.area_duty == 20.0
    assert layout.area_total_instalada == 30.0
    assert layout.utilidade_quente == 8.0 and layout.demanda_maxima_utilidade_quente == 6.0
    assert layout.utilidade_fria == 10.0 and layout.demanda_maxima_utilidade_fria == 7.0
    assert layout.casos_governantes["velocidade_maxima"] == "B"
    assert layout.margens_restricoes["reserva_et"] == (0, 0)


def test_pareto_nao_compensa_pico_quente_com_utilidade_fria():
    cfg = ConfiguracaoServico(2, 1, 1, 1.0, reserva_minima=1)

    def layout(quente, fria):
        casos = (SimpleNamespace(admissivel=True, recuperacao=1.0, alvo_pinch=1.0,
                                 utilidade_quente=quente, utilidade_fria=fria),)
        return buscar_layouts((cfg,), (object(),), casos,
            lambda configuracao, especificacao, todos: SimpleNamespace(area_unitaria=1.0),
            lambda configuracao, geometria, caso: caso)[0]

    quente_alto = layout(10.0, 0.0)
    frio_alto = layout(0.0, 10.0)
    frente = frente_pareto((quente_alto, frio_alto))
    assert quente_alto in frente and frio_alto in frente


def test_reserva_declarada_faz_parte_da_admissibilidade():
    with pytest.raises(ValueError, match="reserva mínima"):
        ConfiguracaoServico(2, 2, 0, 0.5, reserva_minima=1)
