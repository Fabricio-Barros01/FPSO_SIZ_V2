"""Contrato genérico de multiplicidade de unidades físicas (ADR 0005).

É o contrato que `pfd/layout.py` usa para separar duty simultâneo de reserva INSTALADA na
busca de layout do trocador: a reserva conta na área instalada e não recebe carga. Nenhum TAG
de BOMBA usa este contrato ainda — isso é pendência declarada no SPRINTS.md, não entrega.
"""
import pytest

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
