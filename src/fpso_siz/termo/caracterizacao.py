"""Caracterização dos pseudo-componentes do fluido de poço (Riazi & Al-Sahhaf, 1996).

O fluido do BOT tem componentes que nenhum banco de dados descreve:

- **cortes SCN C6–C19**: o backend resolve o nome "C7" como n-heptano, e isso é uma
  armadilha — o corte real tem iso-parafinas, naftênicos e aromáticos, não só a parafina
  normal. Este módulo os caracteriza como pseudo-componentes;
- **frações plus C20+ e C20++**: o BOT dá só MW e densidade.

**Não há substituição de composição.** A fração molar de cada componente é preservada
exatamente; o que muda é a propriedade atribuída a ele (`termo/servico.flash_tp` envia a
composição original ao backend).

Coeficientes e fontes em `config/termo/caracterizacao_scn.toml`; nada numérico aqui.
"""
import math
import re
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar

SCN = "scn"        # corte single carbon number, caracterizado pela correlação
PLUS = "plus"      # fração plus (C20+, C20++), MW do BOT
REAL = "real"      # componente com identificador de banco


def cfg():
    return carregar("termo/caracterizacao_scn.toml")


@dataclass(frozen=True)
class Pseudo:
    """Um pseudo-componente caracterizado. Tudo em SI menos MW (g/mol) e SG (adimensional)."""
    nome: str
    tipo: str          # SCN | PLUS
    nc: float          # número de carbono (SCN) ou NaN (plus)
    MW: float          # g/mol
    Tb: float          # K
    SG: float          # 60/60
    Tc: float          # K
    Pc: float          # Pa
    omega: float
    origem: dict       # grandeza → como foi obtida


def _theta(bloco, M):
    """A eq. 2 do artigo: θ = θ∞ − exp(a − b·M^c), com o sinal declarado no TOML."""
    v = bloco["inf"] - math.exp(bloco["a"] - bloco["b"] * M ** bloco["c"])
    return -v if bloco.get("negativa") else v


def numero_de_carbono(nome):
    """Nc do rótulo do BOT ("C7" → 7), ou None se o rótulo não for um corte SCN."""
    m = re.fullmatch(re.escape(cfg()["scn"]["prefixo"]) + r"(\d+)", nome)
    return int(m.group(1)) if m else None


def classificar(nome, mws_plus=None):
    """SCN, PLUS ou REAL para um rótulo de componente do BOT."""
    c = cfg()
    if nome in (mws_plus or c["plus"]):
        return PLUS
    nc = numero_de_carbono(nome)
    if nc is not None and c["scn"]["nc_min"] <= nc <= c["scn"]["nc_max"]:
        return SCN
    return REAL


def _de_M(nome, tipo, nc, M, origem_mw):
    c = cfg()["correlacao"]
    if tipo == SCN:
        tb = c["Tb_de_Nc"]
        Tb = tb["inf"] - math.exp(tb["a"] - tb["b"] * nc ** tb["c"])
        origem_tb = "correlação eq. 3 (de Nc)"
    else:
        # fração plus: sem Nc, o Tb sai da eq. 5, que é função de M
        Tb = _theta(c["Tb_de_M"], M)
        origem_tb = "correlação eq. 5 (de M)"
    Tbr = _theta(c["Tbr"], M)
    from fpso_siz.core.unidades import bar_para_pa
    return Pseudo(nome=nome, tipo=tipo, nc=float(nc) if nc is not None else math.nan, MW=M, Tb=Tb,
                  SG=_theta(c["SG"], M), Tc=Tb / Tbr, Pc=bar_para_pa(_theta(c["Pc"], M)),
                  omega=_theta(c["omega"], M),
                  origem={"MW": origem_mw, "Tb": origem_tb, "SG": "correlação eq. 6 / Tab. 6 (de M)",
                          "Tc": "correlação Tab. 6: Tc = Tb/Tbr (de M)",
                          "Pc": "correlação Tab. 6 (de M)", "omega": "correlação Tab. 6 (de M)"})


def caracterizar(nome, mw_plus=None):
    """O pseudo-componente de um rótulo do BOT. `mw_plus` é o MW do BOT das frações plus —
    ele é DADO de entrada, e é usado sem alteração. Isso faz o MW da mistura fechar exatamente
    em relação aos MW ADOTADOS (entradas + caracterização); não é afirmação sobre o MW
    verdadeiro do corte real, que ninguém mediu."""
    tipo = classificar(nome, mws_plus={nome: mw_plus} if mw_plus is not None else None)
    if tipo == REAL:
        raise ValueError(f"{nome!r} é componente real: use o identificador do banco, não a correlação")
    if tipo == PLUS:
        if mw_plus is None:
            raise ValueError(f"{nome!r} é fração plus: informe o MW do BOT")
        return _de_M(nome, PLUS, None, float(mw_plus), "DADO do BOT (c20_pseudo)")
    nc = numero_de_carbono(nome)
    m = cfg()["correlacao"]["M_de_Nc"]
    return _de_M(nome, SCN, nc, m["coef_a"] * nc - m["coef_b"], "correlação eq. 7 (M = 14·Nc − 4)")
