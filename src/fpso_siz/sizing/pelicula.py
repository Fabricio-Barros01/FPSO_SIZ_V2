"""Coeficiente de película do lado tubo nos três regimes (extensão do V2).

O Julia — e, até aqui, este programa — só tinha o regime **turbulento** (Dittus-Boelter na forma
de Saari, eq. 6.23): fora de 10⁴ ≤ Re ≤ 1,2·10⁵ o caso era recusado, e era essa recusa que
mantinha abertos os alarmes do P-001, do P-002 e do P-003 em baixa carga. Aqui entram os outros
dois regimes, pela fonte primária do acervo (Branan, cap. 2, pp. 40-41):

    laminar     Re ≤ 2000       Hausen, eq. 2-10
    transição   2000 < Re < 10⁴ interpolação linear, eq. 2-12
    turbulento  Re ≥ 10⁴        Dittus-Boelter (Saari 6.23), o ramo JÁ validado

A ponta turbulenta da interpolação é a **própria 6.23**, e não a 2-11 do Branan: assim a
interpolação encosta exatamente no ramo validado em Re = 10⁴ e o comportamento turbulento não
muda em nada (há teste de regressão). Constantes, domínios, política de transição e a errata do
denominador de Hausen estão em `config/equipment/comum/pelicula_tubo.toml`.

**O que este módulo não faz:** não avalia propriedades (recebe as do caso), não itera a
temperatura de parede contra a curva µ(T) — calcula a temperatura de parede pela eq. 2-9 e recebe
a razão de viscosidades como entrada declarada — e não estende domínio nenhum: o que a fonte não
cobre volta como `valido = False` com o motivo, que o motor trata como inviabilidade com mensagem.
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.ieee import div

LAMINAR, TRANSICAO, TURBULENTO, INDEFINIDO = "laminar", "transicao", "turbulento", "indefinido"


def cfg():
    return carregar("equipment/comum/pelicula_tubo.toml")


@dataclass(frozen=True)
class Filme:
    """O coeficiente de película do lado tubo e a sua procedência."""
    h: float             # W/(m²·K)
    nu: float
    re: float
    regime: str
    correlacao: str
    valido: bool
    motivo: str = ""     # por que a correlação não se aplica (vazio se aplica)
    peso: float = math.nan   # peso da interpolação na transição (0 = laminar, 1 = turbulento)
    fator_parede: float = 1.0

    @property
    def na_transicao(self):
        return self.regime == TRANSICAO


def graetz(re, pr, d_i, l_caminho):
    """Gz = Re·Pr·(d_i/L) — L é o comprimento do CAMINHO de um tubo (Branan p. 40: "if there are
    10 tubes per pass then L is the total length of tubing divided by 10"). Tubo infinitamente
    longo dá Gz = 0, que é o limite de escoamento plenamente desenvolvido."""
    if not (math.isfinite(l_caminho) and l_caminho > 0):
        return 0.0
    return re * pr * d_i / l_caminho


def nusselt_hausen(re, pr, d_i, l_caminho, kf=None):
    """Nu da eq. 2-10 (Hausen), sem o fator de parede. Gz = 0 dá o valor plenamente
    desenvolvido (3,66), que é o piso da correlação."""
    k = (kf or cfg())["hausen"]
    gz = graetz(re, pr, d_i, l_caminho)
    if not (math.isfinite(gz) and gz >= 0):
        return math.nan
    return float(k["nu_desenvolvido"]) + float(k["coef_entrada"]) * gz / (
        1 + float(k["coef_denominador"]) * gz ** float(k["expoente_denominador"]))


def nusselt_sieder_tate_laminar(re, pr, d_i, l_caminho, kf=None):
    """Nu da eq. 6.31 de Saari (Sieder-Tate laminar, via Incropera). NÃO entra no
    dimensionamento: é a segunda via do acervo, usada para arbitrar o denominador de Hausen."""
    k = (kf or cfg())["sieder_tate_laminar"]
    gz = graetz(re, pr, d_i, l_caminho)
    if not (math.isfinite(gz) and gz > 0):
        return math.nan
    return float(k["coeficiente"]) * gz ** float(k["expoente"])


def temperatura_parede(t_fluido_tubo, t_fluido_casco, u_externo, h_i, d_i, d_o):
    """Eq. 2-9: T_parede = t + (U_i/h_i)·(T − t), com U referido à área INTERNA (U_i = U_o·d_o/d_i).
    NaN quando falta algum operando — a temperatura de parede é diagnóstico, não trava o cálculo."""
    if not (math.isfinite(u_externo) and u_externo > 0 and math.isfinite(h_i) and h_i > 0 and d_i > 0):
        return math.nan
    if not (math.isfinite(t_fluido_tubo) and math.isfinite(t_fluido_casco)):
        return math.nan
    u_interno = u_externo * d_o / d_i
    return t_fluido_tubo + div(u_interno, h_i) * (t_fluido_casco - t_fluido_tubo)


def _turbulento(re, pr, aquecendo, k_metodo):
    """Dittus-Boelter na forma de Saari (o ramo já validado), com a sua faixa declarada."""
    from fpso_siz.sizing.trocador import nusselt_dittus_boelter
    return nusselt_dittus_boelter(re, pr, aquecendo, k_metodo)


def _fora_de_pr(pr, k_metodo):
    return not (float(k_metodo["dittus_boelter_pr_min"]) <= pr <= float(k_metodo["dittus_boelter_pr_max"]))


def depende_do_comprimento(re, k_metodo, kf=None):
    """True se h_i depende do comprimento do tubo, isto é, se o Reynolds cai no laminar ou na
    transição — onde a correlação é a de Hausen (Gz = Re·Pr·d/L) ou a interpolação que a usa. No
    turbulento, Dittus-Boelter não vê o comprimento, e quem chama pode calcular a película UMA VEZ
    por feixe em vez de a cada iteração do laço de comprimento."""
    kf = kf or cfg()
    return math.isfinite(re) and re > 0 and re < float(k_metodo["dittus_boelter_re_min"])


def filme_tubo(re, pr, k_fluido, d_i, l_caminho, aquecendo, k_metodo, razao_visc=None, kf=None):
    """`Filme` do lado tubo no regime que o Reynolds indica.

    Fora do que as fontes cobrem, devolve `valido = False` com o motivo — e o motivo é específico,
    porque é ele que vai para a mensagem de inviabilidade: Reynolds acima da faixa de
    Dittus-Boelter e Prandtl fora dela são recusas diferentes, e só a segunda não é resolvida por
    correlação de baixo Reynolds nenhuma."""
    kf = kf or cfg()
    exp_parede = float(kf["parede"]["expoente"])
    razao = float(kf["parede"]["razao_padrao"]) if razao_visc is None else float(razao_visc)
    fator = razao ** exp_parede if math.isfinite(razao) and razao > 0 else 1.0
    vazio = Filme(math.nan, math.nan, re, INDEFINIDO, "", False, "", math.nan, fator)
    if not (math.isfinite(re) and re > 0 and math.isfinite(pr) and pr > 0):
        return replace_motivo(vazio, "Reynolds ou Prandtl do lado tubo não são números positivos.")
    if not (math.isfinite(k_fluido) and k_fluido > 0 and math.isfinite(d_i) and d_i > 0):
        return replace_motivo(vazio, "condutividade ou diâmetro interno do tubo inválidos.")

    lam, tr = kf["hausen"], kf["transicao"]
    re_lam = float(lam["re_max"])
    re_turb = float(k_metodo["dittus_boelter_re_min"])
    re_turb_max = float(k_metodo["dittus_boelter_re_max"])

    def com(nu, regime, correlacao, peso=math.nan):
        h = nu * fator * k_fluido / d_i
        ok = math.isfinite(h) and h > 0
        return Filme(h, nu * fator, re, regime, correlacao, ok,
                     "" if ok else "o coeficiente de película não resultou em número positivo.", peso, fator)

    if re <= re_lam:
        nu = nusselt_hausen(re, pr, d_i, l_caminho, kf)
        return com(nu, LAMINAR, "Hausen (Branan eq. 2-10)")
    if re >= re_turb:
        nu, valida = _turbulento(re, pr, aquecendo, k_metodo)
        f = com(nu, TURBULENTO, "Dittus-Boelter (Saari eq. 6.23)")
        if valida:
            return f
        if re > re_turb_max:
            return replace_motivo(f, f"Reynolds de {re:,.0f} acima do teto de {re_turb_max:,.0f} da faixa de "
                                     "Dittus-Boelter; a fonte não cobre este regime.")
        return replace_motivo(f, f"Prandtl de {pr:,.2f} fora da faixa de {k_metodo['dittus_boelter_pr_min']:g} a "
                                 f"{k_metodo['dittus_boelter_pr_max']:g} em que Dittus-Boelter é declarada; nenhuma "
                                 "correlação de baixo Reynolds resolve isto.")
    # transição: as duas correlações no MESMO Reynolds, interpoladas (eq. 2-12)
    nu_lam = nusselt_hausen(re, pr, d_i, l_caminho, kf)
    nu_turb, _ = _turbulento(re, pr, aquecendo, k_metodo)
    peso = (re - float(tr["re_min"])) / float(tr["divisor"])
    nu = nu_lam + (nu_turb - nu_lam) * peso
    f = com(nu, TRANSICAO, "interpolação laminar↔turbulento (Branan eq. 2-12)", peso)
    if _fora_de_pr(pr, k_metodo):
        # a ponta turbulenta da interpolação é Dittus-Boelter: fora da faixa de Pr dela, a
        # interpolação não tem ponta válida, e a transição também não está coberta
        return replace_motivo(f, f"Prandtl de {pr:,.2f} fora da faixa de {k_metodo['dittus_boelter_pr_min']:g} a "
                                 f"{k_metodo['dittus_boelter_pr_max']:g} da correlação turbulenta, que é a ponta "
                                 "superior da interpolação de transição; a faixa não está coberta.")
    return f


def replace_motivo(f, motivo):
    """Mesmo filme, marcado como não aplicável, com o motivo (dataclass congelada)."""
    return Filme(f.h, f.nu, f.re, f.regime, f.correlacao, False, motivo, f.peso, f.fator_parede)
