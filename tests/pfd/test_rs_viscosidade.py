"""Fase B (docs/validacao/45): as bases da μ do óleo vivo e a reconstrução da rota anterior.

A comparação inteira é estudo (`tools/comparar_rs_viscosidade.py`); aqui ficam as afirmações de
base que a nota usa: quem consome a μ do óleo, onde o Rs é nulo ou abaixo da faixa (e por isso as
duas rotas coincidem), e que nos casos com gás de lift a rota anterior é a própria rota vigente.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from fpso_siz.termo import servico as termo

FERRAMENTA = Path(__file__).resolve().parents[2] / "tools" / "comparar_rs_viscosidade.py"


@pytest.fixture(scope="module")
def ferramenta():
    sys.path.insert(0, str(FERRAMENTA.parent))
    spec = importlib.util.spec_from_file_location("comparar_rs_viscosidade", FERRAMENTA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_consumidores_da_mu_do_oleo(ferramenta):
    assert {(t, k) for t, k, _, _ in ferramenta.consumidores()} == {
        ("SG-001", "mu_oil"), ("P-001", "mu_tubo"), ("P-001", "mu_casco"), ("P-002", "mu_casco"),
        ("P-003", "mu_casco"), ("TO-001", "mu_oil"), ("TO-002", "mu_oil"), ("B-001", "mu_oil")}


def test_rs_nulo_a_jusante_e_abaixo_da_faixa_no_v001(ferramenta, planta_propostas):
    """A jusante do V-002 o óleo não libera gás no tanque (Rs = 0); no C-10 o Rs do trem fica abaixo
    da faixa de Beggs & Robinson e a μ é a do óleo morto — as duas rotas coincidem ali."""
    rs_min = termo.cfg()["oleo_vivo"]["faixa_rs_scf_stb"][0]
    for r in planta_propostas.contexto.balanco:
        if not r.avaliavel:
            continue
        assert all(ferramenta.rs(r, c) == pytest.approx(0, abs=1e-6) for c in ("C-18", "C-21", "C-22", "C-23"))
        assert 0 < ferramenta.rs(r, "C-10") < rs_min
        assert ferramenta.rs(r, "C-06") > rs_min


def test_rota_anterior_coincide_nos_casos_com_lift(ferramenta, planta_propostas):
    ctx = planta_propostas.contexto
    std = ferramenta.balanco_standing(ctx.dados, ctx.prem)
    for r in ctx.balanco:
        if not r.avaliavel:
            assert std[r.num].streams == r.streams and std[r.num].T == r.T
            assert ferramenta.rs(std[r.num], "C-06") == ferramenta.rs(r, "C-06")
