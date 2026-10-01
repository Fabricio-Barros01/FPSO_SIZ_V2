import pytest

from fpso_siz.sizing.bombas_paralelo import LimitesBomba, operar
from fpso_siz.sizing.servico import ConfiguracaoServico, configuracoes, selecionar_operacao


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
