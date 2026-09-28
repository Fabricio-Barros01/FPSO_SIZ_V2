"""Trem de separação SG-001 → V-001 → V-002: a sequência composicional do processo.

    z₀ --SG-001--> (β_F, y_F, x_F)
    x_F --V-001--> (β₁, y₁, x₁)
    x₁ --V-002--> (β₂, y₂, x₂)

A alimentação de cada estágio é o LÍQUIDO do anterior, com a quantidade absoluta propagada
(`ṅ_V = β·ṅ_F`, `ṅ_L = (1−β)·ṅ_F`). Tudo é lido do `EstadoProcesso` — composição, T e P de
cada estágio, massas específicas —: nada do processo é reconstruído aqui.

**O que o trem calcula é diagnóstico.** A vazão de gás por estágio que o processo consome é a
de Standing; a proveniência (termo/proveniencia.toml) declara β, x e y como não validados e
sem consumidor. Regra da base molar, e por que ela não sai de um split de fases:
config/trem.toml [base_molar]. Gás de lift: lacuna declarada, fora da base.
"""
import math
from dataclasses import dataclass, field
from functools import cached_property

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.termo import servico as termo


def cfg():
    return carregar("trem.toml")


def lacunas():
    return cfg()["lacuna"]


# ------------------------------------------------------------------ base molar
@dataclass(frozen=True)
class BaseMolar:
    """A quantidade absoluta que entra no trem, e de onde cada parcela veio."""
    oil_sm3d: float
    gas_produzido_sm3d: float
    gas_lift_sm3d: float          # NÃO entra em `massa_kg_d`: composição ausente na fonte
    rho_oleo: float               # kg/m³ (EstadoProcesso.rho["O"])
    rho_gas_std: float            # kg/m³ (EstadoProcesso.rho["G"])
    MW_z: float                   # g/mol, Σ zᵢ·MWᵢ pelos MW adotados

    @property
    def massa_oleo_kg_d(self):
        return self.oil_sm3d * self.rho_oleo

    @property
    def massa_gas_kg_d(self):
        return self.gas_produzido_sm3d * self.rho_gas_std

    @property
    def massa_kg_d(self):
        return self.massa_oleo_kg_d + self.massa_gas_kg_d

    @property
    def n_F_kmol_d(self):
        return self.massa_kg_d / self.MW_z if self.MW_z > 0 else math.nan

    @property
    def fracao_de_lift(self):
        """Quanto do gás que o balanço faz entrar em C-01 é gás de lift."""
        total = self.gas_produzido_sm3d + self.gas_lift_sm3d
        return self.gas_lift_sm3d / total if total > 0 else 0.0

    @property
    def tem_lift(self):
        return self.gas_lift_sm3d > 0


def base_molar(estado):
    c = estado.caso
    return BaseMolar(oil_sm3d=c["oil_sm3d"], gas_produzido_sm3d=c["produced_gas_sm3d"],
                     gas_lift_sm3d=c["lift_gas_sm3d"], rho_oleo=estado.rho["O"], rho_gas_std=estado.rho["G"],
                     MW_z=termo.mw_mistura(estado.composicao, estado.mws_plus))


# ------------------------------------------------------------------ estágios
@dataclass(frozen=True)
class Estagio:
    """Um estágio do trem: o que entrou, o que saiu, e quanto."""
    ponto: str
    corrente_gas: str
    T_C: float
    P_kPa: float
    z: dict                    # alimentação deste estágio
    estado: object             # termo.servico.EstadoTermodinamico
    n_entrada_kmol_d: float
    beta: float = math.nan
    n_vapor_kmol_d: float = math.nan
    n_liquido_kmol_d: float = math.nan
    m_vapor_kg_d: float = math.nan
    m_liquido_kg_d: float = math.nan
    fechamento: object = None  # termo.servico.Fechamento

    @property
    def ok(self):
        return self.estado is not None and self.estado.ok

    @property
    def vapor(self):
        return self.estado.vapor if self.ok else None

    @property
    def liquido(self):
        return self.estado.liquido if self.ok else None

    @property
    def y(self):
        return dict(self.vapor.composicao) if self.vapor else {}

    @property
    def x(self):
        return dict(self.liquido.composicao) if self.liquido else {}


@dataclass(frozen=True)
class FechamentoTrem:
    """O que entrou tem de sair:  ṅ_F = Σ ṅ_V + ṅ_L,final, global e por componente.

    `ok_parcial` cobre só os estágios executados. `ok` é do TREM: exige também que a cascata
    tenha percorrido todos os estágios esperados — um trem interrompido pode fechar
    perfeitamente nos estágios que rodou e continuar não sendo um trem completo."""
    erro_molar_relativo: float
    erro_massico_relativo: float
    erro_componente_max: float      # máx_i |ṅ_F·z_i − (Σ ṅ_V·y_i + ṅ_L,final·x_i)| / ṅ_F
    componente_pior: str
    erro_flash_max: float           # pior fechamento de flash isolado
    flashes_ok: bool
    estagios: int
    esperados: int

    @property
    def ok_parcial(self):
        tol = termo.cfg_flash()["fechamento"]
        return (self.flashes_ok and self.erro_molar_relativo <= tol["tolerancia_soma"]
                and self.erro_massico_relativo <= tol["tolerancia_soma"]
                and self.erro_componente_max <= tol["tolerancia_componente"])

    @property
    def ok(self):
        return self.ok_parcial and self.estagios == self.esperados


@dataclass(frozen=True)
class TremSeparacao:
    base: BaseMolar
    estagios: list = field(default_factory=list)
    interrompido: str = ""     # por que a cascata parou antes do último estágio

    @property
    def completo(self):
        return not self.interrompido and len(self.estagios) == len(cfg()["estagio"])

    @property
    def n_liquido_final(self):
        return self.estagios[-1].n_liquido_kmol_d if self.estagios else math.nan

    @property
    def n_vapor_total(self):
        return sum(e.n_vapor_kmol_d for e in self.estagios if math.isfinite(e.n_vapor_kmol_d))

    @cached_property
    def fechamento(self):
        return _fechar(self)


def resolver(estado):
    """A cascata do `EstadoProcesso`. Não altera o estado."""
    base = base_molar(estado)
    estagios, interrompido = [], ""
    n_atual, z_atual = base.n_F_kmol_d, dict(estado.composicao)
    for e in cfg()["estagio"]:
        cid = e["corrente_gas"]
        t_c, p_kpa = estado.T[cid], estado.P[cid]
        flash = termo.flash_tp(c_para_k(t_c), kpa_para_pa(p_kpa), z_atual, estado.mws_plus)
        if not flash.ok:
            estagios.append(Estagio(e["id"], cid, t_c, p_kpa, dict(z_atual), flash, n_atual))
            interrompido = f"{e['id']}: {flash.mensagem}"
            break
        v, li = flash.vapor, flash.liquido
        b = v.fracao_molar if v is not None else 0.0
        n_v, n_l = b * n_atual, (1.0 - b) * n_atual
        estagios.append(Estagio(e["id"], cid, t_c, p_kpa, dict(z_atual), flash, n_atual, beta=b,
                                n_vapor_kmol_d=n_v, n_liquido_kmol_d=n_l,
                                m_vapor_kg_d=n_v * v.MW if v is not None else 0.0,
                                m_liquido_kg_d=n_l * li.MW if li is not None else 0.0,
                                fechamento=termo.conferir(flash)))
        if li is None:
            interrompido = f"{e['id']}: sem fase líquida — não há alimentação para o estágio seguinte"
            break
        n_atual, z_atual = n_l, dict(li.composicao)
    return TremSeparacao(base, estagios, interrompido)


def _fechar(trem):
    es = [e for e in trem.estagios if e.ok and math.isfinite(e.beta)]
    esperados = len(cfg()["estagio"])
    if not es:
        return FechamentoTrem(math.nan, math.nan, math.nan, "", math.nan, False, 0, esperados)
    n_F, m_F = trem.base.n_F_kmol_d, trem.base.massa_kg_d
    ultimo = es[-1]
    n_saida = sum(e.n_vapor_kmol_d for e in es) + ultimo.n_liquido_kmol_d
    m_saida = sum(e.m_vapor_kg_d for e in es) + ultimo.m_liquido_kg_d
    pior, erro_c = "", 0.0
    for k, zk in es[0].z.items():
        sai = sum(e.n_vapor_kmol_d * e.y.get(k, 0.0) for e in es) + ultimo.n_liquido_kmol_d * ultimo.x.get(k, 0.0)
        e_rel = abs(n_F * zk - sai) / n_F
        if e_rel > erro_c:
            pior, erro_c = k, e_rel
    # o MW da massa que entra é Σ zᵢ·MWᵢ; o da massa que sai vem dos MW das fases (mesmos MW adotados)
    return FechamentoTrem(abs(n_F - n_saida) / n_F, abs(m_F - m_saida) / m_F, erro_c, pior,
                          max(e.fechamento.erro_componente_max for e in es),
                          all(e.fechamento.ok for e in es), len(es), esperados)


# ------------------------------------------------------------------ o que a fonte permite
def coerencia_com_bot(estado, T_std_C, P_std_kPa):
    """Os dois volumes do caso (oil_sm3d, produced_gas_sm3d) são reproduzidos pela composição?

    Flash de z₀ na condição padrão, com a ρ do óleo do próprio estado. Devolve o GOR do BOT, o
    do flash e as duas bases molares que o split permitiria (pelo gás e pelo óleo): é a medida
    que justifica a regra de `[base_molar]`. Nada aqui entra no processo."""
    c = estado.caso
    f = termo.flash_tp(c_para_k(T_std_C), kpa_para_pa(P_std_kPa), estado.composicao, estado.mws_plus)
    v, li = f.vapor, f.liquido
    if v is None or li is None:
        return dict(bifasico=False)
    b, vm, rho_o = v.fracao_molar, estado.VM, estado.rho["O"]
    base_gas = c["produced_gas_sm3d"] / vm / b
    base_oleo = c["oil_sm3d"] * rho_o / li.MW / (1 - b)
    return dict(bifasico=True, beta=b, gor_bot=c["produced_gas_sm3d"] / c["oil_sm3d"],
                gor_flash=(b * vm) / ((1 - b) * li.MW / rho_o), base_gas_kmol_d=base_gas,
                base_oleo_kmol_d=base_oleo,
                discordancia=max(base_gas, base_oleo) / min(base_gas, base_oleo) - 1)
