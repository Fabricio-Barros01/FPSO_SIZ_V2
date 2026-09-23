"""Balanços de massa e energia por bloco e global (fechamento do diagrama de blocos)."""
from fpso_siz.balanco.dados import constantes
from fpso_siz.balanco.modelo import COMP
from fpso_siz.core.configuracao import carregar


def topologia():
    """Topologia do diagrama de blocos (blocos, correntes, fronteira global)."""
    return carregar("topologia_db.toml")


def mtot(s):
    return sum(s.values())


def balanco_bloco(r, bloco):
    """Fechamento de um bloco: massa, energia (entalpia sensível + cargas) e componentes."""
    ins, outs = bloco["entradas"], bloco["saidas"]
    st, T, du = r.streams, r.T, r.duties
    mi = sum(mtot(st[c]) for c in ins)
    mo = sum(mtot(st[c]) for c in outs)
    em = abs(mi - mo) / mi if mi > 0 else 0.0
    Ein = sum(r.H(st[c], T[c]) for c in ins) + sum(du[k] for k in bloco["Q_in"]) + sum(du[k] for k in bloco["W"])
    Eout = sum(r.H(st[c], T[c]) for c in outs) + sum(du[k] for k in bloco["Q_out"])
    den = max(abs(Ein), constantes().numerico["denom_min_energia"])
    eE = abs(Ein - Eout) / den if mi > 0 else 0.0
    comp = {k: (sum(st[c][k] for c in ins) - sum(st[c][k] for c in outs)) for k in COMP}
    return dict(mi=mi, mo=mo, em=em, Ein=Ein, Eout=Eout, eE=eE, comp=comp)


def balanco_global(r):
    """Fechamento na fronteira do módulo (entradas C-01, C-14; saídas de gás, água e óleo)."""
    topo = topologia()
    st, T, du = r.streams, r.T, r.duties
    mi = sum(mtot(st[c]) for c in topo["global_in"])
    mo = sum(mtot(st[c]) for c in topo["global_out"])
    W = du["W_Bo"] + du["W_B1"] + du["W_B2"]
    Ein = sum(r.H(st[c], T[c]) for c in topo["global_in"]) + du["Q_H"] + du["Q_D"] + W
    Eout = sum(r.H(st[c], T[c]) for c in topo["global_out"]) + du["Q_C"]
    return dict(mi=mi, mo=mo, em=abs(mi - mo) / mi, Ein=Ein, Eout=Eout, eE=abs(Ein - Eout) / abs(Ein), W=W)


def balancos_por_bloco(r):
    return {b["id"]: balanco_bloco(r, b) for b in topologia()["blocos"]}
