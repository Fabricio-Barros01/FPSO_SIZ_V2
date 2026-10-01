"""Trocador casco-e-tubos — Saari (LUT), LMTD com fator F (Algoritmo 4.1), com o lado do
casco por Bell-Delaware (Branan). Port de sizing/exchanger/shell_and_tube.jl.

Não é vaso: varre o número de tubos por passe; a exigência é o comprimento de tubo L que
fecha U·A = q/(F·ΔT_lm); cada caso restringe pela velocidade no tubo e pela validade de
Dittus-Boelter (case_admissible); o conjunto, pelos tetos de casco e de comprimento.
Escolhe-se o feixe de MENOR área.
"""
import math
from dataclasses import dataclass, field, replace

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.contrato import Equipamento, ResultField, SweepAxis, SweepColumn, der
from fpso_siz.core.formato_julia import jl, jl_round
from fpso_siz.core.grade import faixa_julia
from fpso_siz.core.ieee import div
from fpso_siz.core.trace import Rastro
from fpso_siz.core.unidades import cp_para_pas, m_para_mm, mm_para_m
from fpso_siz.sizing.base import MetodoTOML, driver_case
from fpso_siz.sizing.bell_delaware import (ShellGeometry, baffle_clearance, com_chicanas, feixe_ideal,
                                           layout_pitches)
from fpso_siz.sizing.hidraulica import reynolds_pipe
from fpso_siz.sizing.pelicula import depende_do_comprimento, filme_tubo, temperatura_parede

EXCHANGER_KEYS = ("m_tubo", "cp_tubo", "t_tubo_in", "t_tubo_out", "rho_tubo", "mu_tubo", "k_tubo",
                  "m_casco", "cp_casco", "t_casco_in", "mu_casco", "k_casco")


def _t():
    return carregar("equipment/comum/trocador.toml")


class ShellTubeExchanger(Equipamento):
    method_id, label = "exchanger", "Trocador de Calor Casco-e-Tubos"


@dataclass(frozen=True)
class ExchangerDuty:
    m_tubo: float
    cp_tubo: float
    t_tubo_in: float
    t_tubo_out: float
    rho_tubo: float
    mu_tubo: float      # Pa·s
    k_tubo: float
    m_casco: float
    cp_casco: float
    t_casco_in: float
    mu_casco: float     # Pa·s
    k_casco: float


def lmtd(dt1, dt2):
    """ΔT médio logarítmico (Eq. 4.6); NaN se algum ΔT ≤ 0 (cruzamento)."""
    if not (math.isfinite(dt1) and math.isfinite(dt2) and dt1 > 0 and dt2 > 0):
        return math.nan
    r = dt1 / dt2
    if abs(r - 1.0) <= _t()["singularidades"]["tol_lmtd"]:
        return float(dt1)
    return (dt1 - dt2) / math.log(r)


def f_correction_1_2(p, r):
    """Fator F do arranjo 1 casco / 2 passes (Fig. 4.3); R = 1 é limite removível."""
    if not (math.isfinite(p) and math.isfinite(r)):
        return math.nan
    if p <= 0:
        return 1.0
    if p >= 1 or r * p >= 1:
        return math.nan
    s = math.sqrt(1 + r * r)
    den_log = (2 - p * (1 + r - s)) / (2 - p * (1 + r + s))
    if not (math.isfinite(den_log) and den_log > 0):
        return math.nan
    if abs(r - 1.0) <= _t()["singularidades"]["tol_f_r1"]:
        return math.sqrt(2.0) * (p / (1 - p)) / math.log(den_log)
    return s * math.log((1 - r * p) / (1 - p)) / ((1 - r) * math.log(den_log))


def nusselt_dittus_boelter(re, pr, aquecendo, k):
    """(Nu, dentro da faixa declarada?) — Eq. 6.23 na forma de Saari."""
    if not (math.isfinite(re) and re > 0 and math.isfinite(pr) and pr > 0):
        return math.nan, False
    e = _t()["dittus_boelter"]["expoente_re"]
    if aquecendo:
        nu = float(k["dittus_boelter_heating"]) * re ** e * pr ** float(k["dittus_boelter_pr_heating"])
    else:
        nu = float(k["dittus_boelter_cooling"]) * re ** e * pr ** float(k["dittus_boelter_pr_cooling"])
    valida = (float(k["dittus_boelter_re_min"]) <= re <= float(k["dittus_boelter_re_max"])
              and float(k["dittus_boelter_pr_min"]) <= pr <= float(k["dittus_boelter_pr_max"]))
    return nu, valida


def overall_u(h_i, h_o, rf_i, rf_o, d_i, d_o, k_w):
    """U referido à área externa, resistências em série (Eq. 5.7a)."""
    if not (h_i > 0 and h_o > 0 and d_i > 0 and d_o > d_i and k_w > 0):
        return math.nan
    razao = d_o / d_i
    r_tot = 1 / h_o + rf_o + d_o * math.log(razao) / (2 * k_w) + razao * rf_i + razao / h_i
    return 1 / r_tot


def parcelas_resistencia(h_i, h_o, rf_i, rf_o, d_i, d_o, k_w):
    """As cinco resistências em série de `overall_u` (m²·K/W, referidas à área externa),
    com as mesmas expressões e na mesma ordem: a soma é 1/U (memorial, F10x)."""
    razao = d_o / d_i
    return {"conveccao_casco": 1 / h_o, "incrustacao_casco": rf_o, "parede": d_o * math.log(razao) / (2 * k_w),
            "incrustacao_tubo": razao * rf_i, "conveccao_tubo": razao / h_i}


def effectiveness_ntu_counterflow(ntu, c_star):
    if not (math.isfinite(ntu) and ntu >= 0 and math.isfinite(c_star) and 0 <= c_star <= 1):
        return math.nan
    if abs(c_star - 1.0) <= _t()["singularidades"]["tol_ntu"]:
        return ntu / (1 + ntu)
    e = math.exp(-ntu * (1 - c_star))
    return (1 - e) / (1 - c_star * e)


@dataclass(frozen=True)
class ExchangerConstraints:
    q: float
    dt_lm: float
    f: float
    ua_exigido: float
    t_casco_out: float
    aquecendo: bool
    m_tubo: float
    rho_tubo: float
    mu_tubo: float
    pr_tubo: float
    k_tubo: float
    d_i: float
    d_o: float
    passes: int
    h_casco: float
    rf_tubo: float
    rf_casco: float
    k_parede: float
    area_tubo: float
    passo_m: float
    area_celula: float
    m_casco: float
    cp_casco: float
    mu_casco: float
    k_casco: float
    layout: int
    corte_chicana: float
    espac_chicana: float
    pares_veda: float
    folga_furo_m: float
    faixas_divisoras: float
    bd_ativo: bool
    kbd: dict
    k: dict
    n_serie: int = 1       # extensões do V2 (F10x.7): cascos iguais em série e em paralelo
    n_paralelo: int = 1
    # extensão do V2: película do lado tubo nos três regimes (Branan pp. 40-41). Com
    # `baixo_re = False` o cálculo é o do Julia — só Dittus-Boelter, e fora da faixa o caso é
    # recusado. `t_tubo_med`/`t_casco_med` servem à temperatura de parede da eq. 2-9.
    baixo_re: bool = False
    razao_visc: float = 1.0
    t_tubo_med: float = math.nan
    t_casco_med: float = math.nan
    # R2 — reaproveitamento do ÚLTIMO feixe calculado para esta restrição.
    #
    # NÃO é cache global, persistente nem compartilhado: o dicionário nasce e morre com ESTE
    # objeto, que o motor cria por caso dentro de uma execução de dimensionamento e descarta ao
    # terminá-la. Duas restrições diferentes — outro caso, outro nº de passes, outra geometria,
    # outro arranjo de cascos — são objetos diferentes, com memórias diferentes: a identidade do
    # estado é a identidade do objeto, e não uma chave que alguém precise manter correta.
    #
    # Guarda UM estado, o último `n`, porque é o que a estrutura do motor pede: `requirement`
    # calcula o ponto, e `derived` e `case_admissible` o releem no MESMO ponto da malha, antes
    # de a varredura andar (medido: 91.216 das 91.232 repetições do P-003 acontecem dentro de
    # 17 chamadas da primeira). Guardar a malha inteira custaria ~110 MB por dimensionamento e
    # não acrescentaria acerto nenhum.
    #
    # `init=False` é o que impede o pior erro possível aqui: sem ele, `dataclasses.replace()`
    # copiaria a REFERÊNCIA da memória para a restrição nova, e um estado calculado com um
    # número de passes poderia ser devolvido para outro. Com `init=False`, `replace()` não a
    # copia — a restrição nova nasce com memória própria e vazia. Há teste para isso.
    # `compare=False`: não entra na igualdade da restrição.
    _ultimo_feixe: dict = field(default_factory=dict, compare=False, repr=False, init=False)


@dataclass(frozen=True)
class GeometriaTrocador:
    """Geometria física congelada de uma unidade, usada exclusivamente em RATING."""
    tubos_por_passe: int
    comprimento: float


def avaliar_geometria(c, geometria):
    """Recalcula películas e UA numa geometria fixa, sem redimensionar o comprimento."""
    n = geometria.tubos_por_passe
    l = geometria.comprimento
    if n < 1 or l <= 0:
        return dict(VAZIO)
    n_total = n * c.passes
    v = c.m_tubo / (c.rho_tubo * n * c.area_tubo)
    re = reynolds_pipe(c.rho_tubo, v, c.d_i, c.mu_tubo)
    d_feixe = math.sqrt(4 * n_total * c.area_celula * (c.passo_m * c.passo_m) / math.pi)
    h_i, nu_valido, diag = _pelicula(c, _caminho(c, l), re)
    d_s = d_feixe + 2 * c.d_o
    if c.bd_ativo:
        folga = mm_para_m(baffle_clearance(m_para_mm(d_s), c.kbd))
        p_n, p_p, _ = layout_pitches(c.layout, c.passo_m, c.kbd)
        l_bc = c.espac_chicana * d_s
        geo = ShellGeometry(d_s, d_feixe, c.d_o, c.passo_m, p_n, p_p,
                            c.corte_chicana * d_s, l_bc, folga, c.folga_furo_m,
                            float(n_total), c.pares_veda, c.faixas_divisoras,
                            2 * c.d_o, c.layout)
        ideal = feixe_ideal(geo, c.m_casco, c.cp_casco, c.mu_casco, c.k_casco, c.kbd)
        n_b = max(l / l_bc - 1, 1.0)
        h_o, fat, ok = com_chicanas(ideal, n_b, l_bc, l_bc, l_bc, c.kbd)
        re_casco = fat.re
    else:
        h_o, n_b, re_casco, ok = c.h_casco, math.nan, math.nan, True
    u = overall_u(h_i, h_o, c.rf_tubo, c.rf_casco, c.d_i, c.d_o, c.k_parede)
    area = n_total * math.pi * c.d_o * l
    return dict(VAZIO, v=v, re=re, h_i=h_i, h_o=h_o, u=u, area=area,
                ua=u * area, l=l, n_total=float(n_total), d_casco=d_feixe,
                d_shell=d_s, re_casco=re_casco, n_chicanas=n_b,
                nu_valido=nu_valido, ok=ok and nu_valido and math.isfinite(u), **diag)


VAZIO = dict(v=math.inf, re=math.nan, h_i=math.nan, h_o=math.nan, u=math.nan, area=math.inf, l=math.inf, n_total=0.0,
             d_casco=math.inf, d_shell=math.inf, re_casco=math.nan, jc=math.nan, jl=math.nan, jb=math.nan,
             js=math.nan, jr=math.nan, j_produto=math.nan, h_ideal=math.nan, n_chicanas=math.nan, nu_valido=False,
             ok=False, regime="", correlacao="", motivo="", peso_transicao=math.nan, t_parede=math.nan)


def _pelicula(c, l_caminho, re):
    """(h_i, válido?, diagnóstico) do lado tubo. Sem a extensão, é o Dittus-Boelter do Julia; com
    ela, o regime que o Reynolds indicar (laminar/transição/turbulento), e o comprimento do caminho
    entra na correlação laminar — por isso ele é argumento, como o próprio Reynolds do feixe (a
    restrição é congelada e compartilhada por toda a varredura: nada por feixe entra nela)."""
    if not c.baixo_re:
        nu, valido = nusselt_dittus_boelter(re, c.pr_tubo, c.aquecendo, c.k)
        return nu * c.k_tubo / c.d_i, valido, {}
    f = filme_tubo(re, c.pr_tubo, c.k_tubo, c.d_i, l_caminho, c.aquecendo, c.k, c.razao_visc)
    return f.h, f.valido, dict(regime=f.regime, correlacao=f.correlacao, motivo=f.motivo, peso_transicao=f.peso)


def _tubo(c, n):
    """O feixe com n tubos por passe: velocidade, h_i, h_o, U, área, L, casco.

    Um mesmo ponto da malha é perguntado por vários critérios do motor — `requirement` pede o
    comprimento, `derived` pede os derivados, `case_admissible` pede a velocidade e a validade
    da correlação —, e todos falam do MESMO feixe. Calcula-se uma vez e reaproveita-se (R2,
    docs/validacao/28-...). Tudo o que o cálculo lê está em `c` e em `n`; nada vem de fora
    além das constantes do método, que não mudam durante a execução.

    Devolve uma CÓPIA: antes do R2 cada chamada devolvia um dicionário novo, e manter isso custa
    ~1 µs contra os ~78 µs do cálculo — barato demais para abrir mão da garantia de que ninguém
    escreve no resultado de outro."""
    ultimo = c._ultimo_feixe
    if ultimo.get("n") == n:
        return dict(ultimo["feixe"])
    feixe = _feixe_calculado(c, n)
    ultimo["n"], ultimo["feixe"] = n, feixe
    return dict(feixe)


def _feixe_calculado(c, n):
    """O cálculo em si, sem reaproveitamento."""
    if not n >= 1:
        return dict(VAZIO)
    n_total = n * c.passes
    v = c.m_tubo / (c.rho_tubo * n * c.area_tubo)
    re = reynolds_pipe(c.rho_tubo, v, c.d_i, c.mu_tubo)
    d_feixe = math.sqrt(4 * n_total * c.area_celula * (c.passo_m * c.passo_m) / math.pi)
    if not c.bd_ativo:
        # sem Bell-Delaware h_o é dado; com a película laminar, h_i depende de L e L de h_i:
        # ponto fixo com a mesma tolerância do laço de comprimento
        padrao = _t()["laco_comprimento"]
        tol, maxit = float(padrao["tolerancia"]), int(padrao["max_iteracoes"])
        l = math.inf
        por_iteracao = c.baixo_re and depende_do_comprimento(re, c.k)
        h_i, nu_valido, diag = _pelicula(c, l, re)
        u = area = math.nan
        for it in range(1, (maxit if por_iteracao else 1) + 1):
            if por_iteracao:
                h_i, nu_valido, diag = _pelicula(c, _caminho(c, l), re)
            u = overall_u(h_i, c.h_casco, c.rf_tubo, c.rf_casco, c.d_i, c.d_o, c.k_parede)
            if not (math.isfinite(u) and u > 0):
                break
            area = c.ua_exigido / u
            novo = area / (n_total * math.pi * c.d_o)
            if math.isfinite(l) and abs(novo - l) <= tol * max(1.0, abs(novo)):
                l = novo
                break
            l = novo
        return dict(VAZIO, v=v, re=re, h_i=h_i, h_o=c.h_casco, u=u, area=area, l=l, n_total=float(n_total),
                    d_casco=d_feixe, d_shell=d_feixe + 2 * c.d_o, nu_valido=nu_valido,
                    ok=math.isfinite(u) and u > 0, t_parede=_t_parede(c, u, h_i), **diag)
    return _tubo_bell_delaware(c, n_total, v, re, d_feixe)


def _caminho(c, l):
    """Comprimento do caminho de um tubo: passes × comprimento por passe (Branan p. 40). Enquanto
    L não é conhecido, o caminho é infinito, que dá o limite plenamente desenvolvido da 2-10 — o
    piso da correlação, e o ponto de partida do laço."""
    return c.passes * l if math.isfinite(l) and l > 0 else math.inf


def _t_parede(c, u, h_i):
    return temperatura_parede(c.t_tubo_med, c.t_casco_med, u, h_i, c.d_i, c.d_o) if c.baixo_re else math.nan


def _tubo_bell_delaware(c, n_total, v, re, d_feixe):
    """Bell-Delaware depende de L (nº de chicanas) e L depende de h_o: ponto fixo em L. Com a
    película de baixo Reynolds ligada, h_i também depende de L (correlação laminar de Hausen) e
    entra no mesmo ponto fixo — sem a extensão, h_i é constante e o laço é o do Julia.

    Das cinco correções da Eq. 2-18, **só Js depende do número de chicanas**: Jc, Jl, Jb, Jr,
    h_ideal, Re e A_s são função apenas da geometria e do escoamento do casco, que o laço não
    muda. Por isso o feixe é avaliado UMA vez, antes do laço (`feixe_ideal`), e cada passagem
    recombina só Js (`com_chicanas`). Não é cache: é a estrutura de dependência das equações, e
    a conta final é termo a termo a mesma, na mesma ordem.

    PREMISSA DO ARRANJO DE CHICANAS: os vãos de entrada e de saída são iguais ao vão central
    (`l_bi = l_bo = l_bc`) — ver `espac_chicana` e a nota do TOML. Nesse arranjo a Eq. 2-28 dá
    Js = 1 identicamente, e é isso que se observa. A equação continua aqui, completa e
    exercitada a cada passagem: um arranjo de vãos de ponta maiores (prática comum, por causa
    dos bocais) só precisa de uma entrada nova, sem tocar neste laço."""
    kbd = c.kbd
    padrao = _t()["laco_comprimento"]
    tol = float(kbd.get("tolerancia", padrao["tolerancia"]))
    maxit = int(kbd.get("max_iter", padrao["max_iteracoes"]))
    d_otl = d_feixe
    d_s = d_otl + 2 * c.d_o
    folga_mm = baffle_clearance(m_para_mm(d_s), kbd)
    p_n, p_p, _ = layout_pitches(c.layout, c.passo_m, kbd)
    l_bc = c.espac_chicana * d_s
    geo = ShellGeometry(d_s, d_otl, c.d_o, c.passo_m, p_n, p_p, c.corte_chicana * d_s, l_bc, mm_para_m(folga_mm),
                        c.folga_furo_m, float(n_total), c.pares_veda, c.faixas_divisoras, 2 * c.d_o, c.layout)
    l = u = area = h_o = math.nan
    fat = None
    n_b = 1.0
    ok = False
    # no turbulento h_i não depende de L: calcula-se uma vez, como antes da extensão. No laminar e
    # na transição (Hausen, Gz = Re·Pr·d/L) ele depende, e entra no ponto fixo.
    por_iteracao = c.baixo_re and depende_do_comprimento(re, c.k)
    h_i, nu_valido, diag = _pelicula(c, _caminho(c, l), re)
    # invariante no laço: a geometria do casco e o escoamento do casco não mudam com L
    feixe = feixe_ideal(geo, c.m_casco, c.cp_casco, c.mu_casco, c.k_casco, kbd)
    for it in range(1, maxit + 1):
        if por_iteracao:
            h_i, nu_valido, diag = _pelicula(c, _caminho(c, l), re)
        n_b = max(l / l_bc - 1, 1.0) if (math.isfinite(l) and l > 0 and l_bc > 0) else 1.0
        h_o, fat, bd_ok = com_chicanas(feixe, n_b, l_bc, l_bc, l_bc, kbd)
        if not bd_ok:
            return dict(VAZIO, v=v, re=re, h_i=h_i, n_total=float(n_total), d_casco=d_feixe, d_shell=d_s,
                        re_casco=fat.re, h_ideal=fat.h_ideal, nu_valido=nu_valido, **diag)
        u = overall_u(h_i, h_o, c.rf_tubo, c.rf_casco, c.d_i, c.d_o, c.k_parede)
        if not (math.isfinite(u) and u > 0):
            return dict(VAZIO, v=v, re=re, h_i=h_i, h_o=h_o, n_total=float(n_total), d_casco=d_feixe, d_shell=d_s,
                        nu_valido=nu_valido, **diag)
        area = c.ua_exigido / u
        novo = area / (n_total * math.pi * c.d_o)
        if math.isfinite(l) and abs(novo - l) <= tol * max(1.0, abs(novo)):
            l = novo
            ok = True
            break
        l = novo
        if it == maxit:
            ok = False
    return dict(VAZIO, v=v, re=re, h_i=h_i, h_o=h_o, u=u, area=area, l=l, n_total=float(n_total), d_casco=d_feixe,
                d_shell=d_s, re_casco=fat.re, jc=fat.jc, jl=fat.jl, jb=fat.jb, js=fat.js, jr=fat.jr,
                j_produto=fat.produto, h_ideal=fat.h_ideal, n_chicanas=n_b, nu_valido=nu_valido, ok=ok,
                t_parede=_t_parede(c, u, h_i), **diag)


class SaariLMTD(MetodoTOML):
    method_id = "saari_lmtd"
    config = "equipment/exchanger/saari_lmtd.toml"
    rotulo_padrao = "Saari — LMTD com fator F"
    config_extensoes = "equipment/exchanger/saari_extensoes.toml"

    def applies_to(self):
        return ShellTubeExchanger()

    def stream_keys(self):
        return ()

    def case_input(self, vals):
        faltando = [k for k in EXCHANGER_KEYS if k not in vals]
        if faltando:
            raise ValueError("caso sem as entradas do trocador: " + ", ".join(faltando))
        v = {k: float(vals[k]) for k in EXCHANGER_KEYS}
        return ExchangerDuty(v["m_tubo"], v["cp_tubo"], v["t_tubo_in"], v["t_tubo_out"], v["rho_tubo"],
                             cp_para_pas(v["mu_tubo"]), v["k_tubo"], v["m_casco"], v["cp_casco"], v["t_casco_in"],
                             cp_para_pas(v["mu_casco"]), v["k_casco"])

    def sizing_constraints(self, e, p, k):
        tr = Rastro()
        n_par = max(round(p.get("cascos_paralelo", 1.0)), 1)
        n_ser = max(round(p.get("cascos_serie", 1.0)), 1)
        if n_par > 1:   # cada casco em paralelo: 1/N das vazões dos dois lados, mesmas temperaturas
            e = replace(e, m_tubo=e.m_tubo / n_par, m_casco=e.m_casco / n_par)
            tr.trace("balanco", "Tab. 3.1", "cascos em paralelo", "vazões por casco = total/N", float(n_par), "–")
        c_tubo = e.m_tubo * e.cp_tubo
        c_casco = e.m_casco * e.cp_casco
        if not (math.isfinite(c_tubo) and c_tubo > 0):
            return False, "Capacidade térmica do lado tubo inválida: confira vazão mássica e cp.", tr
        if not (math.isfinite(c_casco) and c_casco > 0):
            return False, "Capacidade térmica do lado casco inválida: confira vazão mássica e cp.", tr
        q = c_tubo * (e.t_tubo_out - e.t_tubo_in)
        aquecendo = q > 0
        if not abs(q) > 0:
            return (False, "As temperaturas de entrada e saída do lado tubo são iguais: não há calor a trocar, e não "
                           "há trocador a dimensionar.", tr)
        t_casco_out = e.t_casco_in - q / c_casco
        tr.trace("balanco", "Eq. 4.5", "q", "ṁ·cp·(T_saída − T_entrada) no tubo", q, "W")
        tr.trace("balanco", "Eq. 4.5", "T_casco,saída", "T_casco,ent − q/(ṁ·cp)_casco", t_casco_out, "°C")
        if aquecendo:
            quente_in, quente_out, frio_in, frio_out = e.t_casco_in, t_casco_out, e.t_tubo_in, e.t_tubo_out
        else:
            quente_in, quente_out, frio_in, frio_out = e.t_tubo_in, e.t_tubo_out, e.t_casco_in, t_casco_out
        dt1 = quente_in - frio_out
        dt2 = quente_out - frio_in
        dtlm = lmtd(dt1, dt2)
        tr.trace("balanco", "Eq. 4.7", "ΔT₁", "T_quente,ent − T_frio,saída", dt1, "K")
        tr.trace("balanco", "Eq. 4.7", "ΔT₂", "T_quente,saída − T_frio,ent", dt2, "K")
        if not math.isfinite(dtlm):
            return (False, "Cruzamento de temperatura: com estas vazões e capacidades térmicas, um fluido ultrapassaria "
                           f"a temperatura de entrada do outro (ΔT₁ = {jl_round(dt1, 1)} K, ΔT₂ = {jl_round(dt2, 1)} K). "
                           "Nenhum trocador em contracorrente faz isso — reveja vazões, cp ou temperaturas.", tr)
        tr.trace("balanco", "Eq. 4.6", "ΔT_lm", "(ΔT₁ − ΔT₂)/ln(ΔT₁/ΔT₂)", dtlm, "K")
        passes = min(max(round(p["passes_tubo"]), 1), 2)
        fator = 1.0
        if passes == 2:
            p_ef = div(e.t_tubo_out - e.t_tubo_in, e.t_casco_in - e.t_tubo_in)
            r_ef = (e.t_casco_in - t_casco_out) / (e.t_tubo_out - e.t_tubo_in)
            fator = f_correction_1_2(abs(p_ef), abs(r_ef))
            tr.trace("balanco", "Fig. 4.3", "P", "ΔT do tubo / (T_casco,ent − T_tubo,ent)", abs(p_ef), "–")
            tr.trace("balanco", "Fig. 4.3", "R", "ΔT do casco / ΔT do tubo", abs(r_ef), "–")
            if not (math.isfinite(fator) and fator > 0):
                return (False, "O arranjo 1-2 não fecha com estas temperaturas: o fator de correção F sai do domínio da "
                               "Fig. 4.3. Em contracorrente puro (1 passe) o caso é viável — o cruzamento interno de um "
                               "segundo passe é que não é.", tr)
        tr.trace("balanco", "Fig. 4.3" if passes == 2 else "§4.2.1", "F",
                 "correção do arranjo 1-2" if passes == 2 else "contracorrente puro: F = 1", fator, "–")
        ua = abs(q) / (fator * dtlm)
        tr.trace("balanco", "Eq. 4.9", "U·A", "q/(F·ΔT_lm)", ua, "W/K")
        if n_ser > 1:   # N cascos iguais em série: cada um com 1/N do U·A (F do conjunto, conservador)
            ua = ua / n_ser
            tr.trace("balanco", "—", "U·A por casco", "U·A/N (cascos em série)", ua, "W/K")
        d_o = mm_para_m(p["d_externo"])
        d_i = d_o - 2 * mm_para_m(p["espessura"])
        if not d_i > 0:
            return (False, f"A espessura de parede ({jl(p['espessura'])} mm) consome o diâmetro externo "
                           f"({jl(p['d_externo'])} mm): não sobra seção livre no tubo.", tr)
        pr = div(e.cp_tubo * e.mu_tubo, e.k_tubo)
        if not (math.isfinite(pr) and pr > 0):
            return (False, "Prandtl do fluido do tubo inválido: confira cp, viscosidade e condutividade térmica.", tr)
        tr.trace("tubo", "§6.1.1", "Pr", "cp·µ/k", pr, "–")
        tr.trace("tubo", "§3.2.2", "d_i", "d_o − 2·espessura", m_para_mm(d_i), "mm")
        kbd = dict(k.get("bell_delaware", {}))
        bd_ativo = bool(kbd) and bool(kbd.get("ativo", False))
        if bd_ativo:
            if not (math.isfinite(e.mu_casco) and e.mu_casco > 0):
                return (False, "Viscosidade do fluido do casco inválida: sem ela não há Reynolds do casco, e o "
                               "coeficiente h_o não pode ser calculado.", tr)
            if not (math.isfinite(e.k_casco) and e.k_casco > 0):
                return (False, "Condutividade do fluido do casco inválida: sem ela não há Prandtl do casco, e o "
                               "coeficiente h_o não pode ser calculado.", tr)
            tr.trace("casco", "§6.1.1", "Pr (casco)", "cp·µ/k", div(e.cp_casco * e.mu_casco, e.k_casco), "–")
            tr.trace("casco", "Br. 2-18", "hipótese", "(µ/µ_parede)^0,14 = 1 — T de parede não iterada", 1.0, "–")
        padrao = _t()["layout"]
        layouts = [int(x) for x in kbd.get("layouts", padrao["layouts"])]
        layout = round(p["layout_tubos"])
        layout = layout if layout in [int(x) for x in padrao["layouts"]] else int(padrao["layouts"][0])
        razoes = [float(x) for x in kbd.get("area_celula_sobre_pt2", padrao["area_celula_sobre_pt2"])]
        area_celula = razoes[layouts.index(layout)] if layout in layouts else float(padrao["area_celula_sobre_pt2"][0])
        # extensão do V2: película do lado tubo nos três regimes (Branan pp. 40-41). Com o default
        # (0), o cálculo é o do Julia: só Dittus-Boelter, e fora da faixa o caso é recusado.
        baixo_re = bool(p.get("pelicula_baixo_re", 0.0))
        razao_visc = float(p.get("razao_visc_parede", 1.0))
        t_tubo_med = (e.t_tubo_in + e.t_tubo_out) / 2
        t_casco_med = (e.t_casco_in + t_casco_out) / 2
        if baixo_re:
            kp = carregar("equipment/comum/pelicula_tubo.toml")
            tr.trace("tubo", "Br. 2-10/2-12", "regimes do lado tubo",
                     "Hausen até Re = {:g}; interpolação até Re = {:g}; Dittus-Boelter acima".format(
                         kp["hausen"]["re_max"], kp["transicao"]["re_max"]), 1.0, "–")
            tr.trace("tubo", "Br. 2-9", "T média do tubo", "(T_entrada + T_saída)/2 do lado tubo", t_tubo_med, "°C")
            tr.trace("tubo", "Br. 2-9", "T média do casco", "(T_entrada + T_saída)/2 do lado casco", t_casco_med, "°C")
            tr.trace("tubo", "Br. 2-10", "hipótese", "(µ/µ_parede)^0,14 com razão declarada — a curva µ(T) é da "
                     "camada de propriedades, não do método", razao_visc, "–")
        cons = ExchangerConstraints(
            abs(q), dtlm, fator, ua, t_casco_out, aquecendo, e.m_tubo, e.rho_tubo, e.mu_tubo, pr, e.k_tubo, d_i, d_o,
            passes, p["h_casco"], p["rf_tubo"], p["rf_casco"], p["k_parede"], math.pi * (d_i * d_i) / 4,
            p["razao_passo"] * d_o, area_celula, e.m_casco, e.cp_casco, e.mu_casco, e.k_casco, layout,
            p["corte_chicana"], p["espacamento_chicana"], p["pares_veda"], mm_para_m(p["folga_furo_chicana"]),
            p["faixas_divisoras"], bd_ativo, kbd, dict(k), n_ser, n_par, baixo_re, razao_visc, t_tubo_med,
            t_casco_med)
        return True, cons, tr

    def sweep_axis(self, p):
        return SweepAxis("n_tubos", "tubos por passe", "–", faixa_julia(p["n_min"], p["n_step"], p["n_max"]))

    def global_keys(self):
        return ["n_min", "n_max", "n_step", "v_min", "v_max", "d_casco_max", "l_tubo_max"]

    def requirement(self, n, c):
        return _tubo(c, n)["l"]

    def governing_of(self, n, c):
        return "termica"

    def derived(self, n, l, gov, c, k, p):
        t = _tubo(c, n)
        return {"v": t["v"], "re": t["re"], "h_tubo": t["h_i"], "h_casco": t["h_o"], "re_casco": t["re_casco"],
                "h_ideal": t["h_ideal"], "jc": t["jc"], "jl": t["jl"], "jb": t["jb"], "js": t["js"], "jr": t["jr"],
                "j_produto": t["j_produto"], "n_chicanas": t["n_chicanas"], "nu_valido": 1.0 if t["nu_valido"] else 0.0,
                "pr": c.pr_tubo, "re_min_correlacao": float(k.get("dittus_boelter_re_min", math.nan)),
                "re_max_correlacao": float(k.get("dittus_boelter_re_max", math.nan)), "u": t["u"], "area": t["area"],
                "n_total": t["n_total"], "d_casco": m_para_mm(t["d_casco"]), "d_shell": m_para_mm(t["d_shell"]),
                "l": float(l), "l_sobre_d": l / t["d_casco"] if t["d_casco"] > 0 else math.nan, "q": c.q,
                "dt_lm": c.dt_lm, "f": c.f, "passes": float(c.passes)}

    def case_admissible(self, n, c, p):
        t = _tubo(c, n)
        return t["ok"] and t["nu_valido"] and p["v_min"] <= t["v"] <= p["v_max"]

    def admissible(self, n, der_, p):
        return der_.get("d_shell", math.inf) <= p["d_casco_max"] and der_.get("l", math.inf) <= p["l_tubo_max"]

    def objective(self, n, der_, p):
        return der_.get("area", math.inf)

    def envelope_params(self, params):
        v_min = max(p["v_min"] for p in params)
        v_max = min(p["v_max"] for p in params)
        if not v_min <= v_max:
            return (False, f"As bandas de velocidade no tubo pedidas pelos casos não se cruzam: um exige v ≥ {jl(v_min)} "
                           f"m/s e outro v ≤ {jl(v_max)} m/s. O feixe é um só.")
        return True, dict(n_min=min(p["n_min"] for p in params), n_max=max(p["n_max"] for p in params),
                          n_step=min(p["n_step"] for p in params), v_min=v_min, v_max=v_max,
                          d_casco_max=min(p["d_casco_max"] for p in params),
                          l_tubo_max=min(p["l_tubo_max"] for p in params),
                          banda_caso_projeto=max(p.get("banda_caso_projeto", 0.0) for p in params))

    # --- extensões do V2 (F10x.7)
    def caso_projeto(self, conss):
        """Caso de projeto do feixe (P-45): o de maior vazão volumétrica no tubo."""
        return max(range(len(conss)), key=lambda i: conss[i].m_tubo / conss[i].rho_tubo)

    def envelope_case_params(self, conss, p_env):
        """P-45: banda inteira no caso de projeto; nos de turndown só o teto (a velocidade abaixo
        do piso vira alerta em envelope_derived). A faixa de Dittus-Boelter continua exigida em
        todos os casos (case_admissible)."""
        if not p_env.get("banda_caso_projeto", 0.0) or not conss:
            return super().envelope_case_params(conss, p_env)
        projeto = self.caso_projeto(conss)
        turndown = {**p_env, "v_min": 0.0}
        return [p_env if i == projeto else turndown for i in range(len(conss))]

    def operacao_por_caso(self, conss, n, pcs):
        """Cada caso no feixe escolhido (mesma física): papel (projeto/turndown pela P-45), v, Re,
        Dittus-Boelter válido, h_i, h_o, U, comprimento exigido e alerta de v abaixo do piso."""
        projeto = self.caso_projeto(conss) if conss else -1
        v_min = max((pc["v_min"] for pc in pcs), default=0.0)
        out = []
        for i, c in enumerate(conss):
            t = _tubo(c, n)
            out.append(dict(papel="projeto" if i == projeto else "turndown", v=t["v"], re=t["re"],
                            nu_valido=bool(t["nu_valido"]), h_i=t["h_i"], h_o=t["h_o"], u=t["u"], l=t["l"], q=c.q,
                            abaixo_v_min=t["v"] < v_min,
                            # extensão do V2: o regime do lado tubo, a correlação que produziu h_i,
                            # o peso da interpolação na transição e a temperatura de parede da
                            # eq. 2-9 — é o que o relatório e o MC citam ao lado do coeficiente
                            regime=t.get("regime", ""), correlacao=t.get("correlacao", ""),
                            motivo=t.get("motivo", ""), peso_transicao=t.get("peso_transicao", math.nan),
                            t_parede=t.get("t_parede", math.nan)))
        return out

    def bloqueios(self, n, conss, pcs, p_env):
        """Critérios que reprovam o feixe com n tubos por passe (diagnóstico da reotimização,
        F10x.7), na ordem do dimensionamento: [(critério, índice do caso ou -1)]. Vazio = o
        feixe atende a todos os casos e aos tetos de geometria."""
        out = []
        ls = []
        for i, (c, pc) in enumerate(zip(conss, pcs)):
            t = _tubo(c, n)
            ls.append(t["l"])
            if not t["ok"]:
                out.append(("calculo", i))
                continue
            if t["v"] > pc["v_max"]:
                out.append(("v_max", i))
            if t["v"] < pc["v_min"]:
                out.append(("v_min_projeto" if pc["v_min"] > 0 and p_env.get("banda_caso_projeto", 0.0) else "v_min", i))
            if not t["nu_valido"]:
                out.append(("dittus_boelter", i))
        d_shell = m_para_mm(_tubo(conss[0], n)["d_shell"]) if conss else math.inf
        l_max = max((x for x in ls if math.isfinite(x)), default=math.inf)
        if l_max > p_env["l_tubo_max"]:
            out.append(("comprimento", -1))
        if d_shell > p_env["d_casco_max"]:
            out.append(("casco", -1))
        return out

    def envelope_derived(self, n, conss, pcs, p_env):
        """Conjunto de cascos no ponto escolhido: número em série e em paralelo, área por casco e
        total, caso de projeto e alertas de operabilidade/incrustação (P-45)."""
        if not conss:
            return {}
        c0 = conss[0]
        if c0.n_serie == 1 and c0.n_paralelo == 1 and not p_env.get("banda_caso_projeto", 0.0):
            return {}
        op = self.operacao_por_caso(conss, n, pcs)
        l_max = max(o["l"] for o in op)
        area_casco = n * c0.passes * math.pi * c0.d_o * l_max
        alertas = [i for i, o in enumerate(op) if o["papel"] == "turndown" and o["abaixo_v_min"]]
        return {"cascos_serie": float(c0.n_serie), "cascos_paralelo": float(c0.n_paralelo),
                "area_por_casco": area_casco, "area_total": area_casco * c0.n_serie * c0.n_paralelo,
                "caso_projeto": float(self.caso_projeto(conss)), "casos_abaixo_v_min": [float(i) for i in alertas]}

    def selection_message(self, rows, teto, p, mechanism="none"):
        if not rows:
            return "A grade de números de tubos ficou vazia."
        banda = f"{jl(p['v_min'])}–{jl(p['v_max'])} m/s"
        vs = [x for x in (r.derivados.get("v", math.nan) for r in rows) if math.isfinite(x)]
        na_banda = [r for r in rows if p["v_min"] <= r.derivados.get("v", math.nan) <= p["v_max"]]
        if not na_banda:
            lo, hi = (min(vs), max(vs)) if vs else (math.nan, math.nan)
            return (f"Nenhum feixe da grade mantém a velocidade no tubo na banda {banda}: na grade oferecida ela varia "
                    f"de {jl_round(lo, 2)} a {jl_round(hi, 2)} m/s. Amplie a grade de tubos, mude o diâmetro do tubo, "
                    "ou reveja a banda.")
        k = self.constants()
        validos = [r for r in na_banda if r.derivados.get("nu_valido", 1.0) != 0.0]
        if not validos:
            res = [x for x in (r.derivados.get("re", math.nan) for r in na_banda) if math.isfinite(x)]
            lo, hi = (min(res), max(res)) if res else (math.nan, math.nan)
            prs = [x for x in (r.derivados.get("pr", math.nan) for r in na_banda) if math.isfinite(x)]
            pr = prs[0] if prs else math.nan
            return (f"Na banda de velocidade {banda} todos os feixes caem fora da faixa em que Saari declara a "
                    f"correlação de Dittus-Boelter (Eq. 6.23): o Reynolds no tubo vai de {jl_round(lo, 0)} a "
                    f"{jl_round(hi, 0)} e o Prandtl vale {jl_round(pr, 1)}, contra "
                    f"{jl_round(float(k['dittus_boelter_re_min']), 0)}–{jl_round(float(k['dittus_boelter_re_max']), 0)} e "
                    f"{jl(k['dittus_boelter_pr_min'])}–{jl(k['dittus_boelter_pr_max'])}. Como h_i atravessa U, a área e o "
                    "comprimento, o programa não extrapola. Mude o diâmetro do tubo, reveja a viscosidade ou a "
                    "temperatura do fluido do tubo, ou desloque a banda de velocidade.")
        curto = [r for r in validos if r.derivados.get("l", math.inf) <= p["l_tubo_max"]]
        if not curto:
            menor_l = min(r.derivados.get("l", math.inf) for r in validos)
            return (f"Na banda de velocidade {banda} todos os feixes pedem tubo mais longo que o limite de "
                    f"{jl(p['l_tubo_max'])} m — o mais curto dá {jl_round(menor_l, 2)} m. Amplie a grade para mais "
                    "tubos, aceite tubo mais longo, ou melhore o coeficiente do casco.")
        menor = min(r.derivados.get("d_shell", math.inf) for r in curto)
        if not menor > p["d_casco_max"]:   # V2: a recusa veio de outro caso (Julia não chega aqui num caso só)
            return (f"Há feixes na banda de velocidade {banda}, dentro da faixa de Dittus-Boelter, com tubo até "
                    f"{jl(p['l_tubo_max'])} m e casco até {jl(p['d_casco_max'])} mm (o menor casco dá "
                    f"{jl_round(menor, 0)} mm). A recusa não veio deste caso.")
        return (f"Na banda de velocidade todos os feixes pedem casco maior que o limite de {jl(p['d_casco_max'])} mm — "
                f"o menor deles dá {jl_round(menor, 0)} mm. Use tubo de menor diâmetro, passo mais apertado, ou divida o "
                "serviço em dois cascos em paralelo.")

    def governing_label(self, g):
        return "área de troca térmica" if g == "termica" else str(g)

    # --- memorial (F10x): mesma física do dimensionamento, avaliada no ponto escolhido
    def parcelas_u(self, n, cons):
        """(resistências de 1/U [m²·K/W] com n tubos por passe, U [W/m²K])."""
        t = _tubo(cons, n)
        if not (math.isfinite(t["u"]) and t["u"] > 0):
            return {}, math.nan
        return parcelas_resistencia(t["h_i"], t["h_o"], cons.rf_tubo, cons.rf_casco, cons.d_i, cons.d_o,
                                    cons.k_parede), t["u"]

    def perfil_tq(self, e, cons):
        """Temperaturas terminais × calor acumulado a partir da entrada do tubo [W, °C]:
        o tubo vai de T_ent (0) a T_saída (q); o casco, em contracorrente, entra no fim
        do tubo (q) e sai no início (0). cp constante: perfis lineares entre os terminais."""
        return {"tubo": [(0.0, e.t_tubo_in), (cons.q, e.t_tubo_out)],
                "casco": [(0.0, cons.t_casco_out), (cons.q, e.t_casco_in)]}

    def requirement_spec(self):
        return ("comprimento de tubo", "m")

    def result_fields(self, r):
        tem = getattr(r, "feasible", True) and math.isfinite(r.x)
        ok = "neutro" if not tem else ("ok" if getattr(r, "ok", True) else "erro")
        return [
            ResultField("Tubos por passe", r.x if tem else math.nan, digits=0, highlight=True),
            ResultField("Comprimento do tubo L", r.y if tem else math.nan, unit="m", highlight=True),
            ResultField("Área de troca A", der(r, "area"), unit="m²"),
            ResultField("Tubos no total", der(r, "n_total"), digits=0),
            ResultField("Diâmetro do feixe", der(r, "d_casco"), unit="mm", digits=0),
            ResultField("Diâmetro do casco", der(r, "d_shell"), unit="mm", digits=0),
            ResultField("Esbeltez do feixe L/D", der(r, "l_sobre_d")),
            ResultField("Velocidade no tubo", der(r, "v"), unit="m/s", status=ok),
            ResultField("Reynolds no tubo", der(r, "re"), digits=0),
            ResultField("Coeficiente interno h_i", der(r, "h_tubo"), unit="W/m²K", digits=0),
            ResultField("Coeficiente do casco h_o", der(r, "h_casco"), unit="W/m²K", digits=0),
            ResultField("Correção de Bell-Delaware", der(r, "j_produto"), digits=3),
            ResultField("Coeficiente global U", der(r, "u"), unit="W/m²K", digits=1),
            ResultField("Carga térmica q", der(r, "q"), unit="W", digits=0),
            ResultField("ΔT médio logarítmico", der(r, "dt_lm"), unit="K"),
            ResultField("Fator de correção F", der(r, "f"), digits=3),
            ResultField("Caso governante", driver_case(r) if tem else "—"),
        ]

    def sweep_columns(self):
        return [SweepColumn("tubos/passe", "x", 0), SweepColumn("L (m)", "y"), SweepColumn("A (m²)", "area", 1),
                SweepColumn("v (m/s)", "v"), SweepColumn("U (W/m²K)", "u", 0)]

    def trace_blocks(self):
        return [("balanco", "Bloco A — balanço térmico e ΔT médio"), ("tubo", "Bloco B — lado do tubo"),
                ("casco", "Bloco C — lado do casco (Bell-Delaware)"), ("selection", "Seleção do feixe")]

    def grid_hint(self, p):
        return f"Verifique tubos mínimo ({jl(p['n_min'])}), máximo ({jl(p['n_max'])}) e passo ({jl(p['n_step'])})."

    def trace_selection(self, tr, best, p):
        d = best.derivados
        tr.trace("selection", "—", "tubos por passe", f"menor área com {jl(p['v_min'])} ≤ v ≤ {jl(p['v_max'])} m/s",
                 best.x, "–")
        tr.trace("selection", "§3.2.2", "v", "ṁ/(ρ·n·πd_i²/4)", d.get("v", math.nan), "m/s")
        tr.trace("selection", "§6.3", "Re", "ρvd_i/µ", d.get("re", math.nan), "–")
        tr.trace("selection", "Eq. 6.23", "h_i", "Nu·k/d_i (Dittus-Boelter)", d.get("h_tubo", math.nan), "W/m²K")
        if math.isfinite(d.get("j_produto", math.nan)):
            tr.trace("selection", "Br. 2-20", "Re (casco)", "d_o·W_s/(µ_s·A_s)", d.get("re_casco", math.nan), "–")
            tr.trace("selection", "Br. 2-19", "h_ideal", "j·cp·(W_s/A_s)·(k/(cp·µ))^(2/3)", d.get("h_ideal", math.nan),
                     "W/m²K")
            tr.trace("selection", "Br. 2-22", "Jc", "corte e espaçamento de chicana", d.get("jc", math.nan), "–")
            tr.trace("selection", "Br. 2-23", "Jl", "vazamento casco- e tubo-chicana", d.get("jl", math.nan), "–")
            tr.trace("selection", "Br. 2-27", "Jb", "desvio pelo vão feixe-casco", d.get("jb", math.nan), "–")
            tr.trace("selection", "Br. 2-28", "Js", "pontas de chicana alargadas", d.get("js", math.nan), "–")
            tr.trace("selection", "Br. 2-29", "Jr", "gradiente adverso (laminar)", d.get("jr", math.nan), "–")
            tr.trace("selection", "Br. 2-18", "h_o", "h_ideal·Jc·Jl·Jb·Js·Jr", d.get("h_casco", math.nan), "W/m²K")
        else:
            tr.trace("selection", "Tab. 4.1", "h_o", "informado (Bell-Delaware desligado)", d.get("h_casco", math.nan),
                     "W/m²K")
        tr.trace("selection", "Eq. 5.7a", "U", "resistências em série, área externa", d.get("u", math.nan), "W/m²K")
        tr.trace("selection", "Eq. 4.4", "A", "q/(U·F·ΔT_lm)", d.get("area", math.nan), "m²")
        tr.trace("selection", "—", "L", "A/(N·π·d_o)", best.y, "m")
        tr.trace("selection", "Br. 2-13", "d_feixe", "√(4·N·A_célula/π)", d.get("d_casco", math.nan), "mm")
        tr.trace("selection", "Br. 2-17", "D_casco", "d_feixe + 2·d_o", d.get("d_shell", math.nan), "mm")
