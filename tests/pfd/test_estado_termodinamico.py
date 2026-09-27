"""Fase 3 — serviço termodinâmico ativo (`pfd/estado_termodinamico.py`).

O serviço é a camada que o processo poderá CHAMAR: `flash_tp(T, P, z, fluido)`. Nesta fase ele
é só disponibilizado — nada do balanço nem do dimensionamento passa por ele.

O que estes testes prendem, em ordem de importância:

1. **o serviço não cria uma segunda verdade.** Onde o PFD já calcula a mesma coisa
   (`fluidos.gas`, `fluidos.agua`, `fluidos.salmoura_fracao`), o serviço tem de dar o MESMO
   número, bit a bit — senão passam a existir duas termodinâmicas no programa;
2. o contrato: fases, composições, frações, propriedades, unidades e base declarada;
3. lacuna é NaN declarada, nunca número suposto;
4. não convergir é estado; entrada inválida é erro de quem chama;
5. a interface não conhece biblioteca nenhuma.
"""
import math

import pytest

from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import estado_termodinamico as et
from fpso_siz.pfd import fluidos

Z_GAS = {"N2": 0.02, "CO2": 0.03, "C1": 0.70, "C2": 0.12, "C3": 0.08, "nC4": 0.05}
T_K, P_PA = 330.0, 2.5e6
BIFASICO = (250.0, 5.0e6)


def mesmo(a, b):
    return (math.isnan(a) and math.isnan(b)) or a == b


# ------------------------------------------------------------------ 1. uma verdade só
def test_o_vapor_do_servico_e_o_mesmo_gas_do_pfd():
    """`fluidos.gas` e o serviço falam com a MESMA EOS pela mesma porta: Z, μ e k têm de sair
    idênticos. Se divergirem, o programa passou a ter duas termodinâmicas."""
    g = fluidos.gas(Z_GAS, 23.1523, T_K - 273.15, P_PA / 1000.0)
    v = et.flash_tp(T_K, P_PA, Z_GAS, "hidrocarboneto").vapor
    assert v is not None
    assert mesmo(v.Z, g.Z)
    assert mesmo(v.k, g.k)
    from fpso_siz.core.unidades import pas_para_cp
    assert mesmo(pas_para_cp(v.mu), g.mu)


def test_a_agua_do_servico_e_a_mesma_agua_do_pfd():
    """A fase IAPWS-95 do backend e as funções de `chemicals` são a mesma norma; o serviço só
    acrescenta cp e h. ρ, μ e k não podem mudar."""
    a = fluidos.agua(T_K - 273.15, P_PA / 1000.0)
    liq = et.flash_tp(T_K, P_PA, {"H2O": 1.0}, "agua").liquido
    from fpso_siz.core.unidades import pas_para_cp
    assert mesmo(liq.rho, a.rho) and mesmo(liq.k, a.k) and mesmo(pas_para_cp(liq.mu), a.mu)
    # e o que o serviço acrescenta existe
    assert math.isfinite(liq.cp) and liq.cp > 0 and math.isfinite(liq.h)


def test_a_salmoura_do_servico_e_a_mesma_do_pfd():
    w = 0.035
    s = fluidos.salmoura_fracao(T_K - 273.15, w)
    aq = et.flash_tp(T_K, P_PA, {"NaCl": w}, "salmoura").aquosa
    from fpso_siz.core.unidades import pas_para_cp
    assert mesmo(aq.rho, s.rho) and mesmo(aq.cp, s.cp) and mesmo(pas_para_cp(aq.mu), s.mu)


# ------------------------------------------------------------------ 2. o contrato
def test_monofasico_devolve_uma_fase_coerente():
    e = et.flash_tp(T_K, P_PA, Z_GAS, "hidrocarboneto")
    assert e.ok and e.monofasico and e.fracao_vapor == 1.0 and e.liquido is None
    v = e.vapor
    assert v.fracao_molar == 1.0 and v.fracao_massica == 1.0
    assert v.composicao == pytest.approx(Z_GAS)          # sem líquido, y = z
    assert all(math.isfinite(x) and x > 0 for x in (v.Z, v.rho, v.cp, v.mu, v.k, v.MW))
    assert math.isfinite(v.h) and math.isfinite(e.h)


def test_bifasico_devolve_x_y_e_as_duas_fracoes():
    e = et.flash_tp(*BIFASICO, Z_GAS, "hidrocarboneto")
    assert e.ok and not e.monofasico and len(e.fases) == 2
    v, l = e.vapor, e.liquido
    assert 0 < e.fracao_vapor < 1 and 0 < e.fracao_vapor_massica < 1
    assert v.fracao_molar + l.fracao_molar == pytest.approx(1.0)
    assert v.fracao_massica + l.fracao_massica == pytest.approx(1.0)
    for f in (v, l):
        assert sum(f.composicao.values()) == pytest.approx(1.0)
        assert set(f.composicao) == set(Z_GAS)
    # o balanço de componente fecha: z = β·y + (1−β)·x
    for comp in Z_GAS:
        recomposto = v.fracao_molar * v.composicao[comp] + l.fracao_molar * l.composicao[comp]
        assert recomposto == pytest.approx(Z_GAS[comp], abs=1e-9), comp
    # o líquido é mais pesado e mais denso que o vapor
    assert l.rho > v.rho and l.MW > v.MW and l.Z < v.Z
    # entalpia da mistura = média pelas frações MÁSSICAS
    assert e.h == pytest.approx(v.fracao_massica * v.h + l.fracao_massica * l.h)


def test_o_estado_declara_modelo_backend_fonte_e_referencia_de_entalpia():
    for fluido, z in (("hidrocarboneto", Z_GAS), ("agua", {"H2O": 1.0}), ("salmoura", {"NaCl": 0.035})):
        e = et.flash_tp(T_K, P_PA, z, fluido)
        d = et.declaracao(fluido)
        assert e.fluido == fluido and e.modelo == d["modelo"] and e.fonte == d["fonte"]
        assert e.base_composicao == d["base_composicao"]
        assert e.referencia_entalpia == d["referencia_entalpia"] and e.referencia_entalpia.strip()
        assert "thermo" in e.backend and "chemicals" in e.backend
        assert {f.nome for f in e.fases} <= set(d["fases"])


def test_a_base_de_composicao_nao_e_a_mesma_para_todos():
    """Hidrocarboneto e água recebem fração MOLAR; salmoura recebe fração MÁSSICA de sal. É
    declarado, e não adivinhado — por isso o estado carrega a base que usou."""
    bases = {f: et.declaracao(f)["base_composicao"] for f in et.fluidos_declarados()}
    assert bases["hidrocarboneto"] == bases["agua"] == "fracao_molar"
    assert bases["salmoura"] == "fracao_massica_de_sal"


# ------------------------------------------------------------------ 3. lacunas
def test_lacuna_e_nan_declarada_nunca_numero_suposto():
    aq = et.flash_tp(T_K, P_PA, {"NaCl": 0.035}, "salmoura").aquosa
    assert math.isnan(aq.k) and math.isnan(aq.h), "Laliberté não dá k nem h: têm de vir NaN"
    assert math.isnan(aq.Z) and math.isnan(aq.MW)
    declaradas = {x["grandeza"] for x in et.lacunas("salmoura")}
    assert any("condutividade" in g for g in declaradas) and any("ntalpia" in g for g in declaradas)
    for x in et.lacunas():
        assert x["motivo"].strip() and x["quando"].strip() and x["fluido"] in et.fluidos_declarados()


def test_a_fracao_pesada_e_lacuna_e_nao_numero_inventado():
    """C20+ não tem Tc/Pc/ω: o serviço RECUSA, em vez de flashear um pseudo-componente
    inventado. O surrogate é a Fase 4."""
    with pytest.raises(ValueError, match="C20"):
        et.flash_tp(T_K, P_PA, {"C1": 0.6, "C20+": 0.4}, "hidrocarboneto")
    assert any("C20" in x["grandeza"] for x in et.lacunas("hidrocarboneto"))


def test_a_condutividade_da_fase_liquida_vem_avisada():
    e = et.flash_tp(*BIFASICO, Z_GAS, "hidrocarboneto")
    assert any("condutividade da fase líquida" in a for a in e.avisos)
    assert e.liquido.metodos["k"], "o método efetivo tem de acompanhar o valor"


# ------------------------------------------------------------------ 4. erro e convergência
def test_entrada_invalida_e_erro_de_quem_chama():
    with pytest.raises(ValueError, match="não declarado"):
        et.flash_tp(T_K, P_PA, Z_GAS, "inexistente")
    for T in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="temperatura"):
            et.flash_tp(T, P_PA, Z_GAS, "hidrocarboneto")
    for P in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError, match="pressão"):
            et.flash_tp(T_K, P, Z_GAS, "hidrocarboneto")
    with pytest.raises(ValueError, match="vazia"):
        et.flash_tp(T_K, P_PA, {}, "hidrocarboneto")
    with pytest.raises(ValueError, match="fração inválida"):
        et.flash_tp(T_K, P_PA, {"C1": -0.1, "C2": 1.1}, "hidrocarboneto")


def test_composicao_que_nao_soma_um_e_recusada_e_nao_normalizada():
    """Normalizar em silêncio esconderia erro de quem chama."""
    with pytest.raises(ValueError, match="somam"):
        et.flash_tp(T_K, P_PA, {"C1": 0.5, "C2": 0.2}, "hidrocarboneto")


def test_nao_convergir_e_estado_e_nao_excecao(monkeypatch):
    """Contrato do projeto: inviabilidade é estado. O serviço devolve ok=False com a mensagem
    do backend, e quem chama decide."""
    from fpso_siz.pfd import _chedl

    def explode(*a, **k):
        raise ValueError("faixa de composição não suportada")
    monkeypatch.setattr(_chedl, "flash_vle", explode)
    e = et.flash_tp(T_K, P_PA, Z_GAS, "hidrocarboneto")
    assert not e.ok and "não convergiu" in e.mensagem and "faixa de composição" in e.mensagem
    assert e.fases == () and e.fluido == "hidrocarboneto" and math.isnan(e.h)


def test_erro_de_programacao_nao_e_engolido(monkeypatch):
    """Só ValueError e ArithmeticError viram estado. Um TypeError é defeito, e tem de aparecer."""
    from fpso_siz.pfd import _chedl

    def defeito(*a, **k):
        raise TypeError("assinatura errada")
    monkeypatch.setattr(_chedl, "flash_vle", defeito)
    with pytest.raises(TypeError):
        et.flash_tp(T_K, P_PA, Z_GAS, "hidrocarboneto")


def test_fora_da_faixa_de_laliberte_vira_aviso_e_nao_bloqueio():
    e = et.flash_tp(c_para_k(200.0), P_PA, {"NaCl": 0.035}, "salmoura")
    assert e.ok and e.aquosa is not None
    assert any("fora da faixa" in a for a in e.avisos)


# ------------------------------------------------------------------ 5. a interface é livre
def test_a_interface_nao_conhece_biblioteca_nenhuma():
    """`estado_termodinamico.py` fala com o ChEDL só pela porta `_chedl`, como o resto do PFD.
    (O teste de arquitetura geral cobre a porta; aqui fixa-se o módulo do serviço.)"""
    import pathlib
    fonte = pathlib.Path(et.__file__).read_text(encoding="utf-8")
    for proibido in ("import thermo", "import chemicals", "from thermo", "from chemicals"):
        assert proibido not in fonte, proibido


def test_pressao_entra_em_pa_e_temperatura_em_k():
    """As unidades são as declaradas: um estado pedido em (K, Pa) e o mesmo pedido convertido de
    (°C, kPa) têm de coincidir — é o contrato de unidades, não um detalhe."""
    a = et.flash_tp(T_K, P_PA, Z_GAS, "hidrocarboneto")
    b = et.flash_tp(c_para_k(T_K - 273.15), kpa_para_pa(P_PA / 1000.0), Z_GAS, "hidrocarboneto")
    assert mesmo(a.vapor.rho, b.vapor.rho) and mesmo(a.vapor.Z, b.vapor.Z)
