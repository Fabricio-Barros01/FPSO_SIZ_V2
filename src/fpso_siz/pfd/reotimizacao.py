"""Reotimização discreta de TAGs de trocador (F10x.7): config/pfd/reotimizacao.toml.

Cada candidato é um EstadoTAG com os valores da grade editados, dimensionado pelo mesmo
serviço por TAG (o número de tubos por passe continua varrido pelo método). O diagnóstico de
um candidato inviável usa o hook `bloqueios` do método, linha a linha do envelope: o melhor
feixe é o de menos bloqueios (critério, caso) e, entre eles, o de menor área. Os limites de
geometria do método não são alterados; a divisão em cascos só entra se o bloqueio que a
justifica estiver no melhor candidato. Nada aqui é física nova.
"""
import itertools
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.parametros import with_defaults
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as mc


def cfg():
    return carregar("pfd/reotimizacao.toml")


@dataclass(frozen=True)
class Candidato:
    valores: dict
    viavel: bool
    area: float              # área total (todos os cascos) do feixe escolhido ou do melhor feixe
    x: float                 # tubos por passe
    y: float                 # comprimento de tubo por casco
    bloqueios: tuple         # ((critério, índice do caso ou -1), ...) do melhor feixe
    rt: object

    @property
    def chave(self):
        return (not self.viavel, len(self.bloqueios), self.area)


@dataclass(frozen=True)
class Etapa:
    cascos: int
    candidatos: tuple

    @property
    def melhor(self):
        return min(self.candidatos, key=lambda c: c.chave)


def grade(ident, sobrescrever=None):
    """[{chave: valor}] na ordem declarada (produto cartesiano)."""
    g = {k: v["valores"] for k, v in cfg()["grade"].items()}
    g.update(sobrescrever or {})
    return [dict(zip(g, combo)) for combo in itertools.product(*g.values())]


def _parametros(rt):
    m = rt.entradas.metodo
    conss = [c for _, c in mc.restricoes(rt)]
    params = [with_defaults(m.parameters(), vals) for _, vals in rt.entradas.case_set().expand()]
    ok, p_env = m.envelope_params(params)
    return m, conss, (m.envelope_case_params(conss, p_env) if ok else None), p_env if ok else None


def avaliar(ctx, ident, valores):
    e = servico.estado_inicial(ident)
    for chave, valor in valores.items():
        e.editar(chave, float(valor), None, {})
    rt = servico.dimensionar(servico.preparar(ctx, e), e)
    r = rt.resultado
    if r is None:
        return Candidato(valores, False, math.inf, math.nan, math.nan, (("lacuna", -1),), rt)
    if r.feasible:
        return Candidato(valores, True, r.derivados_v2.get("area_total", r.derivados.get("area", math.nan)), r.x, r.y,
                         (), rt)
    _, _, _, p_env = _parametros(rt)
    melhor = mc.melhor_feixe(rt, p_env, valores.get("cascos_serie", 1.0) * valores.get("cascos_paralelo", 1.0))
    if melhor is None:
        return Candidato(valores, False, math.inf, math.nan, math.nan, (("preparacao", -1),), rt)
    b, area, row = melhor
    return Candidato(valores, False, area, row.x, row.y, b, rt)


def buscar(ctx, ident, sobrescrever=None):
    """[Etapa]: um casco; depois, se o gatilho do TAG está no melhor candidato, 2, 3… cascos."""
    t = cfg()["tags"][ident]
    etapas = []
    for n in range(1, int(t["n_cascos_max"]) + 1):
        base = {**t["premissas"], t["divisao"]: float(n)}
        etapas.append(Etapa(n, tuple(avaliar(ctx, ident, {**base, **g}) for g in grade(ident, sobrescrever))))
        melhor = etapas[-1].melhor
        if melhor.viavel or t["gatilho"] not in {c for c, _ in melhor.bloqueios}:
            break
    return etapas


def escolhido(etapas):
    """O melhor candidato de todas as etapas (viável de menor área, ou o de menos bloqueios)."""
    return min((e.melhor for e in etapas), key=lambda c: c.chave)


def operacao(c):
    """Operação de cada caso no feixe do candidato (hook do método), com o nome do caso."""
    m, conss, pcs, _ = _parametros(c.rt)
    nomes = [n for n, _ in c.rt.entradas.case_set().expand()]
    return [dict(caso=n, **o) for n, o in zip(nomes, m.operacao_por_caso(conss, c.x, pcs))]
