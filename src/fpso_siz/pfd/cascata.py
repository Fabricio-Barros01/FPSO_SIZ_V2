"""Fase 5.1 — cascata composicional do trem de separação, em MODO SOMBRA.

A F5 avaliou SG-001, V-001 e V-002 como **flashes independentes da mesma composição global**.
Isso não é o trem: o que entra no V-001 é o líquido que saiu do SG-001, não o fluido de poço.
Aqui a análise vira uma sequência física,

    z₀ --SG-001--> (β_F, y_F, x_F)
    x_F --V-001--> (β₁, y₁, x₁)
    x₁ --V-002--> (β₂, y₂, x₂)

com a quantidade absoluta de hidrocarboneto propagada estágio a estágio,
`ṅ_V = β·ṅ_F` e `ṅ_L = (1−β)·ṅ_F`.

**Continua tudo em sombra.** Nada do balanço, do dimensionamento, dos equipamentos ou dos
memoriais passa por aqui; nenhuma propriedade muda de status no mapa de proveniência
(`pfd/integracao.py`), e o guarda `exigir_liberada` continua recusando consumo.

## A base molar não é suposta

O arquivo de casos **não traz vazão molar**, e as três grandezas que existem são
incompatíveis entre si: `fluid_compositions` é por TIPO DE FLUIDO, e o mesmo tipo aparece em
casos com GOR diferentes — nenhum equilíbrio na condição padrão reproduz `oil_sm3d` e
`produced_gas_sm3d` ao mesmo tempo em todos os casos. Por isso a base **não sai de um split
de fases**: sai da MASSA, que é o que o balanço produtivo conserva.

    ṅ_F = ṁ_HC,in / MW_z
    ṁ_HC,in = oil_sm3d·ρ_óleo(API) + produced_gas_sm3d·ρ_gás,padrão

Os dois termos de massa são os MESMOS que o balanço produtivo põe em C-01, com as mesmas
massas específicas de fonte; `MW_z` é o MW da mistura pelos MW **adotados** (F4), tirado do
próprio flash do primeiro estágio. A regra, as fontes e o porquê de não usar o split estão
declarados em `config/pfd/integracao_termodinamica.toml`, `[base_molar]`.

**Gás de lift fica de fora, e isso é lacuna declarada**, não descuido: a composição do gás de
lift não existe na fonte (o BOT dá só o envelope de especificação). Ver `lacunas()`.
"""
import math
from dataclasses import dataclass, field

from fpso_siz.balanco.dados import constantes, pocos
from fpso_siz.balanco.propriedades import gas_props, poco_do_fluido
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import estado_termodinamico as et
from fpso_siz.pfd import integracao as ig


def cfg():
    return ig.cfg()


def lacunas():
    """O que impede a cascata de fechar contra o balanço produtivo, e por quê."""
    return cfg()["lacuna_cascata"]


def regra_base_molar():
    return cfg()["base_molar"]


# ------------------------------------------------------------------ base molar absoluta
@dataclass(frozen=True)
class BaseMolar:
    """A quantidade absoluta que entra no trem, e de onde cada parcela veio."""
    caso: int
    fluido: str
    oil_sm3d: float
    gas_produzido_sm3d: float
    gas_lift_sm3d: float          # NÃO entra em `massa_kg_d`: composição ausente na fonte
    rho_oleo: float               # kg/m³, API do poço
    rho_gas_std: float            # kg/m³, MW do corte leve / V_M
    massa_oleo_kg_d: float
    massa_gas_kg_d: float
    MW_z: float                   # g/mol, pelos MW ADOTADOS (F4)
    n_F_kmol_d: float

    @property
    def massa_kg_d(self):
        return self.massa_oleo_kg_d + self.massa_gas_kg_d

    @property
    def fracao_de_lift(self):
        """Quanto do gás que o balanço produtivo faz entrar em C-01 é gás de lift."""
        total = self.gas_produzido_sm3d + self.gas_lift_sm3d
        return self.gas_lift_sm3d / total if total > 0 else 0.0

    @property
    def tem_lift(self):
        return self.gas_lift_sm3d > 0


def volume_molar_padrao(dados):
    """V_M = R·T_padrão/P_padrão, em sm³/kmol: a definição de sm³, a mesma do balanço."""
    const = constantes()
    return const.R * c_para_k(dados.T_std_C) / dados.P_std_kPa


def massa_especifica_oleo(dados, fluido):
    """ρ do óleo pela API do poço (dado do BOT), a mesma correlação do balanço."""
    const = constantes()
    api = pocos()[poco_do_fluido(dados, fluido)].api
    return const.api_a / (const.api_b + api) * const.rho_agua_15_6C


def mw_da_mistura(estado):
    """MW da mistura pelos MW ADOTADOS: Σ (fração molar da fase · MW da fase).

    Não é o MW verdadeiro do petróleo real — é o que fecha exatamente contra os MW adotados
    nas entradas e na caracterização (F4)."""
    return sum(f.fracao_molar * f.MW for f in estado.fases)


def base_molar(dados, caso, estado_primeiro_estagio):
    """`BaseMolar` do caso, pela regra declarada em `[base_molar]`.

    `estado_primeiro_estagio` entra só para dar o MW da mistura pelos MW adotados: nenhum
    flash a mais é feito por causa da base."""
    fluido = caso["fluid_type"]
    vm = volume_molar_padrao(dados)
    rho_o = massa_especifica_oleo(dados, fluido)
    rho_g = gas_props(dados.composicoes[fluido], constantes(), vm)["rho_std"]
    m_o = caso["oil_sm3d"] * rho_o
    m_g = caso["produced_gas_sm3d"] * rho_g
    mw = mw_da_mistura(estado_primeiro_estagio)
    return BaseMolar(caso=caso["num"], fluido=fluido, oil_sm3d=caso["oil_sm3d"],
                     gas_produzido_sm3d=caso["produced_gas_sm3d"], gas_lift_sm3d=caso["lift_gas_sm3d"],
                     rho_oleo=rho_o, rho_gas_std=rho_g, massa_oleo_kg_d=m_o, massa_gas_kg_d=m_g,
                     MW_z=mw, n_F_kmol_d=(m_o + m_g) / mw if mw > 0 else math.nan)


# ------------------------------------------------------------------ estágios
@dataclass(frozen=True)
class Estagio:
    """Um estágio do trem: o que entrou, o que saiu, e quanto."""
    ponto: str
    corrente_gas: str
    T_C: float
    P_kPa: float
    z: dict                    # alimentação deste estágio
    estado: object             # EstadoTermodinamico
    n_entrada_kmol_d: float
    beta: float = math.nan
    n_vapor_kmol_d: float = math.nan
    n_liquido_kmol_d: float = math.nan
    m_vapor_kg_d: float = math.nan
    m_liquido_kg_d: float = math.nan
    fechamento: object = None

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
class Cascata:
    """O trem inteiro de um caso, com a base, os estágios e o fechamento global."""
    caso: int
    fluido: str
    base: object
    estagios: list = field(default_factory=list)
    interrompida: str = ""     # por que a cascata parou antes do último estágio

    @property
    def completa(self):
        return not self.interrompida and len(self.estagios) == len(cfg()["cascata"]["sequencia"])

    @property
    def n_liquido_final(self):
        return self.estagios[-1].n_liquido_kmol_d if self.estagios else math.nan

    @property
    def n_vapor_total(self):
        return sum(e.n_vapor_kmol_d for e in self.estagios if math.isfinite(e.n_vapor_kmol_d))


def _condicoes(r, ponto, prem):
    """(T em °C, P em kPa) do estágio, lidos do próprio balanço — como na F5."""
    return r.T[ponto["corrente_gas"]], prem[ponto["pressao"]]


def cascata(r, dados, prem, mws_plus, composicoes=None):
    """A cascata composicional de um caso. Não toca em `r` nem no balanço."""
    comp = composicoes if composicoes is not None else dados.composicoes
    caso = dados.caso(r.num)
    z = {k: v for k, v in comp[r.fluid].items() if v > 0}
    pontos = {p["id"]: p for p in ig.pontos()}
    estagios, base, interrompida = [], None, ""
    n_atual, z_atual = math.nan, z
    for ident in cfg()["cascata"]["sequencia"]:
        ponto = pontos[ident]
        t_c, p_kpa = _condicoes(r, ponto, prem)
        try:
            e = et.flash_poco(c_para_k(t_c), kpa_para_pa(p_kpa), z_atual, mws_plus)
        except ValueError as err:
            interrompida = f"{ident}: {err}"
            break
        if not e.ok:
            estagios.append(Estagio(ident, ponto["corrente_gas"], t_c, p_kpa, dict(z_atual), e, n_atual))
            interrompida = f"{ident}: o flash não convergiu"
            break
        if base is None:                       # o MW adotado sai do primeiro flash: nenhum a mais
            base = base_molar(dados, caso, e)
            n_atual = base.n_F_kmol_d
        v, li = e.vapor, e.liquido
        b = v.fracao_molar if v is not None else 0.0
        n_v, n_l = b * n_atual, (1.0 - b) * n_atual
        estagios.append(Estagio(ident, ponto["corrente_gas"], t_c, p_kpa, dict(z_atual), e, n_atual,
                                beta=b, n_vapor_kmol_d=n_v, n_liquido_kmol_d=n_l,
                                m_vapor_kg_d=n_v * v.MW if v is not None else 0.0,
                                m_liquido_kg_d=n_l * li.MW if li is not None else 0.0,
                                fechamento=ig.conferir(e)))
        if li is None:
            interrompida = f"{ident}: sem fase líquida — não há alimentação para o estágio seguinte"
            break
        n_atual, z_atual = n_l, dict(li.composicao)
    return Cascata(r.num, r.fluid, base, estagios, interrompida)


# ------------------------------------------------------------------ fechamento do trem
@dataclass(frozen=True)
class FechamentoTrem:
    """O fechamento do TREM, não de um flash isolado: o que entrou tem de sair."""
    erro_molar_absoluto: float      # |ṅ_F − (Σ ṅ_V + ṅ_L,final)|, kmol/d
    erro_molar_relativo: float
    erro_massico_relativo: float
    erro_componente_max: float      # máx_i |ṅ_F·z_i − (Σ ṅ_V·y_i + ṅ_L,final·x_i)| / ṅ_F
    componente_pior: str
    erro_estagio_max: float         # pior fechamento de flash isolado da cascata
    estagios: int

    @property
    def ok(self):
        c = cfg()["fechamento"]
        return (self.erro_molar_relativo <= c["tolerancia_soma"]
                and self.erro_componente_max <= c["tolerancia_componente"]
                and self.erro_massico_relativo <= c["tolerancia_soma"])


def fechamento_trem(casc):
    """ṅ_HC,in = ṅ_V,F + ṅ_V,1 + ṅ_V,2 + ṅ_L,final, global e componente a componente."""
    es = [e for e in casc.estagios if e.ok and math.isfinite(e.beta)]
    if not es or casc.base is None:
        return None
    n_F = casc.base.n_F_kmol_d
    ultimo = es[-1]
    saida = sum(e.n_vapor_kmol_d for e in es) + ultimo.n_liquido_kmol_d
    erro_abs = abs(n_F - saida)
    m_F = casc.base.massa_kg_d
    m_saida = sum(e.m_vapor_kg_d for e in es) + ultimo.m_liquido_kg_d
    pior, erro_c = "", 0.0
    for k in es[0].z:
        entra = n_F * es[0].z[k]
        sai = sum(e.n_vapor_kmol_d * e.y.get(k, 0.0) for e in es) + ultimo.n_liquido_kmol_d * ultimo.x.get(k, 0.0)
        e_rel = abs(entra - sai) / n_F if n_F > 0 else math.nan
        if e_rel > erro_c:
            pior, erro_c = k, e_rel
    return FechamentoTrem(erro_abs, erro_abs / n_F if n_F > 0 else math.nan,
                          abs(m_F - m_saida) / m_F if m_F > 0 else math.nan, erro_c, pior,
                          max((e.fechamento.erro_componente_max for e in es if e.fechamento), default=0.0),
                          len(es))


def rodar(resultados, dados, prem, mws_plus, composicoes=None):
    """[(Cascata, FechamentoTrem)] de todos os casos. Não altera `resultados`."""
    out = []
    for r in resultados:
        c = cascata(r, dados, prem, mws_plus, composicoes)
        out.append((c, fechamento_trem(c)))
    return out
