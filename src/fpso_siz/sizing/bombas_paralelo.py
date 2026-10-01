"""Operação de bombas físicas em paralelo sobre o contrato genérico de serviço."""
from dataclasses import dataclass

from fpso_siz.sizing.servico import selecionar_operacao


@dataclass(frozen=True)
class LimitesBomba:
    vazao_minima: float | None = None
    potencia_maxima: float | None = None
    npshr: float | None = None


@dataclass(frozen=True)
class ResultadoBombas:
    ativas: int
    vazao_por_unidade: float
    head_requerido: float
    potencia_por_unidade: float
    potencia_operando: float
    potencia_instalada: float
    margem_npsh: float | None


def operar(configuracao, vazao, head, eficiencia, rho, gravidade, npsha,
           capacidade_unidade, limites=LimitesBomba()):
    """Seleciona unidades e verifica limites hidráulicos por unidade.

    A curva/capacidade continua sendo entrada do modelo da bomba; standby não recebe
    vazão nem potência operacional, mas entra na potência instalada.
    """
    if not 0 < eficiencia <= 1 or rho <= 0 or gravidade <= 0 or head < 0:
        raise ValueError("condições hidráulicas inválidas")

    def admissivel(op):
        potencia = rho * gravidade * op.vazao_por_unidade * head / eficiencia
        return ((limites.vazao_minima is None or op.vazao_por_unidade >= limites.vazao_minima)
                and (limites.potencia_maxima is None or potencia <= limites.potencia_maxima)
                and (limites.npshr is None or npsha >= limites.npshr))

    op = selecionar_operacao(configuracao, vazao, vazao, capacidade_unidade, admissivel)
    if op is None:
        return None
    potencia = rho * gravidade * op.vazao_por_unidade * head / eficiencia
    margem = None if limites.npshr is None else npsha - limites.npshr
    return ResultadoBombas(op.ativas, op.vazao_por_unidade, head, potencia,
                           op.ativas * potencia, configuracao.instaladas * potencia, margem)
