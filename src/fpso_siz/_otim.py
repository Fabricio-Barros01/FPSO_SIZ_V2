"""Porta única do `pymoo` (F15), como `_num.py` e `pfd/_chedl.py`.

Só este módulo importa `pymoo`, e o import é preguiçoso: quem não otimiza não paga a
dependência, e um teste de arquitetura garante a porta única. A física e o avaliador ficam em
`pfd/otimizacao.py`, que não conhece `pymoo` — trocar de biblioteca ou portar o programa a
outra linguagem mexe só aqui.

O algoritmo é o do documento 0003: NSGA-II até três objetivos e NSGA-III a partir de quatro
(direções de referência de Das-Dennis), variáveis mistas tratadas como reais com arredondamento
das inteiras na decodificação, restrições por violação (g ≤ 0), semente fixa.
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


def _problema(dados, propostas, sub):
    """Problema do pymoo sobre o avaliador. As fronteiras entram como LISTAS: numpy é reservado à
    porta `_num.py` pela invariante 1, e o pymoo aceita sequências aqui — o que também deixa esta
    camada mapeável no port a C/Java."""
    from pymoo.core.problem import ElementwiseProblem

    ids_obj = [o["id"] for o in otim.objetivos(sub)]
    lo, hi, _ = otim.limites(sub)
    tags = otim.tags_restritas(sub)
    grande = float(carregar("pfd/otimizacao.toml")["algoritmo"].get("penalidade", 0)) or math.inf

    class Modulo(ElementwiseProblem):
        """Cada indivíduo é uma avaliação do serviço por TAG. Objetivo não calculável (um TAG do
        somatório não está dimensionado) entra como infinito: o indivíduo é dominado, e a
        violação é que informa o caminho de volta ao admissível."""

        def __init__(self):
            super().__init__(n_var=len(lo), n_obj=len(ids_obj), n_ieq_constr=len(tags), xl=lo, xu=hi)
            self.avaliacoes = []

        def _evaluate(self, x, out, *args, **kwargs):
            a = otim.avaliar(dados, tuple(x), propostas, sub)
            self.avaliacoes.append(a)
            out["F"] = [a.objetivos[i] if math.isfinite(a.objetivos[i]) else grande for i in ids_obj]
            out["G"] = [a.restricoes[t] for t in tags]

    return Modulo(), ids_obj, tags


def otimizar(dados, propostas=None, populacao=None, geracoes=None, semente=None, sub=None):
    """Roda a otimização e devolve (frente, historico, meta). `frente`: [(x, objetivos,
    restricoes)] dos pontos não dominados viáveis; `historico`: todas as Avaliacao, na ordem;
    `meta`: algoritmo, versão do pymoo, semente, população e gerações usadas."""
    from pymoo.optimize import minimize

    k = otim.cfg()["algoritmo"]
    populacao = int(k["populacao"]) if populacao is None else int(populacao)
    geracoes = int(k["geracoes"]) if geracoes is None else int(geracoes)
    semente = int(k["semente"]) if semente is None else int(semente)
    problema, ids_obj, tags = _problema(dados, propostas, sub)
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
            "geracoes": geracoes, "avaliacoes": len(problema.avaliacoes),
            "subproblema": sub or "completo", "variaveis": [v["id"] for v in otim.variaveis(sub)],
            "objetivos": ids_obj, "tags_restritas": tags}
    return frente, problema.avaliacoes, meta
