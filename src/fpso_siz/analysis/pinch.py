"""Núcleo da Análise Pinch — algoritmo da "Problem Table" (Linnhoff e Flower, 1978).

Port de `src/analysis/pinch.jl`, nome a nome.

Fonte: Kemp, I. C., *Pinch Analysis and Process Integration: A User Guide on Process
Integration for the Efficient Use of Energy*, 2ª ed., Butterworth-Heinemann, 2007
(ISBN 978-0-7506-8260-2). O algoritmo passo a passo está no apêndice do cap. 3, **§3.9.1,
pp. 95-96**; o balanço por intervalo é a Eq. (2.3), **p. 21**.

Responde a pergunta que nenhum método de dimensionamento responde: dado um conjunto de
correntes a aquecer e a resfriar, **quanto de utilidade quente e fria a rede exige, no
mínimo**, antes de qualquer trocador ser desenhado. É alvo termodinâmico, não projeto de
equipamento.

**Este módulo é puro.** Não há `ParameterSpec`, caso, método nem contrato aqui: a entrada é
uma lista de `ThermalStream` e um ΔTmin, e a saída é um `PinchResult`. O encaixe no contrato
de varredura mora em `sizing/pinch_kemp.py`.

**Temperatura em °C**, declarado e não herdado: Kemp trabalha em °C nos caps. 2-3, e toda
grandeza daqui é ou uma *diferença* de temperatura — idêntica em °C e K — ou uma temperatura
deslocada que só aparece dentro de diferenças. A origem da escala nunca entra na conta.

**O deslocamento de ΔTmin/2 é aplicado em `shifted_temperatures`, e em lugar nenhum mais**
(passo 2 de §3.9.1, p. 95; é a terceira das três formas que a Nota 2 da p. 24 lista, e a que
o livro adota). Um deslocamento aplicado duas vezes apareceria como um pinch plausível no
lugar errado.

**Sinal: excedente é POSITIVO.** `CP_net = ΣCP_quente − ΣCP_fria`, e intervalo com excedente
tem `ΔH > 0` — convenção da 2ª edição (Nota 1 da p. 24 e Nota (c) da p. 96).

**Nenhum caminho levanta exceção.** `validate_streams` devolve as mensagens; entrada recusada
vira `PinchResult` inviável com diagnóstico, como `infeasible` do contrato.

**Entrega:** deslocamento, tabela de intervalos, cascata infactível e factível, QHmin, QCmin,
temperaturas de pinch (deslocada, quente e fria), sinalização de problema-limiar e as curvas
compostas de §2.3. A *grand composite curve* não tem função própria porque é o par
(`cascade_feasible`, `boundaries`) que o resultado já devolve.

**NÃO entrega e NÃO alega:** síntese de rede de trocadores, alvo de área, utilidades
múltiplas, número mínimo de unidades, ΔTcont por corrente (§3.3.1, p. 53 — esta versão usa
ΔTmin global) e CP polinomial em T (§3.1.3, p. 45 — CP constante por segmento, o método padrão
do livro).
"""
import math
from dataclasses import dataclass, field

from fpso_siz.core.configuracao import carregar


def _k():
    return carregar("equipment/comum/pinch.toml")


# ------------------------------------------------------------------ entrada
@dataclass(frozen=True)
class StreamSegment:
    """Trecho de corrente com CP constante. `mcp` é a capacidade calorífica de FLUXO (ṁ·cp),
    em kW/°C — uma taxa, não uma propriedade; `t_in` e `t_out` são temperaturas reais em °C.

    Não há campo de tipo, e nenhum é aceito: que o segmento seja quente ou frio é consequência
    do sinal de (t_in − t_out), e perguntá-lo criaria um dado que pode contradizer os dois
    números acima."""
    t_in: float
    t_out: float
    mcp: float


@dataclass(frozen=True)
class ThermalStream:
    """Corrente de processo como sequência de segmentos de CP constante.

    Segmentos existem porque o CP real depende da temperatura, e o remédio do livro é
    linearizar por trechos (§3.1.3, p. 45). Os segmentos têm de ser contíguos e ter a mesma
    direção: uma corrente que esquenta e depois esfria são duas correntes."""
    name: str
    segments: tuple = field(default_factory=tuple)


def corrente(name, t_in, t_out, mcp):
    """Corrente de um segmento só — o caso comum."""
    return ThermalStream(str(name), (StreamSegment(float(t_in), float(t_out), float(mcp)),))


def is_hot(seg):
    """Um segmento é quente quando esfria. Derivado, nunca declarado."""
    return seg.t_in > seg.t_out


def is_cold(seg):
    return seg.t_in < seg.t_out


def stream_type(s):
    """"hot" | "cold", derivado do primeiro segmento — só tem sentido depois de
    `validate_streams` aprovar, que é quem garante que os segmentos concordam em direção."""
    return "hot" if is_hot(s.segments[0]) else "cold"


def heat_load(x):
    """Carga térmica do segmento ou da corrente, em kW — sempre positiva."""
    if isinstance(x, ThermalStream):
        return sum(heat_load(seg) for seg in x.segments)
    return x.mcp * abs(x.t_in - x.t_out)


def heat_loads(streams):
    """(quente, fria): as cargas totais, em kW. Existe para a conferência cruzada que a p. 24
    manda fazer — QCmin − QHmin tem de igualar ΣQ_quente − ΣQ_fria, em qualquer ΔTmin."""
    quente = fria = 0.0
    for s in streams:
        for seg in s.segments:
            if is_hot(seg):
                quente += heat_load(seg)
            else:
                fria += heat_load(seg)
    return quente, fria


# ------------------------------------------------------------------ saída
@dataclass(frozen=True)
class TemperatureInterval:
    """Intervalo entre duas fronteiras consecutivas de temperatura DESLOCADA. `cp_net` é
    ΣCP_quente − ΣCP_fria das correntes que o atravessam (passo 5); `dh` é o calor líquido
    liberado, positivo quando há excedente (passo 6, e Eq. (2.3) da p. 21)."""
    s_top: float
    s_bot: float
    cp_net: float
    dh: float


@dataclass(frozen=True)
class PinchResult:
    """Resultado da Problem Table. Sem `feasible`, nada mais tem significado: `message`
    explica o que impediu (mesmo contrato de `SizingResult`).

    As duas cascatas vêm juntas de propósito: a infactível é a que o leitor confere contra a
    Figura 2.9(a), e a factível é a que dá os alvos.

    `t_pinch_shifted` é LISTA: o passo 9 diz "the point(s) at which there is zero net heat
    flow", no plural. `threshold` e a lista vazia são coisas diferentes — um problema-limiar é
    aquele em que uma das utilidades zera (§3.3.2, p. 54), e no ΔTmin exato do limiar isso
    acontece e ainda há pinch interior."""
    feasible: bool
    message: str
    dt_min: float
    intervals: tuple
    cascade_infeasible: tuple     # n+1 nós, começando em 0 no topo
    cascade_feasible: tuple       # n+1 nós, começando em QHmin no topo
    boundaries: tuple             # n+1 fronteiras deslocadas, decrescentes
    q_h_min: float                # kW
    q_c_min: float                # kW
    t_pinch_shifted: tuple        # °C, deslocada
    t_pinch_hot: tuple            # °C, real, lado quente
    t_pinch_cold: tuple           # °C, real, lado frio
    threshold: bool


def pinch_infeasible(message, dt_min=math.nan):
    """PinchResult inviável com diagnóstico. Espelha `infeasible` do contrato."""
    return PinchResult(False, str(message), float(dt_min), (), (), (), (), math.nan, math.nan, (), (), (), False)


# ------------------------------------------------------------------ recusa de entrada (devolve mensagens)
def validate_streams(streams, dt_min):
    """Todas as queixas contra as correntes e o ΔTmin (lista vazia = tudo válido). NÃO levanta.
    Uma regra por mensagem, e cada mensagem nomeia a corrente."""
    msgs = []
    if not (math.isfinite(dt_min) and dt_min > 0):
        msgs.append(f"ΔTmin tem de ser um número positivo (recebi {dt_min} °C).")
    if not streams:
        msgs.append("Lista de correntes vazia: não há o que integrar.")
    for s in streams:
        nome = s.name if s.name else "(sem nome)"
        if not s.segments:
            msgs.append(f"Corrente '{nome}' não tem nenhum segmento.")
            continue
        for i, seg in enumerate(s.segments, 1):
            onde = f"'{nome}'" if len(s.segments) == 1 else f"'{nome}', segmento {i}"
            if not (math.isfinite(seg.t_in) and math.isfinite(seg.t_out)):
                msgs.append(f"{onde}: temperatura não numérica ({seg.t_in} → {seg.t_out} °C).")
                continue
            # A recusa que mais precisa explicar-se: CP infinito. Kemp §3.1.3, p. 44, diz que a
            # carga latente "pode ser considerada" corrente a temperatura fixa com CP infinito, e
            # na frase seguinte dá a prática que o software usa no lugar — o pinch é sempre
            # causado por uma corrente COMEÇANDO, e preservar a temperatura de suprimento mantém
            # o pinch exato. A mensagem carrega a receita, senão o usuário só sabe que foi
            # recusado.
            if seg.t_in == seg.t_out:
                msgs.append(f"{onde}: segmento isotérmico ({seg.t_in} °C). Mudança de fase não entra como CP "
                            "infinito. Kemp §3.1.3, p. 44: mantenha a temperatura de suprimento e desloque a de "
                            "destino em ~0,1 °C — para cima se a corrente é fria (vaporizando), para baixo se é "
                            "quente (condensando).")
                continue
            if not (math.isfinite(seg.mcp) and seg.mcp > 0):
                msgs.append(f"{onde}: mCp tem de ser positivo (recebi {seg.mcp} kW/°C).")
        # As duas regras que só fazem sentido ENTRE segmentos, e só se cada segmento já é válido
        # por si: acusar descontinuidade entre dois segmentos com NaN seria ruído em cima da
        # queixa que importa.
        if len(s.segments) > 1 and all(math.isfinite(g.t_in) and math.isfinite(g.t_out) and g.t_in != g.t_out
                                       for g in s.segments):
            quente = is_hot(s.segments[0])
            if any(is_hot(g) != quente for g in s.segments):
                msgs.append(f"Corrente '{nome}' muda de direção entre segmentos: uma corrente que esquenta e depois "
                            "esfria são duas correntes, não uma.")
            for i in range(len(s.segments) - 1):
                a, b = s.segments[i], s.segments[i + 1]
                if a.t_out != b.t_in:
                    msgs.append(f"Corrente '{nome}': o segmento {i + 1} termina em {a.t_out} °C e o {i + 2} começa em "
                                f"{b.t_in} °C. Os segmentos têm de ser contíguos.")
    return msgs


# ------------------------------------------------------------------ passo 2: o ÚNICO deslocamento
def shifted_temperatures(seg, dt_min):
    """(s_in, s_out) do segmento, em °C: −ΔTmin/2 se quente, +ΔTmin/2 se frio (passo 2, p. 95).

    Esta função é o único ponto do módulo que desloca temperatura."""
    meio = dt_min / 2
    return (seg.t_in - meio, seg.t_out - meio) if is_hot(seg) else (seg.t_in + meio, seg.t_out + meio)


# ------------------------------------------------------------------ o algoritmo (§3.9.1, pp. 95-96)
def problem_table(streams, dt_min):
    """Alvos de energia de um conjunto de correntes (Kemp §3.9.1, pp. 95-96). Nunca levanta:
    entrada recusada vira resultado inviável. Os nove passos do livro estão marcados no corpo."""
    # Passo 1 — o ΔTmin é escolha de quem chama; aqui só se confere que é utilizável.
    queixas = validate_streams(streams, dt_min)
    if queixas:
        return pinch_infeasible(" ".join(queixas), dt_min)
    dt = float(dt_min)

    # Passo 2 — deslocar. A partir daqui ninguém mais olha temperatura real, e é isso que
    # impede um segundo deslocamento.
    desl = []
    for s in streams:
        for seg in s.segments:
            s_in, s_out = shifted_temperatures(seg, dt)
            desl.append((min(s_in, s_out), max(s_in, s_out), seg.mcp, is_hot(seg)))

    # Passos 3 e 4 — listar as fronteiras e ordenar em ordem DECRESCENTE.
    fronteiras = sorted({t for d in desl for t in (d[0], d[1])}, reverse=True)
    n = len(fronteiras) - 1

    # Passos 5 e 6 — CP líquido e calor líquido de cada intervalo.
    intervalos = []
    for i in range(n):
        topo, base = fronteiras[i], fronteiras[i + 1]
        cp = 0.0
        for lo, hi, mcp, quente in desl:
            # As fronteiras SAEM das pontas dos segmentos: um segmento ou cobre o intervalo
            # inteiro ou não toca o seu interior. Não há caso parcial.
            if lo <= base and hi >= topo:
                cp += mcp if quente else -mcp
        intervalos.append(TemperatureInterval(topo, base, cp, cp * (topo - base)))

    # Passo 7 — cascata a partir de zero no topo. O nó k está na fronteira k.
    infactivel = [0.0]
    for it in intervalos:
        infactivel.append(infactivel[-1] + it.dh)

    # Passo 8 — o fluxo mais negativo (ou zero) vira utilidade quente no topo.
    q_h = max(0.0, -min(infactivel))
    factivel = [x + q_h for x in infactivel]

    # Passo 9 — os alvos, e o pinch onde o fluxo é nulo.
    q_c = factivel[-1]
    escala = max((abs(x) for x in factivel), default=0.0)
    tol = _k()["singularidades"]["tol_fluxo_nulo"] * max(1.0, escala)

    # Só nós INTERIORES: o nó 1 vale QHmin e o último vale QCmin, e zero neles significa "esta
    # ponta não precisa de utilidade" — é a ponta livre de um problema-limiar, não um pinch.
    idx = [k for k in range(1, n) if abs(factivel[k]) <= tol]
    s_pinch = tuple(fronteiras[k] for k in idx)
    return PinchResult(True, "", dt, tuple(intervalos), tuple(infactivel), tuple(factivel), tuple(fronteiras),
                       q_h, q_c, s_pinch, tuple(t + dt / 2 for t in s_pinch), tuple(t - dt / 2 for t in s_pinch),
                       q_h <= tol or q_c <= tol)


# ------------------------------------------------------------------ curvas compostas (§2.3)
@dataclass(frozen=True)
class CompositeCurves:
    """As duas curvas compostas, em temperatura REAL (não deslocada). `h_*`/`t_*` são pares
    (entalpia acumulada em kW, temperatura em °C) prontos para plotar, em temperatura crescente;
    `q_rec` é a sobreposição horizontal das duas — o calor que a rede pode recuperar."""
    h_hot: tuple
    t_hot: tuple
    h_cold: tuple
    t_cold: tuple
    q_rec: float


def _curva_composta(segmentos):
    """(h, t) de UM lado. §2.3, p. 18: dentro de cada faixa entre dois pontos de quebra
    consecutivos, as correntes presentes somam os seus CP, e a faixa contribui ΣCP·ΔT de
    entalpia. Sai em temperatura crescente, acumulando de H = 0.

    Os pontos de quebra são TODAS as temperaturas de entrada e de saída, porque é em cada uma
    delas que uma corrente entra ou sai da soma. Faixa sem corrente tem ΣCP = 0 e entalpia
    nula: a curva fica vertical ali, que é o desenho correto."""
    if not segmentos:
        return (), ()
    quebras = sorted({t for seg in segmentos for t in (seg.t_in, seg.t_out)})
    if len(quebras) < 2:
        return (), ()
    h = [0.0]
    for k in range(1, len(quebras)):
        lo, hi = quebras[k - 1], quebras[k]
        # ΣCP da faixa: os segmentos que a atravessam INTEIRA. Comparar contra o ponto médio
        # evita o empate de fronteira — um segmento que termina em `lo` não participa da faixa
        # acima dele.
        meio = (lo + hi) / 2
        cp = 0.0
        for seg in segmentos:
            s_lo, s_hi = min(seg.t_in, seg.t_out), max(seg.t_in, seg.t_out)
            if s_lo < meio < s_hi:
                cp += seg.mcp
        h.append(h[-1] + cp * (hi - lo))
    return tuple(h), tuple(quebras)


def composite_curves(streams, pr):
    """As curvas compostas quente e fria, posicionadas uma contra a outra (§2.3, pp. 17-19, e
    Fig. 2.4): a quente nasce em H = 0; a fria é deslocada horizontalmente de QCmin, que a
    Problem Table devolve. A menor separação vertical é ΔTmin quando há pinch. Nenhuma procura
    de encosto é repetida — quem localiza o pinch é o algoritmo de §3.9.1.

    `pr` é o `PinchResult` destas mesmas correntes, ou o ΔTmin (aí a tabela é calculada aqui).
    Curvas vazias quando o problema é inviável; faltando um dos lados, conserva o que existe e
    devolve q_rec = NaN, pois não há o que sobrepor."""
    if not isinstance(pr, PinchResult):
        pr = problem_table(streams, pr)
    if not pr.feasible:
        return CompositeCurves((), (), (), (), math.nan)
    quentes, frias = [], []
    for s in streams:
        for seg in s.segments:
            (quentes if is_hot(seg) else frias).append(seg)
    h_q, t_q = _curva_composta(quentes)
    h_f, t_f = _curva_composta(frias)
    if not h_q or not h_f:
        return CompositeCurves(h_q, t_q, h_f, t_f, math.nan)
    # A fria começa em QCmin, não em zero: é esse deslocamento que põe as duas curvas a ΔTmin
    # uma da outra no pinch (Fig. 2.4).
    h_f = tuple(x + pr.q_c_min for x in h_f)
    rec = min(h_q[-1], h_f[-1]) - max(h_q[0], h_f[0])
    return CompositeCurves(h_q, t_q, h_f, t_f, max(rec, 0.0))
