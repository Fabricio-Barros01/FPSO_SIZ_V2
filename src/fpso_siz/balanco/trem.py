"""Trem de separação SG-001 → V-001 → V-002: a sequência composicional do processo.

    z_base --Nota 4--> z_caso
    z_caso --SG-001--> (β_F, y_F, x_F)
    x_F --V-001--> (β₁, y₁, x₁)
    x₁ --V-002--> (β₂, y₂, x₂)

**Composição do caso** (config/trem.toml [recombinacao]; docs/validacao/38): a composição do BOT
(`z_base`, por tipo de fluido) é flashada na referência do FWKO (P_FWKO e a T do caso) e as duas
fases são recombinadas na proporção que reproduz o `produced_gas_sm3d` como gás do FWKO e o
`oil_sm3d` como óleo morto depois da série FWKO → condição padrão. É premissa de modelagem
aprovada, sustentada pelo BOT e não prescrita por ele. `z_base` nunca é alterado.

**O trem é produtivo nos casos avaliáveis** (sem gás de lift): a alimentação de cada estágio é o
LÍQUIDO do anterior, com a quantidade absoluta propagada (`ṅ_V = β·ṅ_F`, `ṅ_L = (1−β)·ṅ_F`); o
balanço (`balanco/modelo.py`) consome a vazão, a massa, o MW, o Z e a ρ da fase vapor de cada
estágio. Cada líquido é levado à condição padrão para saber quanto dele é óleo morto e quanto é
gás dissolvido — é assim que o balanço, que conta óleo (O) e gás (G), acompanha o flash.
Casos com gás de lift: não avaliáveis (a composição do lift não existe na fonte).
"""
import math
from dataclasses import dataclass, field
from functools import cached_property, lru_cache

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_k, kpa_para_pa, pa_para_kpa
from fpso_siz.termo import servico as termo


def cfg():
    return carregar("trem.toml")


def lacunas():
    return cfg()["lacuna"]


# ------------------------------------------------------------------ flash (memorizado)
@lru_cache(maxsize=None)
def _flash(T_K, P_Pa, itens, plus):
    return termo.flash_tp(T_K, P_Pa, dict(itens), dict(plus))


def flash(T_C, P_kPa, z, mws_plus):
    """`termo.flash_tp` na unidade do processo, memorizado pela condição e composição EXATAS:
    o mesmo (T, P, z) devolve o mesmo objeto, então repetir um caso não repete o flash."""
    return _flash(c_para_k(T_C), kpa_para_pa(P_kPa), tuple(z.items()), tuple(sorted((mws_plus or {}).items())))


def _beta(f):
    return f.vapor.fracao_molar if f.vapor is not None else 0.0


# ------------------------------------------------------------------ avaliabilidade
def avaliavel(caso):
    """(True, "") se o caso entra no trem produtivo; (False, motivo) se não."""
    if caso["lift_gas_sm3d"] > 0:
        return False, f"{cfg()['avaliacao']['estado_nao_avaliavel']}: gás de lift sem composição na fonte"
    return True, ""


# ------------------------------------------------------------------ recombinação (Nota 4)
@dataclass(frozen=True)
class Reproducao:
    """O z_caso re-flashado: as vazões do BOT têm de voltar."""
    q_gas_fwko_sm3d: float     # β·ṅ·V_M de z_caso na referência
    q_oleo_tanque_m3d: float    # líquido da referência levado à condição padrão, em volume de óleo morto
    erro_gas_rel: float
    erro_oleo_rel: float

    @property
    def ok(self):
        tol = cfg()["recombinacao"]["tolerancia_reproducao"]
        return self.erro_gas_rel <= tol and self.erro_oleo_rel <= tol


@dataclass(frozen=True)
class Recombinacao:
    z_base: dict
    z_caso: dict
    T_ref_C: float
    P_ref_kPa: float
    VM: float                   # Sm³/kmol
    rho_oleo: float             # kg/m³ (óleo morto, API)
    q_gas_bot_sm3d: float
    q_oleo_bot_m3d: float
    vapor_ref: object           # termo.Fase: y_ref
    liquido_ref: object         # termo.Fase: x_ref
    beta_std: float             # fração molar de x_ref que vaporiza na condição padrão
    MW_vapor_std: float
    MW_liquido_std: float
    n_gas_kmol_d: float
    n_liquido_kmol_d: float
    reproducao: Reproducao
    mw_mistura: float           # Σ z_caso,i·MW_i pelos MW adotados (independente das fases)

    @property
    def n_total_kmol_d(self):
        return self.n_gas_kmol_d + self.n_liquido_kmol_d

    @property
    def massa_kg_d(self):
        return self.n_gas_kmol_d * self.vapor_ref.MW + self.n_liquido_kmol_d * self.liquido_ref.MW

    @property
    def massa_oleo_tanque_kg_d(self):
        return self.n_liquido_kmol_d * (1.0 - self.beta_std) * self.MW_liquido_std

    @property
    def massa_gas_padrao_kg_d(self):
        """Gás do FWKO mais o gás que o líquido do FWKO libera até a condição padrão."""
        return self.n_gas_kmol_d * self.vapor_ref.MW + self.n_liquido_kmol_d * self.beta_std * self.MW_vapor_std

    @property
    def q_gas_padrao_sm3d(self):
        return (self.n_gas_kmol_d + self.n_liquido_kmol_d * self.beta_std) * self.VM

    # --- fechamentos da própria mistura
    @property
    def erro_soma_z(self):
        return abs(sum(self.z_caso.values()) - 1.0)

    @property
    def erro_molar(self):
        """|Σᵢ(ṅ_g·yᵢ + ṅ_L·xᵢ) − (ṅ_g + ṅ_L)| / ṅ."""
        y, x = self.vapor_ref.composicao, self.liquido_ref.composicao
        soma = sum(self.n_gas_kmol_d * y.get(k, 0.0) + self.n_liquido_kmol_d * x.get(k, 0.0) for k in self.z_caso)
        return abs(soma - self.n_total_kmol_d) / self.n_total_kmol_d

    @property
    def erro_massico(self):
        """|ṅ·Σ zᵢ·MWᵢ − (ṅ_g·MW_v + ṅ_L·MW_l)| / ṁ: a massa pelas fases contra a massa pela mistura."""
        return abs(self.n_total_kmol_d * self.mw_mistura - self.massa_kg_d) / self.massa_kg_d

    @property
    def componente(self):
        """(pior componente, máxᵢ |ṅ·zᵢ − ṅ_g·yᵢ − ṅ_L·xᵢ| / ṅ)."""
        y, x = self.vapor_ref.composicao, self.liquido_ref.composicao
        n = self.n_total_kmol_d
        erros = {k: abs(n * z - self.n_gas_kmol_d * y.get(k, 0.0) - self.n_liquido_kmol_d * x.get(k, 0.0)) / n
                 for k, z in self.z_caso.items()}
        pior = max(erros, key=erros.get)
        return pior, erros[pior]

    @property
    def ok(self):
        tol = cfg()["recombinacao"]["tolerancia_fechamento"]
        return (self.reproducao.ok and max(self.erro_soma_z, self.erro_molar, self.componente[1]) <= tol
                and self.erro_massico <= tol)


def _liquidos(f):
    """(fração molar, MW médio) de TODAS as fases líquidas do flash. Na condição padrão o PR com
    pseudo-componentes pode dividir o óleo em duas fases líquidas (casos Mid Life); para o
    balanço, óleo de tanque é tudo o que é líquido ali, qualquer que seja a divisão."""
    liq = [p for p in f.fases if p.nome != "vapor"]
    n = sum(p.fracao_molar for p in liq)
    return n, (sum(p.fracao_molar * p.MW for p in liq) / n if n > 0 else 0.0)


def _serie_ate_padrao(x, T_std, P_std, mws):
    """(β, MW do vapor, MW do líquido total) de `x` levado à condição padrão."""
    f = flash(T_std, P_std, x, mws)
    if not f.ok:
        raise ValueError(f"série até a condição padrão não convergiu: {f.mensagem}")
    return _beta(f), (f.vapor.MW if f.vapor is not None else 0.0), _liquidos(f)[1]


def recombinar(z_base, mws, q_gas_sm3d, q_oleo_m3d, rho_oleo, VM, T_ref_C, P_ref_kPa, T_std_C, P_std_kPa):
    """A composição do caso pela Nota 4 (config/trem.toml [recombinacao]). ValueError se a
    referência não for bifásica: sem as duas fases não há o que recombinar."""
    ref = flash(T_ref_C, P_ref_kPa, z_base, mws)
    if not ref.ok or ref.vapor is None or ref.liquido is None:
        raise ValueError(f"referência da recombinação não bifásica a {T_ref_C} °C e {P_ref_kPa} kPa: {ref.mensagem}")
    y, x = ref.vapor.composicao, ref.liquido.composicao
    b_s, mw_vs, mw_ls = _serie_ate_padrao(x, T_std_C, P_std_kPa, mws)
    n_g = q_gas_sm3d / VM
    n_l = q_oleo_m3d * rho_oleo / ((1.0 - b_s) * mw_ls)
    n = n_g + n_l
    z = {k: (n_g * y.get(k, 0.0) + n_l * x.get(k, 0.0)) / n for k in z_base}
    # verificação: o z_caso, re-flashado, devolve as vazões do BOT?
    f = flash(T_ref_C, P_ref_kPa, z, mws)
    b = _beta(f)
    b2, _, mw2 = _serie_ate_padrao(f.liquido.composicao, T_std_C, P_std_kPa, mws)
    q_g = b * n * VM
    q_o = (1.0 - b) * n * (1.0 - b2) * mw2 / rho_oleo
    rep = Reproducao(q_g, q_o, abs(q_g - q_gas_sm3d) / q_gas_sm3d, abs(q_o - q_oleo_m3d) / q_oleo_m3d)
    return Recombinacao(dict(z_base), z, T_ref_C, P_ref_kPa, VM, rho_oleo, q_gas_sm3d, q_oleo_m3d,
                        ref.vapor, ref.liquido, b_s, mw_vs, mw_ls, n_g, n_l, rep, termo.mw_mistura(z, mws))


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
    VM: float = math.nan
    beta: float = math.nan
    n_vapor_kmol_d: float = math.nan
    n_liquido_kmol_d: float = math.nan
    m_vapor_kg_d: float = math.nan
    m_liquido_kg_d: float = math.nan
    m_oleo_tanque_kg_d: float = math.nan       # do líquido deste estágio, pela série até a condição padrão
    m_gas_dissolvido_kg_d: float = math.nan   # o resto do líquido: gás que ele ainda libera
    q_gas_dissolvido_sm3d: float = math.nan
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

    @property
    def q_vapor_sm3d(self):
        return self.n_vapor_kmol_d * self.VM


@dataclass(frozen=True)
class FechamentoTrem:
    """O que entrou tem de sair:  ṅ_F = Σ ṅ_V + ṅ_L,final, global e por componente.

    `ok_parcial` cobre só os estágios executados. `ok` é do TREM: exige também que a cascata
    tenha percorrido todos os estágios esperados."""
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
    recombinacao: object = None      # Recombinacao, ou None no caso não avaliável
    estagios: list = field(default_factory=list)
    interrompido: str = ""           # por que a cascata parou antes do último estágio
    avaliavel: bool = True
    motivo: str = ""

    @property
    def completo(self):
        return self.avaliavel and not self.interrompido and len(self.estagios) == len(cfg()["estagio"])

    @property
    def n_liquido_final(self):
        return self.estagios[-1].n_liquido_kmol_d if self.estagios else math.nan

    @property
    def n_vapor_total(self):
        return sum(e.n_vapor_kmol_d for e in self.estagios if math.isfinite(e.n_vapor_kmol_d))

    def estagio(self, corrente_gas):
        return next(e for e in self.estagios if e.corrente_gas == corrente_gas)

    @cached_property
    def fechamento(self):
        return _fechar(self)


def nao_avaliavel(motivo):
    return TremSeparacao(avaliavel=False, motivo=motivo)


def resolver(rec, condicoes, mws, T_std_C, P_std_kPa):
    """A cascata a partir do caso recombinado. `condicoes`: [(ponto, corrente de gás, T °C,
    P kPa)] na ordem do trem — as do EstadoProcesso em construção."""
    estagios, interrompido = [], ""
    n_atual, z_atual = rec.n_total_kmol_d, dict(rec.z_caso)
    for ponto, cid, t_c, p_kpa in condicoes:
        f = flash(t_c, p_kpa, z_atual, mws)
        if not f.ok:
            estagios.append(Estagio(ponto, cid, t_c, p_kpa, dict(z_atual), f, n_atual, rec.VM))
            interrompido = f"{ponto}: {f.mensagem}"
            break
        v, li = f.vapor, f.liquido
        b = _beta(f)
        n_v, n_l = b * n_atual, (1.0 - b) * n_atual
        m_l = n_l * li.MW if li is not None else 0.0
        if li is not None:
            b_s, mw_vs, mw_ls = _serie_ate_padrao(dict(li.composicao), T_std_C, P_std_kPa, mws)
        else:
            b_s, mw_vs, mw_ls = 0.0, 0.0, 0.0
        estagios.append(Estagio(ponto, cid, t_c, p_kpa, dict(z_atual), f, n_atual, rec.VM, beta=b,
                                n_vapor_kmol_d=n_v, n_liquido_kmol_d=n_l,
                                m_vapor_kg_d=n_v * v.MW if v is not None else 0.0, m_liquido_kg_d=m_l,
                                m_oleo_tanque_kg_d=n_l * (1.0 - b_s) * mw_ls,
                                m_gas_dissolvido_kg_d=n_l * b_s * mw_vs, q_gas_dissolvido_sm3d=n_l * b_s * rec.VM,
                                fechamento=termo.conferir(f)))
        if li is None:
            interrompido = f"{ponto}: sem fase líquida — não há alimentação para o estágio seguinte"
            break
        n_atual, z_atual = n_l, dict(li.composicao)
    return TremSeparacao(rec, estagios, interrompido)


def _fechar(trem):
    es = [e for e in trem.estagios if e.ok and math.isfinite(e.beta)]
    esperados = len(cfg()["estagio"])
    if not es or trem.recombinacao is None:
        return FechamentoTrem(math.nan, math.nan, math.nan, "", math.nan, False, len(es), esperados)
    n_F, m_F = trem.recombinacao.n_total_kmol_d, trem.recombinacao.massa_kg_d
    ultimo = es[-1]
    n_saida = sum(e.n_vapor_kmol_d for e in es) + ultimo.n_liquido_kmol_d
    m_saida = sum(e.m_vapor_kg_d for e in es) + ultimo.m_liquido_kg_d
    pior, erro_c = "", 0.0
    for k, zk in es[0].z.items():
        sai = sum(e.n_vapor_kmol_d * e.y.get(k, 0.0) for e in es) + ultimo.n_liquido_kmol_d * ultimo.x.get(k, 0.0)
        e_rel = abs(n_F * zk - sai) / n_F
        if e_rel > erro_c:
            pior, erro_c = k, e_rel
    return FechamentoTrem(abs(n_F - n_saida) / n_F, abs(m_F - m_saida) / m_F, erro_c, pior,
                          max(e.fechamento.erro_componente_max for e in es),
                          all(e.fechamento.ok for e in es), len(es), esperados)


# ------------------------------------------------------------------ TVP (diagnóstico)
def tvp_kpa(trem, T_C, mws):
    """Pressão de vapor verdadeira [kPa] do líquido final do trem a `T_C` (ponto de bolha pelo
    mesmo flash). Diagnóstico — não é restrição de nenhum cálculo. NaN se não avaliável."""
    if not trem.completo:
        return math.nan
    return pa_para_kpa(termo.pressao_bolha(c_para_k(T_C), trem.estagios[-1].x, mws))
