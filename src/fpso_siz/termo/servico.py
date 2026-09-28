"""Serviço termodinâmico: a ÚNICA API pública de propriedades de fluido e de equilíbrio.

Duas famílias, cada uma com a sua proveniência declarada em `config/termo/proveniencia.toml`:

- **propriedades de fase na condição** (`gas`, `agua`, `agua_saturada`, `salmoura_fracao`,
  `oleo`, `oleo_vivo`, `emulsao`, `pressao_vapor_saturado`, `mu_interp`): o que o
  dimensionamento consome hoje. Cada função recebe a condição (T em °C, P em kPa), devolve nas
  unidades do projeto e, se receber um `Rastro`, anota cada propriedade com a fonte;
- **equilíbrio do fluido de poço** (`flash_tp`, `mw_mistura`, `conferir`): Peng-Robinson sobre
  componentes reais do banco e pseudo-componentes caracterizados (`termo/caracterizacao.py`).
  É o que o trem de separação do processo (`balanco/trem.py`) usa.

Regra das fontes: só entra o que tem fonte citável. O que não tem vira LACUNA — NaN, anotado
como tal — e nunca um número suposto. Condição fora da faixa de validade de uma correlação não
bloqueia: vira aviso. Ninguém fora de `termo/` fala com o backend (`termo/backend.py`).
"""
import math
from dataclasses import dataclass, field

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_f, c_para_k, kpa_para_pa, mgl_para_kgm3, pas_para_cp
from fpso_siz.termo import backend, caracterizacao

BLOCO = "propriedades"


def cfg():
    return carregar("termo/fluidos.toml")


def cfg_flash():
    return carregar("termo/flash.toml")


def versoes():
    """Versões do thermo/chemicals efetivamente usadas (vão para o JSON e o MC)."""
    return backend.versoes()


@dataclass(frozen=True)
class Gas:
    Z: float
    rho: float      # kg/m³
    mu: float       # cP
    k: float        # W/(m·K)
    VF: float       # fração vaporizada prevista pela EOS (1 = só vapor)
    avisos: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class Liquido:
    rho: float      # kg/m³
    mu: float       # cP
    cp: float       # J/(kg·K)
    k: float        # W/(m·K); NaN = lacuna de entrada
    avisos: tuple = field(default_factory=tuple)
    nota: str = ""  # correção aplicada à μ (ex.: óleo vivo), para a fonte da entrada


def _anotar(rastro, fonte, var, formula, valor, unidade):
    if rastro is not None:
        rastro.trace(BLOCO, fonte, var, formula, valor, unidade)


# ------------------------------------------------------------------ gás
def gas(y, MW, T_C, P_kPa, rastro=None):
    """Gás de composição `y` (frações do balanço, corte N2–nC4, P-03) e massa molar `MW` do
    balanço, a (T, P). Z pela EOS; ρ = P·MW/(Z·R·T) com MW e R do balanço, para que a vazão
    real (ṁ/ρ) seja coerente com a massa do balanço."""
    c = cfg()["gas"]
    comp = c["componentes"]
    faltam = sorted(set(y) - set(comp))
    if faltam:
        raise ValueError(f"componentes do gás sem identificador em fluidos.toml: {faltam}")
    T = c_para_k(T_C)
    e = backend.estado_gas([comp[k] for k in y], list(y.values()), T, kpa_para_pa(P_kPa), c["eos"], c["kij"])
    R = carregar("constantes.toml")["gas"]["R"]
    rho = P_kPa * MW / (e["Z"] * R * T)
    mu = pas_para_cp(e["mu"])
    avisos = []
    if e["VF"] < 1:
        avisos.append(f"a EOS prevê condensação parcial do gás a {T_C:.1f} °C e {P_kPa:.0f} kPa "
                      f"(fração vaporizada {e['VF']:.4f}); usadas as propriedades da fase vapor")
    _anotar(rastro, c["rotulo_eos"], "Z", f"EOS {c['eos']}, kij {c['kij']}, composição do balanço (P-03)", e["Z"], "–")
    _anotar(rastro, c["rotulo_z"], "ρ_g", "P·MW/(Z·R·T)", rho, "kg/m³")
    _anotar(rastro, c["rotulo_transporte"], "μ_g", f"mistura {e['metodo_mu']} sobre {'/'.join(e['metodo_mu_puros'])}",
            mu, "cP")
    _anotar(rastro, c["rotulo_transporte"], "k_g", f"mistura {e['metodo_k']}", e["k"], "W/(m·K)")
    return Gas(e["Z"], rho, mu, e["k"], e["VF"], tuple(avisos))


def gas_cp(y, T_C, P_kPa):
    """cp mássico [J/(kg·K)] e Z da fase vapor pela EOS (mesma composição e EOS de `gas`):
    comparação da F14 com o cp constante do balanço."""
    c = cfg()["gas"]
    comp = c["componentes"]
    e = backend.estado_gas([comp[k] for k in y], list(y.values()), c_para_k(T_C), kpa_para_pa(P_kPa), c["eos"],
                          c["kij"])
    return dict(cp=e["cp"], Z=e["Z"], VF=e["VF"])


# ------------------------------------------------------------------ água
def agua(T_C, P_kPa, rastro=None):
    """Água sem sal (diluição, S_D = 0): IAPWS. cp não é usado (vem do balanço): NaN."""
    c = cfg()["agua"]
    e = backend.agua_iapws(c_para_k(T_C), kpa_para_pa(P_kPa))
    mu = pas_para_cp(e["mu"])
    _anotar(rastro, c["rotulo"], "ρ_w", "IAPWS-95", e["rho"], "kg/m³")
    _anotar(rastro, c["rotulo"], "μ_w", "IAPWS 2008", mu, "cP")
    _anotar(rastro, c["rotulo"], "k_w", "IAPWS 2011", e["k"], "W/(m·K)")
    return Liquido(e["rho"], mu, math.nan, e["k"])


def agua_saturada(T_C, rastro=None):
    """Água pura de utilidade (circuito fechado de água quente ou de resfriamento; BOT 2.7.3.7.16
    e 3.3.2) como líquido saturado a T: a pressão do circuito não é dado do balanço."""
    c = cfg()["agua"]
    e = backend.agua_saturada_iapws(c_para_k(T_C))
    mu = pas_para_cp(e["mu"])
    base = "líquido saturado a T"
    _anotar(rastro, c["rotulo"], "ρ_w", f"IAPWS-95, {base}", e["rho"], "kg/m³")
    _anotar(rastro, c["rotulo"], "μ_w", f"IAPWS 2008, {base}", mu, "cP")
    _anotar(rastro, c["rotulo"], "k_w", f"IAPWS 2011, {base}", e["k"], "W/(m·K)")
    _anotar(rastro, c["rotulo"], "cp_w", f"IAPWS-95, {base}", e["cp"], "J/(kg·K)")
    return Liquido(e["rho"], mu, e["cp"], e["k"])


def fracao_sal(S_mgL, rho_std):
    """Fração mássica de sal de uma água de salinidade S (mg/L) e massa específica padrão ρ."""
    return mgl_para_kgm3(S_mgL) / rho_std


def salmoura(T_C, S_mgL, rho_std, rastro=None):
    """Água produzida como solução de NaCl: fração mássica w = S/ρ_padrão (S_W e rho_W das
    premissas). ρ, μ e cp de Laliberté (2009); k é lacuna (sem NaCl no banco de Magomedov)."""
    return salmoura_fracao(T_C, fracao_sal(S_mgL, rho_std), rastro)


def salmoura_fracao(T_C, w, rastro=None):
    """Fase aquosa como solução de NaCl de fração mássica w (ex.: água produzida misturada à
    de diluição, com o sal de cada uma). ρ, μ e cp de Laliberté (2009); k é lacuna."""
    c = cfg()["salmoura"]
    v, faixas = backend.salmoura_laliberte(c_para_k(T_C), w, c["sal"])
    avisos = [f"{p}: fora da faixa de Laliberté (T {tmin:g}–{tmax:g} °C, w ≤ {wmax:.3f}; aqui {T_C:.1f} °C, "
              f"w = {w:.3f})" for p, (tmin, tmax, wmax) in faixas.items()
              if not (tmin <= T_C <= tmax and w <= wmax)]
    mu = pas_para_cp(v["mu"])
    _anotar(rastro, c["rotulo"], "w_NaCl", "massa de sal / massa da fase aquosa", w, "–")
    _anotar(rastro, c["rotulo"], "ρ_w", "Laliberté, densidade", v["rho"], "kg/m³")
    _anotar(rastro, c["rotulo"], "μ_w", "Laliberté, viscosidade", mu, "cP")
    _anotar(rastro, c["rotulo"], "cp_w", "Laliberté, capacidade calorífica", v["cp"], "J/(kg·K)")
    _anotar(rastro, c["rotulo_lacuna_k"], "k_w", "entrada do usuário", math.nan, "W/(m·K)")
    return Liquido(v["rho"], mu, v["cp"], math.nan, tuple(avisos))


# ------------------------------------------------------------------ óleo
def mu_interp(tabela, T):
    """Viscosidade por interpolação log-linear em T numa tabela [(T °C, μ cP)] do BOT; fora da
    tabela, valor do extremo (P-40). Devolve (μ, marcador)."""
    (t_min, mu_min), (t_max, mu_max) = tabela[0], tabela[-1]
    if T <= t_min:
        return mu_min, f"extrapolado<{t_min}"
    if T >= t_max:
        return mu_max, f"limitado a {t_max} °C"
    for (t0, m0), (t1, m1) in zip(tabela, tabela[1:]):
        if t0 <= T <= t1:
            return math.exp(math.log(m0) + (math.log(m1) - math.log(m0)) * (T - t0) / (t1 - t0)), "interp."
    # inalcançável: com t_min < T < t_max, algum par consecutivo cerca T
    raise ValueError(f"tabela de viscosidade inválida em T = {T}")  # pragma: no cover


def oleo(poco, rho_std, T_C, rastro=None, rs_scf_stb=None):
    """Óleo: μ de óleo morto da tabela do poço (BOT) com a regra P-40 do balanço e, se
    `rs_scf_stb` é dado, a correção de óleo vivo de Beggs & Robinson (1975) com o gás
    dissolvido da corrente; ρ padrão pelo API. cp vem do balanço e k é lacuna."""
    c = cfg()["oleo"]
    mu, marcador = mu_interp(poco.viscosidade, T_C)
    avisos = [] if marcador == "interp." else [f"viscosidade do óleo {marcador} (tabela do BOT; P-40)"]
    nota = ""
    if rs_scf_stb is None:
        _anotar(rastro, c["rotulo_viscosidade"], "μ_o", f"óleo morto, log-linear em T ({marcador})", mu, "cP")
    else:
        _anotar(rastro, c["rotulo_viscosidade"], "μ_od", f"óleo morto, log-linear em T ({marcador})", mu, "cP")
        mu_od = mu
        mu, av = oleo_vivo(mu_od, rs_scf_stb, poco.api, T_C, rastro)
        avisos += av
        if mu != mu_od:
            nota = f"óleo vivo, {cfg()['oleo_vivo']['rotulo']}"
    _anotar(rastro, c["rotulo_densidade"], "ρ_o", "condição padrão, sem correção por T e Bo", rho_std, "kg/m³")
    return Liquido(rho_std, mu, math.nan, math.nan, tuple(avisos), nota)


def oleo_vivo(mu_od, rs_scf_stb, api, T_C, rastro=None):
    """(μ_o [cP], avisos): Beggs & Robinson (1975), μ_o = A·μ_od^B com A e B função do gás
    dissolvido Rs [scf/STB]; coeficientes e faixa de dados em fluidos.toml [oleo_vivo].
    Abaixo da faixa de Rs a correlação não é extrapolada: com os coeficientes arredondados ela
    não volta a μ_od quando Rs → 0 (dá um óleo vivo mais viscoso que o morto), e o valor medido
    do óleo morto (BOT) é mantido, conservador para a decantação."""
    c = cfg()["oleo_vivo"]
    rs_min, rs_max = c["faixa_rs_scf_stb"]
    if not rs_scf_stb >= rs_min:
        avisos = []
        if round(rs_scf_stb) > 0:
            avisos.append(f"Rs = {rs_scf_stb:.0f} scf/STB abaixo da faixa de Beggs & Robinson ({rs_min:g}–{rs_max:g} "
                          "scf/STB): mantido o óleo morto do BOT")
        _anotar(rastro, c["rotulo"], "μ_o", "Rs abaixo da faixa da correlação: óleo morto mantido", mu_od, "cP")
        return mu_od, avisos
    A = c["a"] * (rs_scf_stb + c["b"]) ** c["c"]
    B = c["d"] * (rs_scf_stb + c["e"]) ** c["f"]
    mu = A * mu_od ** B
    t_f = c_para_f(T_C)
    avisos = []
    if rs_scf_stb > rs_max:
        avisos.append(f"Rs = {rs_scf_stb:.0f} scf/STB acima da faixa de Beggs & Robinson ({rs_min:g}–{rs_max:g} scf/STB)")
    if not c["faixa_api"][0] <= api <= c["faixa_api"][1]:
        avisos.append(f"API {api:g} fora da faixa de Beggs & Robinson ({c['faixa_api'][0]:g}–{c['faixa_api'][1]:g})")
    if not c["faixa_t_f"][0] <= t_f <= c["faixa_t_f"][1]:
        avisos.append(f"T = {t_f:.0f} °F fora da faixa de Beggs & Robinson ({c['faixa_t_f'][0]:g}–{c['faixa_t_f'][1]:g} °F)")
    _anotar(rastro, c["rotulo"], "Rs", "gás dissolvido da corrente (balanço: trem nos casos avaliáveis, Standing nos "
            "demais)", rs_scf_stb, "scf/STB")
    _anotar(rastro, c["rotulo"], "μ_o", "óleo vivo: A·μ_od^B", mu, "cP")
    return mu, avisos


# ------------------------------------------------------------------ emulsão
def _fora(x, faixa):
    return not faixa[0] <= x <= faixa[1]


def emulsao(mu_c, mu_d, frac_d, rastro=None):
    """Viscosidade de emulsão (Zanker; Branan eq. 27-4):
    μ = (μ_C/δ_C)·(1 + a·μ_D·δ_D/(μ_D + μ_C)), δ_C = 1 − δ_D. Devolve (μ, avisos)."""
    c = cfg()["emulsao"]
    frac_c = 1 - frac_d
    mu = mu_c / frac_c * (1 + c["a"] * mu_d * frac_d / (mu_d + mu_c))
    checagens = [("μ da fase contínua", mu_c, c["mu_continua_cP"]), ("μ da fase dispersa", mu_d, c["mu_dispersa_cP"]),
                 ("fração contínua", frac_c, c["fracao_continua"]), ("fração dispersa", frac_d, c["fracao_dispersa"])]
    avisos = [f"{nome} = {v:.4g} fora da faixa de validade de Zanker ({faixa[0]:g}–{faixa[1]:g})"
              for nome, v, faixa in checagens if _fora(v, faixa)]
    _anotar(rastro, c["rotulo"], "μ_emulsão", f"(μC/δC)·(1 + {c['a']:g}·μD·δD/(μD + μC))", mu, "cP")
    return mu, tuple(avisos)


# ------------------------------------------------------------------ pressão de vapor
def pressao_vapor_saturado(P_vaso_kPa, rastro=None):
    """Líquido que sai de um vaso de separação está no ponto de bolha: Pv = P do vaso."""
    c = cfg()["vapor"]
    _anotar(rastro, c["rotulo"], "Pv", "líquido no ponto de bolha: Pv = P do vaso a montante", P_vaso_kPa, "kPa")
    return P_vaso_kPa


# ------------------------------------------------------------------ equilíbrio do fluido de poço
@dataclass(frozen=True)
class Fase:
    """Uma fase do equilíbrio, em SI. h, cp, μ e k não existem aqui: sem Cp_ig dos
    pseudo-componentes eles são AUSENTES por construção (ver a proveniência)."""
    nome: str                # "vapor" | "liquido"
    fracao_molar: float      # da mistura total
    fracao_massica: float
    composicao: dict         # {componente: fração molar na fase} — y no vapor, x no líquido
    Z: float
    MW: float                # g/mol
    rho: float               # kg/m³


@dataclass(frozen=True)
class EstadoTermodinamico:
    """O equilíbrio de uma composição a (T, P). Não convergir é estado (`ok = False`)."""
    T: float                 # K
    P: float                 # Pa
    z: dict                  # composição global, fração molar
    fases: tuple = ()
    avisos: tuple = ()
    ok: bool = True
    mensagem: str = ""

    def fase(self, nome):
        """A fase de nome dado, ou None se o equilíbrio não a prevê nesta condição."""
        return next((f for f in self.fases if f.nome == nome), None)

    @property
    def vapor(self):
        return self.fase("vapor")

    @property
    def liquido(self):
        return self.fase("liquido")

    @property
    def monofasico(self):
        return len(self.fases) == 1


def _conferir_entrada(T, P, z):
    if not (isinstance(T, (int, float)) and math.isfinite(T) and T > 0):
        raise ValueError(f"temperatura inválida: {T!r} (esperado K > 0)")
    if not (isinstance(P, (int, float)) and math.isfinite(P) and P > 0):
        raise ValueError(f"pressão inválida: {P!r} (esperado Pa > 0)")
    _conferir_composicao(z)


def _conferir_composicao(z):
    if not z:
        raise ValueError("composição vazia")
    for chave, v in z.items():
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
            raise ValueError(f"fração inválida para {chave!r}: {v!r}")
    tol = float(cfg_flash()["flash"]["tolerancia_composicao"])
    soma = sum(z.values())
    if abs(soma - 1.0) > tol:
        # não normalizar em silêncio: normalizar esconde erro de quem chama
        raise ValueError(f"as frações molares somam {soma!r}, e não 1 (tolerância {tol})")


def _componentes(z, mws_plus):
    """(reais, pseudos) na forma do backend: reais do banco pelo identificador de
    `[gas.componentes]`, pseudo-componentes pela caracterização."""
    comp = cfg()["gas"]["componentes"]
    mws_plus = mws_plus or {}
    reais, pseudos, faltam = [], [], []
    for pos, nome in enumerate(z):
        tipo = caracterizacao.classificar(nome, mws_plus or None)
        if tipo == caracterizacao.REAL:
            reais.append((pos, comp.get(nome, nome)))
        elif tipo == caracterizacao.PLUS and nome not in mws_plus:
            faltam.append(nome)
        else:
            p = caracterizacao.caracterizar(nome, mws_plus.get(nome))
            pseudos.append((pos, p.nome, p.MW, p.Tc, p.Pc, p.omega))
    if faltam:
        raise ValueError(f"fração plus sem MW do BOT: {sorted(faltam)}; informe `mws_plus`")
    return tuple(reais), tuple(pseudos)


def flash_tp(T, P, z, mws_plus):
    """Equilíbrio líquido-vapor de `z` (fração molar) a (T [K], P [Pa]): Peng-Robinson sobre
    componentes reais e pseudo-componentes (`mws_plus`: MW das frações plus, dado do BOT).

    Entrada inválida é ValueError; não convergir é `EstadoTermodinamico(ok=False)`."""
    _conferir_entrada(T, P, z)
    reais, pseudos = _componentes(z, mws_plus)
    chaves = list(z)
    try:
        r = backend.flash_pseudo(reais, pseudos, [z[k] for k in chaves], T, P, cfg()["gas"]["kij"])
    except (ArithmeticError, ValueError) as e:
        return EstadoTermodinamico(T=T, P=P, z=dict(z), ok=False,
                                   mensagem=f"o flash não convergiu a T = {T} K e P = {P} Pa: {e}")
    fases = tuple(Fase(nome=f["nome"], fracao_molar=f["fracao_molar"], fracao_massica=f["fracao_massica"],
                       composicao=dict(zip(chaves, f["composicao"])), Z=f["Z"], MW=f["MW"], rho=f["rho"])
                  for f in r["fases"])
    return EstadoTermodinamico(T=T, P=P, z=dict(z), fases=fases)


def pressao_bolha(T, z, mws_plus):
    """Pressão de ponto de bolha [Pa] do líquido `z` a T [K]: a maior pressão em que o flash
    ainda prevê vapor (β > 0), por bisseção geométrica sobre `flash_tp` (config/termo/flash.toml
    [bolha]). É uma leitura do mesmo equilíbrio, não correlação nova. Fora do intervalo: NaN."""
    c = cfg_flash()["bolha"]
    lo, hi = kpa_para_pa(c["P_min_kPa"]), kpa_para_pa(c["P_max_kPa"])

    def ferve(P):
        f = flash_tp(T, P, z, mws_plus)
        return f.ok and f.vapor is not None and f.vapor.fracao_molar > 0

    if not ferve(lo) or ferve(hi):
        return math.nan
    for _ in range(c["iteracoes"]):
        meio = math.sqrt(lo * hi)
        lo, hi = (meio, hi) if ferve(meio) else (lo, meio)
    return hi


def mw_mistura(z, mws_plus):
    """MW da mistura, Σ zᵢ·MWᵢ, com os MW ADOTADOS (banco para os reais, caracterização para
    os pseudo): os mesmos que o flash usa. Não é o MW verdadeiro do petróleo real."""
    _conferir_composicao(z)
    reais, pseudos = _componentes(z, mws_plus)
    mws = backend.mws_pseudo(reais, pseudos, cfg()["gas"]["kij"])
    return sum(z[k] * mw for k, mw in zip(z, mws))


@dataclass(frozen=True)
class Fechamento:
    """Os erros de fechamento de um flash, em número. Tudo aqui é invariante do equilíbrio e
    TUDO entra em `ok` — inclusive a coerência entre as bases molar e mássica."""
    erro_componente_max: float      # máx |z_i − (β·y_i + (1−β)·x_i)|
    componente_pior: str
    erro_soma_z: float              # |Σz − 1|
    erro_soma_y: float
    erro_soma_x: float
    erro_balanco_molar: float       # |Σβ − 1|
    erro_balanco_massico: float     # |Σβ_mássica − 1|
    coerencia_molar_massica: float  # |β_mássica − β·MW_v/MW_mistura|
    monofasico: bool

    @property
    def ok(self):
        c = cfg_flash()["fechamento"]
        return (self.erro_componente_max <= c["tolerancia_componente"]
                and max(self.erro_soma_z, self.erro_soma_y, self.erro_soma_x, self.erro_balanco_molar,
                        self.erro_balanco_massico, self.coerencia_molar_massica) <= c["tolerancia_soma"])


def conferir(estado):
    """Fechamento de um `EstadoTermodinamico` bifásico ou monofásico."""
    z = estado.z
    v, li = estado.vapor, estado.liquido
    soma_z = abs(sum(z.values()) - 1.0)
    if v is None or li is None:
        unica = v or li
        pior, erro = "", 0.0
        for k in z:
            e = abs((unica.composicao.get(k, 0.0) if unica else 0.0) - z[k])
            if e > erro:
                pior, erro = k, e
        soma_u = abs(sum(unica.composicao.values()) - 1.0) if unica else 1.0
        return Fechamento(erro, pior, soma_z, soma_u if v else 0.0, soma_u if li else 0.0,
                          abs((unica.fracao_molar if unica else 0.0) - 1.0),
                          abs((unica.fracao_massica if unica else 0.0) - 1.0), 0.0, True)
    b = v.fracao_molar
    pior, erro = "", 0.0
    for k in z:
        e = abs(b * v.composicao.get(k, 0.0) + (1.0 - b) * li.composicao.get(k, 0.0) - z[k])
        if e > erro:
            pior, erro = k, e
    mw_mist = b * v.MW + (1.0 - b) * li.MW
    return Fechamento(erro, pior, soma_z, abs(sum(v.composicao.values()) - 1.0),
                      abs(sum(li.composicao.values()) - 1.0), abs(v.fracao_molar + li.fracao_molar - 1.0),
                      abs(v.fracao_massica + li.fracao_massica - 1.0),
                      abs(v.fracao_massica - b * v.MW / mw_mist) if mw_mist > 0 else math.inf, False)
