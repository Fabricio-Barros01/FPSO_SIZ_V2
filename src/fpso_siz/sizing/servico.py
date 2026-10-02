"""Serviço lógico e unidades físicas, independente da física do equipamento.

Esta camada não interpreta sufixos A/B/C. A filosofia (instaladas, duty, standby e
fração por unidade) é sempre dado explícito e pode ser compartilhada por trocadores,
bombas e futuros equipamentos.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracaoServico:
    instaladas: int
    duty_projeto: int
    standby: int
    fracao_nominal: float
    minimo_ativas: int = 1

    def __post_init__(self):
        if self.instaladas < 1 or self.duty_projeto < 1:
            raise ValueError("o serviço precisa de ao menos uma unidade instalada e duty")
        if self.standby < 0 or self.duty_projeto + self.standby != self.instaladas:
            raise ValueError("instaladas deve ser igual a duty_projeto + standby")
        if not 0 < self.fracao_nominal <= 1:
            raise ValueError("a fração nominal por unidade deve estar em (0, 1]")
        if not 1 <= self.minimo_ativas <= self.duty_projeto:
            raise ValueError("número mínimo de unidades ativas inválido")

    def capacidades(self):
        """Números admissíveis de unidades ativas, do menor ao duty de projeto."""
        return tuple(range(self.minimo_ativas, self.duty_projeto + 1))

    def totais_extensivos(self, valor_unitario, ativas):
        if ativas not in self.capacidades():
            raise ValueError("número de unidades ativas fora da política do serviço")
        return {
            "unitario": valor_unitario,
            "operando": ativas * valor_unitario,
            "instalado": self.instaladas * valor_unitario,
        }


@dataclass(frozen=True)
class OperacaoUnidades:
    ativas: int
    vazao_por_unidade: float
    carga_por_unidade: float
    capacidade_disponivel: float


def selecionar_operacao(configuracao, vazao, carga, capacidade_unidade, admissivel=None):
    """Escolhe o menor número admissível de unidades, favorecendo Reynolds no turndown.

    ``admissivel`` recebe a operação candidata e aplica limites próprios da física do
    equipamento (velocidade/Re para trocador; curva/NPSH/vazão mínima para bomba).
    """
    if vazao < 0 or carga < 0 or capacidade_unidade <= 0:
        raise ValueError("vazão, carga e capacidade devem ser fisicamente válidas")
    for ativas in configuracao.capacidades():
        op = OperacaoUnidades(ativas, vazao / ativas, carga / ativas,
                              ativas * capacidade_unidade)
        if carga <= op.capacidade_disponivel and (admissivel is None or admissivel(op)):
            return op
    return None


def configuracoes(instaladas_maximas):
    """Gera filosofias distintas; redundância nunca é confundida com duty simultâneo."""
    for instaladas in range(1, instaladas_maximas + 1):
        for duty in range(1, instaladas + 1):
            yield ConfiguracaoServico(instaladas, duty, instaladas - duty, 1 / duty)


@dataclass(frozen=True)
class CandidatoLayout:
    configuracao: ConfiguracaoServico
    geometria: object
    casos: tuple
    area_unitaria: float
    utilidade_quente: float
    utilidade_fria: float

    @property
    def recuperacao(self):
        return sum(getattr(c, "recuperacao", 0.0) for c in self.casos)

    @property
    def area_instalada(self):
        return self.configuracao.instaladas * self.area_unitaria


def buscar_layouts(configuracoes_admissiveis, geometrias, casos, design, avaliar):
    """Busca discreta genérica DESIGN → RATING → envelope.

    Os callbacks mantêm a física em seu método: ``design`` materializa a geometria;
    ``avaliar`` seleciona unidades, faz rating e devolve, para cada caso, um objeto com
    ``admissivel``, ``utilidade_quente`` e ``utilidade_fria``.
    """
    aceitos = []
    for configuracao in configuracoes_admissiveis:
        for especificacao in geometrias:
            geometria = design(configuracao, especificacao, casos)
            resultados = tuple(avaliar(configuracao, geometria, caso) for caso in casos)
            if resultados and all(r.admissivel for r in resultados):
                aceitos.append(CandidatoLayout(
                    configuracao, geometria, resultados, geometria.area_unitaria,
                    sum(r.utilidade_quente for r in resultados),
                    sum(r.utilidade_fria for r in resultados)))
    return tuple(aceitos)


def frente_pareto(candidatos):
    """Frente física (recuperação máxima, área e utilidades mínimas), sem custos."""
    def domina(a, b):
        va = (-a.recuperacao, a.area_instalada, a.utilidade_quente + a.utilidade_fria)
        vb = (-b.recuperacao, b.area_instalada, b.utilidade_quente + b.utilidade_fria)
        return all(x <= y for x, y in zip(va, vb)) and any(x < y for x, y in zip(va, vb))

    return tuple(c for c in candidatos if not any(domina(outro, c) for outro in candidatos if outro is not c))
