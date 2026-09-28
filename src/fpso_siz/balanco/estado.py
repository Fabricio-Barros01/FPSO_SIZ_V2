"""O estado de processo oficial: o que `balanco.modelo.resolver_caso` devolve e o que TODO o
resto consome — entradas dos TAGs, dimensionamento, otimização, saídas, memoriais e gate.

Não existe outro. O trem de separação (`balanco/trem.py`) é parte deste estado: nos casos
termodinamicamente avaliáveis é ele que dá o gás de cada estágio; nos demais o estado diz por que
não é avaliável.
"""
from dataclasses import dataclass, field

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
    trem: object = None                             # balanco/trem.TremSeparacao (produtivo ou não avaliável)
    gas_padrao: dict = field(default_factory=dict)  # Sm³/d do componente G por corrente (casos avaliáveis)

    @property
    def avaliavel(self):
        """O caso entrou no trem produtivo (recombinação + flash)?"""
        return self.trem is not None and self.trem.avaliavel

    @property
    def recombinacao(self):
        return self.trem.recombinacao if self.avaliavel else None

    def vapor(self, corrente):
        """Fase vapor do estágio cuja corrente de gás é `corrente` (None fora do trem produtivo)."""
        if not self.avaliavel:
            return None
        return next((e.vapor for e in self.trem.estagios if e.corrente_gas == corrente), None)

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
        """Vazão volumétrica padrão do componente, m³/d (Sm³/d para gás, com a ρ padrão do corte
        leve: só vale para o gás de um caso não avaliável — use `q`)."""
        return s[c] / self.rho[c] / K_DIA

    def q(self, sid, c):
        """Vazão volumétrica padrão do componente c na corrente sid (m³/d; Sm³/d para gás). O gás
        de um caso avaliável tem o volume que o trem deu à corrente (`gas_padrao`)."""
        if c == "G" and sid in self.gas_padrao:
            return self.gas_padrao[sid]
        return self.vol(self.streams[sid], c)
