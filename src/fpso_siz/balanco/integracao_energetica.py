"""Acoplamento explícito entre balanço e RATING do pré-aquecador.

Não resolve física de trocador: recebe um avaliador de geometria instalada. Centraliza a
propagação de Q_real para as correntes e utilidades dependentes, sem tocar nas vazões.
"""
from dataclasses import replace

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.trace import CalcTrace
from fpso_siz.core.unidades import w_para_kw


def _atualizar(estado, resultado, prem):
    c_fria = estado.C(estado.streams["C-06"])
    c_quente = estado.C(estado.streams["C-22"])
    temperaturas = dict(estado.T)
    q_real = w_para_kw(resultado.q_real)
    q_rec_max = w_para_kw(resultado.q_rec_max)
    q_rating = w_para_kw(resultado.q_rating)
    q_nao_realizada = w_para_kw(resultado.recuperacao_nao_realizada)
    temperaturas["C-07"] = resultado.t_fria_out
    temperaturas["C-23"] = resultado.t_quente_out
    temperaturas["C-24"] = min(resultado.t_quente_out, prem["T_store"])
    cargas = dict(estado.duties)
    cargas.update(Q_rec_max=q_rec_max, Q_rating=q_rating,
                   Q_real=q_real, Q_pre=q_real,
                   Q_rec_nao_realizada=q_nao_realizada,
                   Q_H=max(0, c_fria * (prem["T_trat"] - resultado.t_fria_out)),
                   Q_C=max(0, c_quente * (resultado.t_quente_out - prem["T_store"])))
    rastro = CalcTrace()
    for passo in estado.trace:
        rastro.reg(passo.equacao, passo.escopo, passo.valor, **dict(passo.entradas))
    rastro.reg("rating_preaquecedor", "P-001", q_real,
               Q_rec_max=q_rec_max, Q_rating=q_rating,
               convergiu=resultado.convergiu, iteracoes=resultado.iteracoes)
    rastro.reg("temperatura_preaquecedor_rating", "C-07", resultado.t_fria_out,
               T_in=estado.T["C-06"], Q=q_real, C=c_fria)
    rastro.reg("temperatura_preaquecedor_rating", "C-23", resultado.t_quente_out,
               T_in=estado.T["C-22"], Q=q_real, C=c_quente)
    return replace(estado, T=temperaturas, duties=cargas, trace=rastro)


def resolver(estados, prem, avaliador):
    """Itera balanço → propriedades/rating → P-002/P-003 até convergir por caso.

    ``avaliador(estado)`` deve usar a mesma geometria instalada em todas as chamadas e
    devolver ``ResultadoRating``. Não convergência é diagnóstico explícito.
    """
    cfg = carregar("equipment/comum/servico.toml")["acoplamento"]
    tol = float(cfg["tolerancia_W"])
    maxit = int(cfg["max_iteracoes"])
    atuais = tuple(estados)
    for it in range(1, maxit + 1):
        novos = tuple(_atualizar(e, avaliador(e), prem) for e in atuais)
        residuo = max((abs(n.duties["Q_real"] - a.duties.get("Q_real", a.duties["Q_pre"]))
                       for n, a in zip(novos, atuais)), default=0)
        atuais = novos
        if residuo <= tol:
            return atuais, {"convergiu": True, "iteracoes": it, "residuo_W": residuo}
    return atuais, {"convergiu": False, "iteracoes": maxit, "residuo_W": residuo}
