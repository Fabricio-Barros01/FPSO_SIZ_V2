"""Porta única do `pymoo` (F15), como `termo/backend.py` é a do ChEDL.

Só este módulo importa `pymoo`, e o import é preguiçoso: quem não otimiza não paga a
dependência, e um teste de arquitetura garante a porta única. A física e o avaliador ficam em
`pfd/otimizacao.py`, que não conhece `pymoo` — trocar de biblioteca ou portar o programa a
outra linguagem mexe só aqui.

O algoritmo é o do documento 0003: NSGA-II até três objetivos e NSGA-III a partir de quatro
(direções de referência de Das-Dennis), variáveis mistas tratadas como reais com arredondamento
das inteiras na decodificação, restrições por violação (g ≤ 0), semente fixa.

`multiprocessing` (stdlib) também mora só aqui, pela mesma regra: cada indivíduo é uma avaliação
INDEPENDENTE do serviço por TAG, então a população de uma geração é paralelizável sem tocar no
avaliador. O algoritmo segue sequencial no processo principal — só a avaliação sai para os
filhos — e `Pool.map` preserva a ordem, de modo que frente, histórico e semente dão o MESMO
resultado da rodada sequencial: paralelizar não muda número.
"""
import math

from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import otimizacao as otim


def versao():
    import pymoo
    return pymoo.__version__


def _algoritmo(n_obj, populacao, semente):
    """(algoritmo do pymoo, nome) conforme o número de objetivos."""
    k = otim.cfg()["algoritmo"]
    if n_obj <= int(k["objetivos_max_nsga2"]):
        from pymoo.algorithms.moo.nsga2 import NSGA2
        return NSGA2(pop_size=populacao), "NSGA-II"
    from pymoo.algorithms.moo.nsga3 import NSGA3
    from pymoo.util.ref_dirs import get_reference_directions
    dirs = get_reference_directions("das-dennis", n_obj, n_partitions=populacao // n_obj)
    return NSGA3(ref_dirs=dirs, pop_size=populacao), "NSGA-III"


def _saidas(a, ids_obj, tags, grande):
    """(F, G) de uma Avaliacao. Objetivo não calculável (um TAG do somatório não está
    dimensionado) entra como a penalidade declarada: o indivíduo é dominado, e a violação é que
    informa o caminho de volta ao admissível.

    G tem uma posição a mais do que os TAGs restringidos: a ÚLTIMA conta os TAGs que ficaram
    esperando entrada. Lacuna não é violação de projeto — por isso ela não entra na violação do
    TAG —, mas também não é projeto avaliado, e sem essa posição o pymoo devolveria como
    "viável" um ponto de que não se sabe nada. Falta de dado não vira viabilidade por omissão."""
    return ([a.objetivos[i] if math.isfinite(a.objetivos[i]) else grande for i in ids_obj],
            [a.restricoes[t] for t in tags] + [float(len(a.sem_dado))])


_TRABALHO = {}


def _abrir(dados, propostas, sub):
    """Inicializador do processo filho: os dados entram uma vez por processo, não por indivíduo."""
    _TRABALHO.update(dados=dados, propostas=propostas, sub=sub)


def _ponto(x):
    """A avaliação, no filho. É o mesmo `otim.avaliar` da rodada sequencial."""
    return otim.avaliar(_TRABALHO["dados"], x, _TRABALHO["propostas"], _TRABALHO["sub"])


class _Paralelo:
    """`elementwise_runner` do pymoo: avalia a população inteira em processos e devolve os `out`
    na mesma ordem em que o algoritmo pediu. Guarda as Avaliacao aqui porque o filho não
    escreve na lista do pai."""

    def __init__(self, pool, ids_obj, tags, grande):
        self.pool, self.ids_obj, self.tags, self.grande = pool, ids_obj, tags, grande
        self.avaliacoes = []

    def __call__(self, f, X):
        avs = self.pool.map(_ponto, [tuple(float(v) for v in x) for x in X])
        self.avaliacoes.extend(avs)
        out = []
        for a in avs:
            fs, gs = _saidas(a, self.ids_obj, self.tags, self.grande)
            out.append({"F": fs, "G": gs})
        return out


def _pool(processos, dados, propostas, sub):
    """Pool de processos que recebe os dados uma vez por processo; o que trafega em cada geração é
    só o vetor de decisão e a Avaliacao de volta.

    O contexto é `forkserver`, não `fork`: os filhos nascem de um servidor de processo limpo, de
    uma thread só. `fork` a partir de um processo COM threads (é o caso quando a suíte roda sob
    pytest-xdist, cujo worker tem threads de comunicação) é inseguro e o Python 3.12+ avisa sobre
    isso. O preço do `forkserver` é picklar os argumentos e reimportar o pacote no filho, e aqui
    isso é barato: os casos e as propostas dão cerca de 5 kB e 12 kB, e o preload adianta o import
    do avaliador."""
    import multiprocessing

    ctx = multiprocessing.get_context("forkserver")
    ctx.set_forkserver_preload(["fpso_siz.pfd.otimizacao"])
    return ctx.Pool(processos, initializer=_abrir, initargs=(dados, propostas, sub))


def avaliar_pontos(dados, pontos, propostas=None, sub=None, processos=None):
    """[Avaliacao] de uma lista de pontos, na ordem dada — a varredura exaustiva da validação
    (critério 2 do 0003), que não usa o algoritmo. Com `processos` acima de um, em paralelo; o
    resultado é o mesmo de `pfd/otimizacao.varredura`, avaliação por avaliação."""
    xs = [tuple(float(v) for v in x) for x in pontos]
    processos = 1 if processos is None else int(processos)
    if processos > 1:
        with _pool(processos, dados, propostas, sub) as pool:
            return pool.map(_ponto, xs)
    return [otim.avaliar(dados, x, propostas, sub) for x in xs]


def _problema(dados, propostas, sub, pool=None):
    """Problema do pymoo sobre o avaliador. As fronteiras entram como LISTAS: numpy é reservado à
    porta `_num.py` pela invariante 1, e o pymoo aceita sequências aqui — o que também deixa esta
    camada mapeável no port a C/Java."""
    from pymoo.core.problem import ElementwiseProblem

    ids_obj = [o["id"] for o in otim.objetivos(sub)]
    lo, hi, _ = otim.limites(sub)
    tags = otim.tags_restritas(sub)
    grande = float(carregar("pfd/otimizacao.toml")["algoritmo"].get("penalidade", 0)) or math.inf

    runner = None if pool is None else _Paralelo(pool, ids_obj, tags, grande)

    class Modulo(ElementwiseProblem):
        """Cada indivíduo é uma avaliação do serviço por TAG. Com `pool`, a população de cada
        geração é avaliada pelo runner paralelo e `_evaluate` não é chamado; sem ele, a rodada é
        a sequencial de sempre. `avaliacoes` é a MESMA lista nos dois caminhos."""

        def __init__(self):
            extra = {} if runner is None else {"elementwise_runner": runner}
            # len(tags) violações de projeto + 1 posição para "ponto não avaliável" (ver _saidas)
            super().__init__(n_var=len(lo), n_obj=len(ids_obj), n_ieq_constr=len(tags) + 1,
                             xl=lo, xu=hi, **extra)
            self.avaliacoes = [] if runner is None else runner.avaliacoes

        def _evaluate(self, x, out, *args, **kwargs):
            a = otim.avaliar(dados, tuple(x), propostas, sub)
            self.avaliacoes.append(a)
            out["F"], out["G"] = _saidas(a, ids_obj, tags, grande)

    return Modulo(), ids_obj, tags


def otimizar(dados, propostas=None, populacao=None, geracoes=None, semente=None, sub=None,
             processos=None):
    """Roda a otimização e devolve (frente, historico, meta). `frente`: [(x, objetivos,
    restricoes)] dos pontos não dominados viáveis; `historico`: todas as Avaliacao, na ordem;
    `meta`: algoritmo, versão do pymoo, semente, população, gerações e processos usados.

    `processos` acima de um avalia a população de cada geração em paralelo (mesmo resultado, ver
    o cabeçalho); `None` ou um mantém a rodada sequencial."""
    k = otim.cfg()["algoritmo"]
    populacao = int(k["populacao"]) if populacao is None else int(populacao)
    geracoes = int(k["geracoes"]) if geracoes is None else int(geracoes)
    semente = int(k["semente"]) if semente is None else int(semente)
    processos = 1 if processos is None else int(processos)
    if processos > 1:
        with _pool(processos, dados, propostas, sub) as pool:
            return _rodar(dados, propostas, sub, populacao, geracoes, semente, processos, pool)
    return _rodar(dados, propostas, sub, populacao, geracoes, semente, processos, None)


def _rodar(dados, propostas, sub, populacao, geracoes, semente, processos, pool):
    from pymoo.optimize import minimize

    problema, ids_obj, tags = _problema(dados, propostas, sub, pool)
    algoritmo, nome = _algoritmo(len(ids_obj), populacao, semente)
    res = minimize(problema, algoritmo, ("n_gen", geracoes), seed=semente, verbose=False,
                   save_history=False)
    frente = []
    if res.X is not None:
        # uma solução só volta como vetor 1-D; mais de uma, como matriz
        xs = res.X if getattr(res.X, "ndim", 1) > 1 else [res.X]
        fs = res.F if getattr(res.F, "ndim", 1) > 1 else [res.F]
        for x, f in zip(xs, fs):
            frente.append((tuple(float(v) for v in x), dict(zip(ids_obj, (float(v) for v in f)))))
    meta = {"algoritmo": nome, "pymoo": versao(), "semente": semente, "populacao": populacao,
            "geracoes": geracoes, "processos": processos, "avaliacoes": len(problema.avaliacoes),
            "subproblema": sub or "completo", "variaveis": [v["id"] for v in otim.variaveis(sub)],
            "objetivos": ids_obj, "tags_restritas": tags}
    return frente, problema.avaliacoes, meta
