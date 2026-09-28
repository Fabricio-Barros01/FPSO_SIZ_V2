"""O estado de processo oficial: o que `balanco.modelo.resolver_caso` devolve e o que TODO o
resto consome — entradas dos TAGs, dimensionamento, otimização, saídas, memoriais e gate.

Não existe outro. O trem de separação (`balanco/trem.py`) é parte deste estado, avaliado sob
demanda (é caro: um flash por estágio) e guardado no próprio objeto na primeira leitura.
"""
from dataclasses import dataclass, field
from functools import cached_property

from fpso_siz.balanco import trem as _trem
from fpso_siz.balanco.dados import constantes
from fpso_siz.core.trace import CalcTrace
from fpso_siz.core.unidades import SEGUNDOS_POR_DIA

COMP = ("O", "W", "D", "G")
K_DIA = 1 / SEGUNDOS_POR_DIA  # (m³/d → m³/s)


@dataclass(frozen=True)
class EstadoProcesso:
    """Um caso de projeto resolvido.

    Correntes em kg/s por componente (O óleo, W água produzida, D água de diluição, G gás);
    T em °C e P em kPa por corrente; `duties` com as cargas térmicas e as potências; `gas` com
    a vazão de gás por estágio (Sm³/d); `rho`, `cp` e `gp` com as propriedades que o balanço
    usou; `proveniencia` com a origem e a validade de cada uma (termo/proveniencia.toml)."""
    caso: dict
    fluid: str
    well: str
    api: float
    rho: dict
    cp: dict
    gp: dict
    Wv: float
    BSW01: float
    BSW_F: float
    streams: dict
    T: dict
    P: dict
    duties: dict
    gas: dict
    iters: int
    residuo_reciclo: float
    VM: float  # volume molar padrão usado (m³/kmol)
    mu: tuple
    T_ref: float
    trace: CalcTrace
    fwko: dict = field(default_factory=dict)        # η adotado, η_req, η_padrão, exigido_acima, estado
    composicao: dict = field(default_factory=dict)  # z₀ do fluido (fração molar, só os componentes presentes)
    mws_plus: dict = field(default_factory=dict)    # MW das frações plus (BOT, c20_pseudo)
    proveniencia: dict = field(default_factory=dict)

    @property
    def num(self):
        return self.caso["num"]

    @property
    def convergiu(self):
        return self.residuo_reciclo < constantes().numerico["reciclo_tol"]

    def C(self, s):
        """Capacidade térmica da corrente, kW/K."""
        return sum(s[c] * self.cp[c] for c in COMP)

    def H(self, s, t):
        """Entalpia sensível relativa a T_ref, kW (P-14)."""
        return sum(s[c] * self.cp[c] for c in COMP) * (t - self.T_ref)

    def vol(self, s, c):
        """Vazão volumétrica padrão do componente, m³/d (Sm³/d para gás)."""
        return s[c] / self.rho[c] / K_DIA

    @cached_property
    def trem(self):
        """O trem SG-001 → V-001 → V-002 deste caso (`balanco/trem.TremSeparacao`)."""
        return _trem.resolver(self)
