"""Coeficiente de arrasto e velocidade terminal da gotícula — Eq. (9)–(13) de Alves &
Komesu (2025) = Eq. 3.6–3.7b de Stewart & Arnold (2008). Port de sizing/separator/drag.jl.

C_D sai por substituição sucessiva a partir de 0,34, sub-relaxada (x ← x + ω(f(x) − x))
por robustez: o envelope avalia combinações que ninguém inspecionou. `converged` volta
junto para que a não convergência vire diagnóstico, nunca número errado.
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar


def _k():
    return carregar("equipment/comum/stewart_arnold.toml")["arrasto"]


def constantes_arrasto():
    """Coeficientes das Eq. 3.6–3.7b (TOML), para o rastro documental."""
    return _k()


def terminal_velocity(rho_l, rho_g, dm, cd):
    """Eq. (11): V_t [m/s]; densidades em kg/m³, dm em µm."""
    return _k()["coef_vt"] * math.sqrt(((rho_l - rho_g) / rho_g) * (dm / cd))


def reynolds(rho_g, dm, vt, mu_g):
    """Eq. (10): Re; dm em µm, V_t em m/s, µ_g em cP."""
    return _k()["coef_re"] * rho_g * dm * vt / mu_g


def drag_coefficient(re):
    """Eq. (9): C_D = 24/Re + 3/√Re + 0,34."""
    k = _k()
    return k["cd_a"] / re + k["cd_b"] / math.sqrt(re) + k["cd_c"]


def souders_brown(rho_l, rho_g, dm, cd):
    """Eq. (13): K = [(ρg/(ρl − ρg))·(C_D/dm)]^0,5."""
    return math.sqrt((rho_g / (rho_l - rho_g)) * (cd / dm))


@dataclass(frozen=True)
class Arrasto:
    cd: float
    vt: float
    re: float
    iterations: int
    converged: bool


def converge_drag(rho_l, rho_g, dm, mu_g, cd0=None, relax=None, tol=None, maxiter=None, historico=None):
    """C_D por substituição sucessiva sub-relaxada. `historico` (lista), se dado, recebe
    cada iteração com os valores efetivamente usados (memorial; não altera o laço)."""
    k = _k()
    relax = k["relaxacao"] if relax is None else relax
    cd = float(k["cd_c"] if cd0 is None else cd0)
    tol = k["tolerancia"] if tol is None else tol
    maxiter = k["max_iteracoes"] if maxiter is None else maxiter
    vt = re = 0.0
    converged = False
    iters = 0
    for i in range(1, maxiter + 1):
        iters = i
        vt = terminal_velocity(rho_l, rho_g, dm, cd)
        re = reynolds(rho_g, dm, vt, mu_g)
        if re <= 0:
            break
        cd_new = drag_coefficient(re)
        cd_next = cd + relax * (cd_new - cd)
        if historico is not None:
            historico.append(dict(iteracao=i, cd_entrada=cd, vt=vt, re=re, cd_calculado=cd_new,
                                  cd_saida=cd_next, erro=abs(cd_next - cd), limite=tol * max(abs(cd), 1.0)))
        if abs(cd_next - cd) <= tol * max(abs(cd), 1.0):
            cd = cd_next
            vt = terminal_velocity(rho_l, rho_g, dm, cd)
            re = reynolds(rho_g, dm, vt, mu_g)
            converged = True
            break
        cd = cd_next
    return Arrasto(cd, vt, re, iters, converged)
