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
    reserva_minima: int = 0

    def __post_init__(self):
        if self.instaladas < 1 or self.duty_projeto < 1:
            raise ValueError("o serviço precisa de ao menos uma unidade instalada e duty")
        if self.reserva_minima < 0:
            raise ValueError("a reserva mínima não pode ser negativa")
        if self.standby < 0 or self.duty_projeto + self.standby != self.instaladas:
            raise ValueError("instaladas deve ser igual a duty_projeto + standby")
        if not 0 < self.fracao_nominal <= 1:
            raise ValueError("a fração nominal por unidade deve estar em (0, 1]")
        if not 1 <= self.minimo_ativas <= self.duty_projeto:
            raise ValueError("número mínimo de unidades ativas inválido")
        if self.standby < self.reserva_minima:
            raise ValueError("a configuração não atende à reserva mínima declarada")

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
    recuperacao_total: float
    recuperacao_por_caso: tuple
    fracao_alvo_pinch: float
    fracao_alvo_pinch_por_caso: tuple
    area_duty: float
    area_total_instalada: float
    demanda_maxima_utilidade_quente: float
    perfil_utilidade_quente: tuple
    demanda_maxima_utilidade_fria: float
    perfil_utilidade_fria: tuple
    casos_governantes: dict
    margens_restricoes: dict

    @property
    def recuperacao(self):
        """Nome histórico mantido para consumidores que leem a recuperação agregada."""
        return self.recuperacao_total

    @property
    def area_instalada(self):
        """A área instalada inclui duty e standby, mesmo sem operação simultânea."""
        return self.area_total_instalada

    @property
    def utilidade_quente(self):
        """Energia agregada dos casos; não é capacidade instalada."""
        return sum(self.perfil_utilidade_quente)

    @property
    def utilidade_fria(self):
        """Energia agregada dos casos; não é capacidade instalada."""
        return sum(self.perfil_utilidade_fria)


def _margens_e_governantes(configuracao, resultados):
    """Consolida margens assinadas (atende quando >= 0) e seu caso governante."""
    por_restricao = {"reserva_et": tuple(configuracao.standby - configuracao.reserva_minima
                                           for _ in resultados)}
    for i, resultado in enumerate(resultados):
        margens = getattr(resultado, "margens_restricoes", getattr(resultado, "margens", {}))
        for nome, valor in margens.items():
            por_restricao.setdefault(nome, [None] * len(resultados))[i] = valor
    governantes = {}
    for nome, margens in por_restricao.items():
        validas = [(i, margem) for i, margem in enumerate(margens) if margem is not None]
        if validas:
            indice, _ = min(validas, key=lambda item: item[1])
            governantes[nome] = getattr(resultados[indice], "nome", indice)
        por_restricao[nome] = tuple(margens)
    return governantes, por_restricao


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
            if resultados and all(r.admissivel and getattr(r, "avaliavel", True) for r in resultados):
                recuperacoes = tuple(getattr(r, "recuperacao", 0.0) for r in resultados)
                alvos = tuple(getattr(r, "alvo_pinch", getattr(r, "Q_Pinch", q))
                              for r, q in zip(resultados, recuperacoes))
                quentes = tuple(r.utilidade_quente for r in resultados)
                frias = tuple(r.utilidade_fria for r in resultados)
                recuperacao_total = sum(recuperacoes)
                alvo_total = sum(alvos)
                governantes, margens = _margens_e_governantes(configuracao, resultados)
                indice_quente = max(range(len(quentes)), key=quentes.__getitem__)
                indice_frio = max(range(len(frias)), key=frias.__getitem__)
                governantes.update(
                    utilidade_quente=getattr(resultados[indice_quente], "nome", indice_quente),
                    utilidade_fria=getattr(resultados[indice_frio], "nome", indice_frio))
                aceitos.append(CandidatoLayout(
                    configuracao, geometria, resultados, geometria.area_unitaria,
                    recuperacao_total, recuperacoes,
                    recuperacao_total / alvo_total if alvo_total > 0 else 1.0,
                    tuple(q / alvo if alvo > 0 else 1.0 for q, alvo in zip(recuperacoes, alvos)),
                    configuracao.duty_projeto * geometria.area_unitaria,
                    configuracao.instaladas * geometria.area_unitaria,
                    max(quentes), quentes, max(frias), frias, governantes, margens))
    return tuple(aceitos)


def frente_pareto(candidatos):
    """Frente física sem pesos econômicos.

    Energia agregada mede a operação no conjunto de casos. Os dois picos, mantidos
    separados, dimensionam os envelopes quente e frio; somá-los produziria uma
    capacidade fictícia porque as utilidades não são intercambiáveis.
    """
    def domina(a, b):
        va = (-a.fracao_alvo_pinch, a.area_total_instalada,
              a.utilidade_quente, a.utilidade_fria,
              a.demanda_maxima_utilidade_quente, a.demanda_maxima_utilidade_fria)
        vb = (-b.fracao_alvo_pinch, b.area_total_instalada,
              b.utilidade_quente, b.utilidade_fria,
              b.demanda_maxima_utilidade_quente, b.demanda_maxima_utilidade_fria)
        return all(x <= y for x, y in zip(va, vb)) and any(x < y for x, y in zip(va, vb))

    return tuple(c for c in candidatos if not any(domina(outro, c) for outro in candidatos if outro is not c))
