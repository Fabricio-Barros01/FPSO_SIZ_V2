"""Estudo de circulação fixa da utilidade nos trocadores (F13/Etapa 2).

Hipótese de operação autorizada pelo usuário como ESTUDO (2026-09-26): a bomba da utilidade
mantém a mesma vazão em todos os casos — a do caso de projeto, pelo critério da P-45 (maior
vazão volumétrica no tubo) — e o que varia com a carga é o ΔT da utilidade. No cálculo padrão
é o contrário: o ΔT é fixo pelos insumos e a vazão acompanha a carga (`r_vazao_utilidade`).
Nada aqui altera o cálculo padrão nem promove a hipótese a premissa.

O estudo não supõe temperatura: para cada caso ativo, a temperatura de saída da utilidade é
RESOLVIDA por bisseção sobre o mesmo fechamento de energia que o cálculo padrão inverte,

    ṁ_fixa = q / (cp(T̄)·|t_entrada − t_saída|),   T̄ = (t_entrada + t_saída)/2,

com cp, ρ, μ e k da água reavaliados na temperatura média resultante (IAPWS). A saída
resolvida entra no próprio insumo de temperatura de retorno do TAG: com isso as entradas do
lado tubo (vazão, cp, ρ, μ, k, temperatura de saída) e o rastro continuam consistentes entre
si, e a grade de tubos por passe (`grade_velocidade`) consome a vazão fixa e a densidade
reavaliada quando as entradas são preparadas de novo.

Falha física ou de convergência é ESTADO: o TAG volta inviável com mensagem (contrato de
dimensionamento), nunca exceção. Caso inativo continua inativo — não se resolve nem se edita.
Critérios numéricos (tolerâncias, iterações, expansão do intervalo) em config/pfd/circulacao.toml.
"""
import copy
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.contrato import infeasible_envelope
from fpso_siz.core.ieee import div
from fpso_siz.core.trace import Rastro
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import fluidos


def cfg():
    return carregar("pfd/circulacao.toml")


@dataclass(frozen=True)
class Resolucao:
    """Temperatura de saída resolvida de um caso ativo (ou a falha que impediu resolvê-la)."""
    num: int
    nome: str
    t_entrada: float
    t_saida_base: float      # a do cálculo padrão (insumo), para comparação
    t_saida: float           # a resolvida com a circulação fixa
    carga: float             # W, a mesma do cálculo padrão (fechada pelo lado tubo)
    vazao: float             # kg/s efetivamente resolvida (= vazão fixa, na tolerância)
    cp: float
    rho: float
    iteracoes: int
    projeto: bool
    ok: bool = True
    mensagem: str = ""


@dataclass(frozen=True)
class Estudo:
    """O que a circulação fixa fixou, e como cada caso ativo fechou."""
    tag: str
    caso_projeto: int
    nome_projeto: str
    vazao_fixa: float
    origem: str
    resolucoes: tuple

    @property
    def ok(self):
        return all(r.ok for r in self.resolucoes)

    @property
    def mensagem(self):
        return next((r.mensagem for r in self.resolucoes if not r.ok), "")


def _numero(caso, chave):
    v = caso.valores.get(chave)
    if v is None or v.lacuna or v.faixa or not math.isfinite(v.valor):
        return None
    return v.valor


def _insumo(caso, chave):
    v = caso.insumos.get(chave)
    return None if v is None or not math.isfinite(v.valor) else v.valor


def caso_de_projeto(rt, chaves):
    """Índice do caso ativo de maior vazão volumétrica no tubo (critério da P-45, o mesmo que o
    método usa em `caso_projeto`). None se nenhum caso ativo tem vazão e densidade."""
    melhor, alvo = None, -math.inf
    for i, c in enumerate(rt.entradas.casos):
        if not c.ativo:
            continue
        m, rho = _numero(c, chaves["vazao"]), _numero(c, chaves["densidade"])
        if m is None or rho is None or not rho > 0:
            continue
        if m / rho > alvo:
            melhor, alvo = i, m / rho
    return melhor


def _vazao(carga, t_in, t_out):
    """ṁ que fecha a carga com a água entre t_in e t_out (cp na temperatura média, IAPWS)."""
    a = fluidos.agua_saturada((t_in + t_out) / 2, Rastro())
    return div(carga, a.cp * abs(t_in - t_out)), a


def _resolver_caso(tag, caso, chaves, vazao_fixa, delta_projeto, projeto):
    """Bisseção da temperatura de saída do caso com a vazão fixa. O intervalo inicial vai da
    temperatura de entrada (onde ΔT → 0 e a vazão diverge) até o ΔT do caso de projeto; se não
    houver troca de sinal, o extremo é expandido pelo fator declarado."""
    k, msg = cfg()["bissecao"], cfg()["mensagens"]
    t_in = _insumo(caso, chaves["entrada"])
    t_base = _insumo(caso, chaves["saida"])
    m_base, cp_base = _numero(caso, chaves["vazao"]), _numero(caso, chaves["cp"])
    falha = lambda t: Resolucao(caso.num, caso.nome, t_in or math.nan, t_base or math.nan, math.nan, math.nan,
                                math.nan, math.nan, math.nan, 0, projeto, False, t)
    if t_in is None or t_base is None or m_base is None or cp_base is None:
        return falha(msg["base_incompleta"].format(tag=tag))
    carga = m_base * cp_base * abs(t_base - t_in)
    sinal = math.copysign(1.0, t_base - t_in)
    # extremo junto à entrada: ΔT pequeno → vazão grande → resíduo positivo
    perto = t_in + sinal * k["recuo_relativo"] * delta_projeto
    longe = t_in + sinal * delta_projeto
    try:
        g_perto = _vazao(carga, t_in, perto)[0] - vazao_fixa
        expansoes = 0
        while True:
            g_longe = _vazao(carga, t_in, longe)[0] - vazao_fixa
            if g_perto * g_longe <= 0 or expansoes >= int(k["max_expansoes"]):
                break
            longe = t_in + sinal * abs(longe - t_in) * k["fator_expansao"]
            expansoes += 1
        if g_perto * g_longe > 0:
            return falha(msg["sem_troca_de_sinal"].format(tag=tag, caso=caso.num, vazao=f"{vazao_fixa:.4g}",
                                                          delta=f"{abs(longe - t_in):.4g}"))
        a, b = perto, longe
        for it in range(1, int(k["max_iteracoes"]) + 1):
            meio = (a + b) / 2
            m_meio, props = _vazao(carga, t_in, meio)
            g = m_meio - vazao_fixa
            if abs(b - a) <= k["tol_temperatura"] or abs(g) <= k["tol_vazao"] * vazao_fixa:
                return Resolucao(caso.num, caso.nome, t_in, t_base, meio, carga, m_meio, props.cp, props.rho, it,
                                 projeto)
            if g * g_perto > 0:
                a = meio
            else:
                b = meio
        return falha(msg["nao_convergiu"].format(tag=tag, caso=caso.num, iteracoes=int(k["max_iteracoes"])))
    except (ArithmeticError, ValueError) as erro:
        return falha(msg["propriedade_invalida"].format(tag=tag, caso=caso.num, erro=erro))


def resolver(rt, chaves, origem=""):
    """Estudo da circulação fixa a partir da configuração-base já preparada (`rt`)."""
    tag = rt.tag.tag
    i = caso_de_projeto(rt, chaves)
    if i is None:
        vazio = Resolucao(0, "", math.nan, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan, 0, False,
                          False, cfg()["mensagens"]["sem_caso_projeto"].format(tag=tag))
        return Estudo(tag, -1, "", math.nan, origem, (vazio,))
    projeto = rt.entradas.casos[i]
    vazao_fixa = _numero(projeto, chaves["vazao"])
    delta = abs(_insumo(projeto, chaves["saida"]) - _insumo(projeto, chaves["entrada"]))
    res = tuple(_resolver_caso(tag, c, chaves, vazao_fixa, delta, c.num == projeto.num)
                for c in rt.entradas.casos if c.ativo)
    return Estudo(tag, projeto.num, projeto.nome, vazao_fixa, origem, res)


def aplicar(estado, estudo, chaves):
    """Edita, caso a caso, o insumo de temperatura de retorno com a saída resolvida. Só os casos
    ativos são tocados; os inativos continuam inativos com o motivo do TAG."""
    for r in estudo.resolucoes:
        if r.ok:
            estado.editar(chaves["saida"], r.t_saida, [r.num], {})
    return estado


def executar(ctx, ident, v, estado=None):
    """ResultadoTAG do TAG com a circulação fixa. Prepara a configuração-base completa, fixa a
    vazão do caso de projeto, resolve a saída de cada caso ativo, e prepara as entradas OUTRA
    VEZ com as saídas resolvidas — é nessa segunda preparação que a grade de tubos por passe
    consome a vazão fixa, a densidade reavaliada e a geometria do candidato. Devolve também o
    estudo, para o relatório."""
    chaves = v["circulacao_fixa"]
    base = copy.deepcopy(estado) if estado is not None else servico.estado_inicial(ident)
    for chave, valor in v.get("geral", {}).items():
        base.editar(chave, float(valor), None, {})
    rt_base = servico.dimensionar(servico.preparar(ctx, base), base)
    estudo = resolver(rt_base, chaves, v.get("origem", ""))
    if not estudo.ok:
        return servico.ResultadoTAG(rt_base.entradas, infeasible_envelope(estudo.mensagem), base), estudo
    fixo = aplicar(copy.deepcopy(base), estudo, chaves)
    return servico.dimensionar(servico.preparar(ctx, fixo), fixo), estudo


def aproximacoes(rt, dt_app):
    """As duas aproximações terminais de cada caso ativo contra o ΔT de aproximação da P-32
    (premissa do balanço). É condição DO ESTUDO — a regra padrão do método não a impõe, e nada
    aqui entra no dimensionamento: só se lê o rastro que o método já emitiu (invariante 3). Os
    nomes das variáveis do rastro vêm do TOML, não do código."""
    r = rt.resultado
    if r is None:
        return []
    ra = cfg()["rastro"]
    alvos = (ra["aproximacao_1"], ra["aproximacao_2"])
    out = []
    for nome, pc in zip(r.case_names, r.per_case):
        vals = {}
        for e in pc.trace.entries:
            if e.block == ra["bloco"] and e.var in alvos:
                vals[e.var] = e.value
        finitos = [v for v in vals.values() if v is not None and math.isfinite(v)]
        # a igualdade conta como atendida: a aproximação do lado frio cai exatamente no ΔT_app por
        # construção em alguns casos, e o ruído da cadeia não pode reprovar isso
        folga = cfg()["p32"]["tol_relativa"] * max(1.0, abs(dt_app))
        out.append(dict(caso=nome, dt1=vals.get(alvos[0]), dt2=vals.get(alvos[1]), dt_app=dt_app,
                        menor=min(finitos) if finitos else math.nan,
                        atende=len(finitos) == len(alvos) and min(finitos) >= dt_app - folga))
    return out
