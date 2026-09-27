"""R2 — reaproveitamento do feixe por restrição (docs/validacao/28-...).

Um mesmo ponto da malha é perguntado por vários critérios do motor (`requirement`, `derived`,
`case_admissible`), e todos falam do mesmo feixe. O resultado passou a ser calculado uma vez e
reaproveitado. A memória **vive no objeto de restrição**: não é global, não é persistente e não
atravessa execuções nem indivíduos da otimização.

O que estes testes prendem é o risco real dessa mudança: **reaproveitar o estado errado**. Se um
parâmetro do equipamento muda — passes, cascos, geometria, chicanas, sujeira, propriedades —,
trata-se de outra restrição, com outra memória, e o número tem de mudar junto.
"""
import math
from dataclasses import replace

import pytest

from fpso_siz.core.parametros import defaults, with_defaults
from fpso_siz.sizing.trocador import SaariLMTD, _feixe_calculado, _tubo

M = SaariLMTD()
N = 40.0
# De que o feixe REALMENTE depende. A lista foi levantada para o R2, porque reaproveitar um
# resultado exige saber exatamente o que o produz. Ela se divide em três, e a divisão é o
# resultado da investigação — não uma conveniência do teste.
#
# (a) entradas que mudam o feixe na configuração padrão:
ENTRADAS = {
    "passes": 1,                     # nº de passes no tubo (o padrão é 2)
    "d_i": 0.014,                    # geometria e diâmetros
    "d_o": 0.0254,
    "passo_m": 0.032,
    "area_tubo": 2.0e-4,
    "area_celula": 1.1,
    "layout": 45,                    # arranjo do feixe
    "espac_chicana": 0.6,            # chicanas
    "corte_chicana": 0.3,
    "pares_veda": 3.0,
    "folga_furo_m": 0.0012,
    "faixas_divisoras": 1.0,
    "ua_exigido": 5.0e5,             # térmicos
    "k_parede": 30.0,
    "rf_tubo": 5.0e-4,
    "rf_casco": 5.0e-4,
    "k_tubo": 0.2,
    "pr_tubo": 15.0,
    "m_casco": 25.0,
    "cp_casco": 3000.0,
    "mu_casco": 1.5e-3,
    "k_casco": 0.2,
    "m_tubo": 40.0,                  # hidráulicos
    "rho_tubo": 750.0,
    "mu_tubo": 6.0e-3,
}

# (b) entradas que só agem em OUTRA configuração — e é por isso que precisam de teste próprio:
#     `h_casco` só vale com Bell-Delaware desligado (com ele, h_o vem do método);
#     `razao_visc` só vale no regime de baixo Reynolds, com a película estendida ligada.
#
# (c) campos da restrição que o feixe NÃO lê: `n_serie` e `n_paralelo`. Eles agem ANTES, em
#     `sizing_constraints`, dividindo as vazões por casco — quando chegam aqui, o efeito deles
#     já está em `m_tubo`/`m_casco`. Estão testados como NÃO-dependência, para que a lista
#     acima seja uma afirmação verificada e não uma suposição.
SEM_EFEITO_NO_FEIXE = {"n_serie": 2, "n_paralelo": 2}


def restricao(**extra):
    vals = {**defaults(M.parameters()), **extra}
    ok, cons, _ = M.sizing_constraints(M.case_input(vals), with_defaults(M.parameters(), vals), M.constants())
    assert ok, cons
    return cons


@pytest.fixture
def base():
    return restricao()


def test_reaproveitar_da_o_mesmo_que_calcular(base):
    """A porta com reaproveitamento e o cálculo puro coincidem, campo a campo e bit a bit."""
    for n in (1.0, 10.0, N, 137.0, 400.0):
        direto = _feixe_calculado(base, n)
        for _ in range(3):                       # 1ª calcula, as outras reaproveitam
            t = _tubo(base, n)
            assert set(t) == set(direto)
            for chave, v in direto.items():
                w = t[chave]
                assert (w == v) or (isinstance(v, float) and math.isnan(v) and math.isnan(w)), chave


def test_alternar_entre_dois_pontos_nao_mistura(base):
    """A memória guarda um ponto só; alternar tem de recalcular, nunca devolver o outro."""
    a, b = _tubo(base, 30.0), _tubo(base, 60.0)
    assert a["v"] != b["v"]
    for _ in range(3):
        assert _tubo(base, 30.0)["v"] == a["v"]
        assert _tubo(base, 60.0)["v"] == b["v"]


CAMPOS = ("v", "re", "h_i", "h_o", "u", "area", "l", "n_total", "d_casco")


def _confere_independencia(base, outra):
    """A memória não é compartilhada, e calcular em uma não muda o que a outra devolve."""
    assert outra._ultimo_feixe is not base._ultimo_feixe, "a memória não pode ser compartilhada"
    t_base, t_outra = _tubo(base, N), _tubo(outra, N)
    # recalcular na ordem inversa não pode trazer o valor do outro objeto
    assert _tubo(outra, N)["u"] == t_outra["u"]
    assert _tubo(base, N)["u"] == t_base["u"]
    return t_base, t_outra


@pytest.mark.parametrize("campo,valor", sorted(ENTRADAS.items()))
def test_mudar_uma_entrada_do_equipamento_muda_o_feixe(campo, valor):
    """O risco do R2: reaproveitar através de estados diferentes. Cada restrição é um objeto com
    a sua própria memória — mudar uma entrada dá outro objeto e outro resultado."""
    base = restricao()
    t_base, t_outra = _confere_independencia(base, replace(base, **{campo: valor}))
    assert any(_difere(t_base[k], t_outra[k]) for k in CAMPOS), \
        f"{campo} = {valor} não mudou nada no feixe: ou não é entrada, ou o reaproveitamento cruzou estados"


def test_h_casco_e_entrada_quando_bell_delaware_esta_desligado():
    """Com Bell-Delaware ligado, h_o vem do método e `h_casco` é ignorado — de propósito. Com
    ele desligado, `h_casco` é a entrada do formulário, e tem de mudar o resultado."""
    base = replace(restricao(), bd_ativo=False)
    t_base, t_outra = _confere_independencia(base, replace(base, h_casco=2500.0))
    assert _difere(t_base["h_o"], t_outra["h_o"]) and _difere(t_base["u"], t_outra["u"])
    # e, com Bell-Delaware ligado, mudar h_casco não pode mexer em nada
    ligado = restricao()
    a, b = _confere_independencia(ligado, replace(ligado, h_casco=2500.0))
    assert all(not _difere(a[k], b[k]) for k in CAMPOS)


def test_razao_visc_e_entrada_no_regime_de_baixo_reynolds():
    """`razao_visc` entra pelo fator (µ/µ_parede)^0,14 da película estendida. No turbulento sem
    a extensão ela não é lida — por isso o teste força o regime onde ela vale."""
    laminar = replace(restricao(), baixo_re=True, mu_tubo=2.0)
    t_base, t_outra = _confere_independencia(laminar, replace(laminar, razao_visc=1.3))
    assert _difere(t_base["h_i"], t_outra["h_i"])


@pytest.mark.parametrize("campo,valor", sorted(SEM_EFEITO_NO_FEIXE.items()))
def test_cascos_agem_antes_do_feixe_e_nao_dentro_dele(campo, valor):
    """`n_serie` e `n_paralelo` NÃO são entradas do feixe: eles dividem as vazões em
    `sizing_constraints`, e o que chega aqui já é a vazão por casco. O teste fixa isso para que
    a lista de dependências seja afirmação verificada, e não suposição — se um dia passarem a
    ser lidos aqui, é este teste que avisa."""
    base = restricao()
    t_base, t_outra = _confere_independencia(base, replace(base, **{campo: valor}))
    assert all(not _difere(t_base[k], t_outra[k]) for k in CAMPOS)


def test_cascos_em_paralelo_mudam_o_feixe_pela_vazao():
    """A contraprova: pelo caminho certo — o parâmetro do método —, o arranjo de cascos muda o
    feixe, porque muda a vazão por casco."""
    base, dois = restricao(), restricao(cascos_paralelo=2.0)
    t_base, t_outra = _confere_independencia(base, dois)
    assert _difere(t_base["v"], t_outra["v"]) and _difere(t_base["re"], t_outra["re"])


def _difere(a, b):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return False
        return a != b
    return a != b


def test_a_memoria_nao_entra_na_igualdade():
    """`_ultimo_feixe` é detalhe de execução: duas restrições iguais continuam iguais depois de
    uma delas ter calculado. (A restrição nunca foi hasheável — ela já tinha campos `dict`
    antes do R2 —, então não há hash a preservar.)"""
    a, b = restricao(), restricao()
    assert a == b
    _tubo(a, N)
    assert a == b, "calcular não pode mudar a identidade da restrição"
    assert a._ultimo_feixe and not b._ultimo_feixe


def test_o_resultado_devolvido_e_independente(base):
    """Cada chamada devolve um dicionário próprio: escrever no resultado de uma não contamina a
    próxima. É o contrato que existia antes do R2, e ele foi mantido."""
    a = _tubo(base, N)
    a["u"] = -12345.0
    a["marcador"] = True
    b = _tubo(base, N)
    assert b["u"] != -12345.0 and "marcador" not in b


def test_a_memoria_e_por_objeto_e_morre_com_ele():
    """Não há estado global: uma restrição nova nasce sem memória, e o que a anterior calculou
    não a alcança."""
    a = restricao()
    assert a._ultimo_feixe == {}
    _tubo(a, N)
    assert a._ultimo_feixe.get("n") == N
    nova = restricao()
    assert nova._ultimo_feixe == {}
