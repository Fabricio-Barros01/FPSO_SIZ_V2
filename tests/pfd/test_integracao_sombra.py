"""Fase 5 — integração em modo sombra (`pfd/integracao.py`).

O flash roda em paralelo; o processo continua no caminho legado. O que estes testes prendem:

1. **o guarda funciona** — propriedade não liberada não pode ser consumida, e a recusa é erro,
   não aviso. É o que impede substituição silenciosa;
2. **o mapa é completo e honesto** — toda propriedade citada tem origem, consumidores e motivo;
3. **os fechamentos fecham** — z = β·y + (1−β)·x, somas, balanços molar e mássico;
4. **nada da planta mudou** — o modo sombra não toca em resultado nenhum.
"""
import json
import math
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import integracao as ig

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"


@pytest.fixture(scope="module")
def ambiente():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    mws = {k: v["mw"] for k, v in json.loads(CASOS.read_text(encoding="utf-8"))["c20_pseudo"].items()}
    return dados, prem, mws, resolver_todos(dados, prem)


# ------------------------------------------------------------------ 1. o guarda
def test_propriedade_bloqueada_nao_pode_ser_consumida():
    """O ponto central da ativação seletiva: tentar consumir levanta erro com o motivo."""
    for prop in ("rho_liquido", "h", "cp", "mu", "k"):
        assert ig.status(prop) == ig.BLOQUEADA
        with pytest.raises(ValueError, match="BLOQUEADA"):
            ig.exigir_liberada(prop)


def test_propriedade_em_sombra_tambem_nao_pode_ser_consumida():
    for prop in ("beta", "y", "x"):
        assert ig.status(prop) == ig.SOMBRA
        with pytest.raises(ValueError, match="SOMBRA"):
            ig.exigir_liberada(prop)


def test_propriedade_liberada_passa():
    for prop in ("Z", "MW", "rho_vapor"):
        assert ig.exigir_liberada(prop) is True


def test_a_densidade_de_liquido_esta_bloqueada_com_o_motivo_medido():
    """Não basta estar bloqueada: o motivo tem de citar a medição que a bloqueou."""
    d = ig.mapa()["rho_liquido"]
    assert "0,541" in d["motivo"] or "0.541" in d["motivo"]
    assert any("dimensionamento" in c or "holdup" in c or "velocidade" in c for c in d["consumidores"])


def test_propriedade_desconhecida_e_erro():
    with pytest.raises(ValueError, match="não mapeada"):
        ig.status("inexistente")


# ------------------------------------------------------------------ 2. o mapa
def test_o_mapa_cobre_todas_as_propriedades_pedidas():
    """beta, x, y, Z, MW, rho, h, cp, mu, k — nenhuma pode faltar."""
    m = ig.mapa()
    for prop in ("beta", "x", "y", "Z", "MW", "rho_vapor", "rho_liquido", "h", "cp", "mu", "k"):
        assert prop in m, prop


def test_cada_entrada_do_mapa_esta_completa():
    for i, d in ig.mapa().items():
        assert d["origem_atual"].strip() and d["origem_proposta"].strip(), i
        assert d["consumidores"] and all(c.strip() for c in d["consumidores"]), i
        assert d["status"] in (ig.LIBERADA, ig.SOMBRA, ig.BLOQUEADA), i
        if d["status"] != ig.LIBERADA:
            assert d["motivo"].strip(), i


def test_a_proveniencia_nao_finge_modelo_unico():
    """O estado é híbrido; `proveniencia` tem de mostrar origens diferentes convivendo."""
    p = ig.proveniencia()
    assert set(p) == set(ig.mapa())
    origens = set(p.values())
    assert len(origens) > 1, "um mapa com origem única esconderia o hibridismo"
    # o que está bloqueado continua apontando para a origem LEGADA
    assert p["rho_liquido"] == ig.mapa()["rho_liquido"]["origem_atual"]
    assert p["Z"] == ig.mapa()["Z"]["origem_proposta"]


def test_os_pontos_de_equilibrio_estao_declarados():
    ids = [p["id"] for p in ig.pontos()]
    assert ids == ["SG-001", "V-001", "V-002"]
    for p in ig.pontos():
        assert p["corrente_gas"].startswith("C-") and p["pressao"].startswith("P_")
        assert p["legado"].strip()


# ------------------------------------------------------------------ 3. fechamentos
def test_o_flash_fecha_em_todos_os_casos(ambiente):
    """z_i = β·y_i + (1−β)·x_i, somas e balanços, nos 16 casos × 3 pontos."""
    dados, prem, mws, res = ambiente
    sombras = ig.rodar(res, dados, prem, mws_plus=mws)
    assert len(sombras) == len(res) * len(ig.pontos())
    convergidos = [s for s in sombras if s.estado and s.estado.ok]
    assert len(convergidos) == len(sombras), "todos os pontos têm de convergir"
    for s in convergidos:
        f = s.fechamento
        assert f is not None and f.ok, f"{s.caso}/{s.ponto}: fechamento reprovado"
        assert f.erro_componente_max < 1e-12
        assert f.erro_balanco_molar < 1e-12 and f.erro_balanco_massico < 1e-12


def test_o_fechamento_registra_numero_e_nao_so_um_booleano(ambiente):
    dados, prem, mws, res = ambiente
    s = ig.rodar(res[:1], dados, prem, mws_plus=mws)[0]
    f = s.fechamento
    for campo in ("erro_componente_max", "erro_soma_z", "erro_balanco_molar",
                  "erro_balanco_massico", "coerencia_molar_massica"):
        assert isinstance(getattr(f, campo), float)
    assert f.componente_pior in s.estado.z


def test_monofasico_e_tratado(ambiente):
    """Fase que desaparece: a composição da única fase é a global e a fração é 1."""
    from fpso_siz.core.unidades import c_para_k, kpa_para_pa
    from fpso_siz.pfd import estado_termodinamico as et
    dados, prem, mws, res = ambiente
    z = {"C1": 0.95, "C2": 0.05}
    e = et.flash_poco(c_para_k(60.0), kpa_para_pa(200.0), z, mws)
    assert e.ok and e.monofasico
    f = ig.conferir(e)
    assert f.monofasico and f.ok and f.erro_componente_max < 1e-12


# ------------------------------------------------------------------ 4. a planta não mudou
def test_o_modo_sombra_nao_altera_o_balanco(ambiente):
    dados, prem, mws, res = ambiente
    antes = [(r.num, dict(r.streams["C-04"]), dict(r.duties)) for r in res]
    ig.rodar(res, dados, prem, mws_plus=mws)
    depois = [(r.num, dict(r.streams["C-04"]), dict(r.duties)) for r in res]
    assert antes == depois


def test_a_fase_declara_que_esta_em_sombra():
    assert ig.cfg()["fase"]["modo"] == "sombra"
    assert ig.cfg()["fase"]["nota"].strip()
