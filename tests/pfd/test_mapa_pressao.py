"""Mapa de pressão (tools/mapa_pressao.py): estudo de sensibilidade, só orquestração da API.

Prende: pontos inválidos são classificados (não descartados); o ponto de referência reproduz o
estado produtivo; a TVP é só dos 12 casos avaliáveis e o dimensionamento dos 16; o critério de
sensibilidade é o declarado; e a grade não se confunde com limite.
"""
import importlib.util
import math
from pathlib import Path

import pytest

from fpso_siz.balanco import trem

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def mapa():
    spec = importlib.util.spec_from_file_location("mapa_pressao", RAIZ / "tools" / "mapa_pressao.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_p_d2_maior_ou_igual_a_p_d1_e_classificado_sem_calcular(mapa, planta_base):
    li = mapa.ponto(planta_base.dados, 200.0, 250.0)
    assert li["estado"].startswith("inválido") and "TVP_max_kPa" not in li


def test_ponto_de_referencia_reproduz_o_estado_produtivo(mapa, planta_propostas):
    dados, prem = planta_propostas.dados, planta_propostas.prem
    li = mapa.ponto(dados, prem["P_D1"], prem["P_D2"])
    assert li["estado"] == mapa.VALIDO
    assert (li["casos_dimensionamento"], li["casos_termodinamicos"], li["casos_nao_avaliaveis"]) == (16, 12, 4)
    for ident in mapa.cfg()["tags"]:
        r = planta_propostas.tag(ident).resultado
        assert li[f"{ident.replace('-', '')}_d_mm"] == r.x and li[f"{ident.replace('-', '')}_Leff_m"] == r.y
    b = planta_propostas.balanco
    T = prem[trem.cfg()["tvp"]["premissa_T"]]
    tvps = [trem.tvp_kpa(r.trem, T, r.mws_plus) for r in b if r.avaliavel]
    assert li["TVP_max_kPa"] == max(tvps) and li["TVP_min_kPa"] == min(tvps)
    assert li["Q_G_V002_max_Sm3_d"] == max(r.gas["G_D2"] for r in b)   # os 16 casos, não só os 12


def test_criterio_de_sensibilidade_e_o_declarado(mapa):
    s = mapa.cfg()["sensibilidade"]
    assert mapa.classificar(s["insensivel_max"] / 2) == "INSENSÍVEL"
    assert mapa.classificar(s["insensivel_max"]) == "FRACAMENTE SENSÍVEL"
    assert mapa.classificar(s["sensivel_min"]) == "SENSÍVEL"


def test_sensibilidade_mede_amplitude_monotonicidade_e_dominancia(mapa):
    """Grade sintética: y = P_D2 (P_D1 não influi) — domina P_D2, monotônica crescente."""
    chaves = [c for c, _, _ in mapa.CONTINUAS] + [c for c, _ in mapa.DISCRETAS]
    linhas = [dict({k: 1.0 for k in chaves}, P_D1_kPa=a, P_D2_kPa=b, estado=mapa.VALIDO, TVP_max_kPa=b)
              for a in (500.0, 1000.0) for b in (100.0, 150.0, 200.0)]
    ref = next(li for li in linhas if (li["P_D1_kPa"], li["P_D2_kPa"]) == (1000.0, 200.0))
    x = next(s for s in mapa.sensibilidade(linhas, ref) if s["chave"] == "TVP_max_kPa")
    assert (x["dabs"], x["drel"], x["domina"], x["mono_p2"], x["mono_p1"]) == (100.0, 0.5, "P_D2", "crescente", "constante")
    assert x["minimo"][0] == 100.0 and x["maximo"][0] == 200.0 and x["classe"] == "SENSÍVEL"
    assert next(s for s in mapa.sensibilidade(linhas, ref) if s["chave"] == "V001_d_mm")["classe"] == "INSENSÍVEL"


def test_grade_nao_e_limite(mapa):
    """Os limites têm natureza declarada (fonte, processo, diagnóstico, sem fonte); nenhum é
    extremo da grade."""
    c = mapa.cfg()
    naturezas = {x["natureza"] for x in c["limite"]}
    assert naturezas <= {"fonte", "processo", "diagnostico", "sem_fonte"}
    extremos = {min(c["P_D1_kPa"]), max(c["P_D1_kPa"]), min(c["P_D2_kPa"]), max(c["P_D2_kPa"])}
    assert not extremos & {x["valor"] for x in c["limite"]}
    assert all(bool(x["fonte"]) == (x["natureza"] != "sem_fonte") for x in c["limite"])
    assert math.isfinite(mapa.limite("tvp")["valor"])
