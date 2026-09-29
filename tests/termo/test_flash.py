"""Equilíbrio do fluido de poço: `termo.servico.flash_tp`, `mw_mistura` e `conferir`.

O que estes testes prendem:

1. o contrato do estado: fases vapor/líquido com fração molar e mássica, composição, Z, MW, ρ;
2. o fechamento de um flash, com a coerência molar × mássica DENTRO de `ok`;
3. não convergir é estado; entrada inválida é erro de quem chama; defeito não é engolido;
4. unidades K e Pa; o serviço não conhece a biblioteca (só a porta `termo/backend.py`).
"""
import dataclasses
import json
import math
from pathlib import Path

import pytest

from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.termo import backend
from fpso_siz.termo import servico as termo

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"
T_K, P_PA = 338.15, 2.5e6


@pytest.fixture(scope="module")
def bot():
    return json.loads(CASOS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def mws(bot):
    return {k: v["mw"] for k, v in bot["c20_pseudo"].items()}


@pytest.fixture(scope="module")
def z(bot):
    return {k: v for k, v in bot["fluid_compositions"]["Early Life"].items() if v > 0}


@pytest.fixture(scope="module")
def bifasico(z, mws):
    return termo.flash_tp(T_K, P_PA, z, mws)


# ------------------------------------------------------------------ o contrato
def test_bifasico_devolve_x_y_e_as_duas_fracoes(bifasico, z):
    e = bifasico
    assert e.ok and not e.monofasico and {f.nome for f in e.fases} == {"vapor", "liquido"}
    v, li = e.vapor, e.liquido
    assert v.fracao_molar + li.fracao_molar == pytest.approx(1.0, abs=1e-12)
    assert v.fracao_massica + li.fracao_massica == pytest.approx(1.0, abs=1e-12)
    assert set(v.composicao) == set(li.composicao) == set(z)
    assert v.MW < li.MW and v.rho < li.rho and 0 < v.Z <= 1.1
    # o vapor leva os leves e o líquido os pesados
    assert v.composicao["C1"] > li.composicao["C1"] and li.composicao["C20+"] > v.composicao["C20+"]


def test_fechamento_do_flash_inclui_a_coerencia_das_bases(bifasico):
    f = termo.conferir(bifasico)
    assert f.ok and not f.monofasico
    assert max(f.erro_componente_max, f.erro_soma_y, f.erro_soma_x, f.erro_balanco_molar,
               f.erro_balanco_massico, f.coerencia_molar_massica) < 1e-12


def test_fechamento_reprova_quando_a_coerencia_das_bases_falha(bifasico):
    """A coerência molar × mássica é invariante: se falha, `ok` tem de cair."""
    v = bifasico.vapor
    estragado = dataclasses.replace(bifasico, fases=(dataclasses.replace(v, fracao_massica=v.fracao_massica * 1.01),
                                                     bifasico.liquido))
    f = termo.conferir(estragado)
    assert f.coerencia_molar_massica > 1e-4 and not f.ok


def test_monofasico_devolve_uma_fase_coerente(mws):
    z = {"C1": 0.9, "C2": 0.1}
    e = termo.flash_tp(400.0, 1.0e5, z, mws)
    assert e.ok and e.monofasico and e.vapor is not None and e.liquido is None
    f = termo.conferir(e)
    assert f.ok and f.monofasico and f.erro_componente_max < 1e-12


def test_mw_da_mistura_e_a_soma_pelos_mw_adotados(z, mws):
    reais, pseudos = termo._componentes(z, mws)
    mws_todos = backend.mws_pseudo(reais, pseudos, termo.cfg()["gas"]["kij"])
    assert termo.mw_mistura(z, mws) == sum(z[k] * m for k, m in zip(z, mws_todos))


# ------------------------------------------------------------------ erros e estados
def test_entrada_invalida_e_erro_de_quem_chama(z, mws):
    for T in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="temperatura"):
            termo.flash_tp(T, P_PA, z, mws)
    for P in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError, match="pressão"):
            termo.flash_tp(T_K, P, z, mws)
    with pytest.raises(ValueError, match="vazia"):
        termo.flash_tp(T_K, P_PA, {}, mws)
    with pytest.raises(ValueError, match="fração inválida"):
        termo.flash_tp(T_K, P_PA, {"C1": -0.1, "C2": 1.1}, mws)
    with pytest.raises(ValueError, match="somam"):
        termo.mw_mistura({"C1": 0.5, "C2": 0.2}, mws)


def test_composicao_que_nao_soma_um_e_recusada_e_nao_normalizada(mws):
    """Normalizar em silêncio esconderia erro de quem chama."""
    with pytest.raises(ValueError, match="somam"):
        termo.flash_tp(T_K, P_PA, {"C1": 0.5, "C2": 0.2}, mws)


def test_nao_convergir_e_estado_e_nao_excecao(monkeypatch, z, mws):
    def explode(*a, **k):
        raise ValueError("faixa de composição não suportada")
    monkeypatch.setattr(backend, "flash_pseudo", explode)
    e = termo.flash_tp(T_K, P_PA, z, mws)
    assert not e.ok and "não convergiu" in e.mensagem and "faixa de composição" in e.mensagem and e.fases == ()


def test_nao_convergencia_do_solver_do_backend_e_estado(monkeypatch, z, mws):
    """O solver do ChEDL avisa que não convergiu com exceções próprias (fluids.numerics), que
    não descendem de ArithmeticError nem de ValueError. A porta as traduz: o serviço devolve
    estado com ok=False, e a otimização não cai por um ponto sem equilíbrio."""
    from fluids.numerics import OscillationError

    class Oscila:
        def flash(self, **k):
            raise OscillationError("Converged to cycle in errors, no progress being made")
    monkeypatch.setattr(backend, "_pacote_pseudo", lambda *a: Oscila())
    with pytest.raises(ArithmeticError, match="OscillationError"):
        backend.flash_pseudo((), (), [1.0], T_K, P_PA, "PR")
    e = termo.flash_tp(T_K, P_PA, z, mws)
    assert not e.ok and "OscillationError" in e.mensagem


def test_ponto_de_bolha_sem_equilibrio_em_algum_passo_e_nan(monkeypatch, bifasico, mws):
    """Um flash que não converge no meio da bisseção não é "não ferve": sem equilíbrio não há
    ponto de bolha, e a TVP fica NaN (não avaliável) em vez de deslocada em silêncio."""
    real = termo.flash_tp
    chamadas = []

    def falha_no_terceiro(T, P, zz, m):
        chamadas.append(P)
        if len(chamadas) == 3:
            return dataclasses.replace(real(T, P, zz, m), fases=(), ok=False)
        return real(T, P, zz, m)
    x = bifasico.liquido.composicao          # o líquido do FWKO: ferve abaixo de 2,5 MPa
    assert math.isfinite(termo.pressao_bolha(T_K, x, mws))
    monkeypatch.setattr(termo, "flash_tp", falha_no_terceiro)
    assert math.isnan(termo.pressao_bolha(T_K, x, mws)) and len(chamadas) == 3


def test_erro_de_programacao_nao_e_engolido(monkeypatch, z, mws):
    """Só ValueError e ArithmeticError viram estado. Um TypeError é defeito, e tem de aparecer."""
    def defeito(*a, **k):
        raise TypeError("assinatura errada")
    monkeypatch.setattr(backend, "flash_pseudo", defeito)
    with pytest.raises(TypeError):
        termo.flash_tp(T_K, P_PA, z, mws)


# ------------------------------------------------------------------ unidades e porta
def test_pressao_entra_em_pa_e_temperatura_em_k(z, mws):
    a = termo.flash_tp(T_K, P_PA, z, mws)
    b = termo.flash_tp(c_para_k(T_K - 273.15), kpa_para_pa(P_PA / 1000.0), z, mws)
    assert a.vapor.rho == b.vapor.rho and a.vapor.Z == b.vapor.Z


def test_o_servico_nao_conhece_biblioteca_nenhuma():
    fonte = Path(termo.__file__).read_text(encoding="utf-8")
    for proibido in ("import thermo", "import chemicals", "from thermo", "from chemicals"):
        assert proibido not in fonte, proibido
    assert math.isfinite(termo.cfg_flash()["flash"]["tolerancia_composicao"])
