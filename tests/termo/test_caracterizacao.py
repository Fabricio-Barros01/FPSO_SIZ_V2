"""Caracterização dos pseudo-componentes do fluido de poço (termo/caracterizacao.py).

A mudança é de REPRESENTAÇÃO FÍSICA: cortes SCN C6–C19 e frações plus C20+/C20++ deixam de
depender de um nome de banco de dados (o backend resolvia "C7" como n-heptano) e passam a ser
pseudo-componentes caracterizados por Riazi & Al-Sahhaf (1996).

Os testes cobrem, nesta ordem: a transcrição das correlações contra as conferências internas do
próprio artigo; os invariantes do flash sobre a caracterização; e o que ela NÃO entrega.
"""
import json
from pathlib import Path

import pytest

from fpso_siz.termo import caracterizacao as ca
from fpso_siz.termo import proveniencia
from fpso_siz.termo import servico as termo

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"


@pytest.fixture(scope="module")
def bot():
    return json.loads(CASOS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def mws(bot):
    return {k: v["mw"] for k, v in bot["c20_pseudo"].items()}


@pytest.fixture(scope="module")
def z(bot):
    return {k: v for k, v in bot["fluid_compositions"]["Early Life"].items() if v > 0}


# ------------------------------------------------------------------ a fonte
def test_as_correlacoes_reproduzem_as_conferencias_internas_do_artigo():
    """O artigo (p. 220) afirma dois valores para M = 1382 (Nc = 99): Pc = 1,013 bar e
    Tbr = 0,996. Se a transcrição dos coeficientes estiver errada, isto reprova."""
    c = ca.cfg()["correlacao"]
    M = 1382.0
    pc_bar = ca._theta(c["Pc"], M)
    tbr = ca._theta(c["Tbr"], M)
    assert pc_bar == pytest.approx(1.013, abs=0.01), "Pc da eq. 2 fora da conferência do artigo"
    assert tbr == pytest.approx(0.996, abs=0.001), "Tbr da eq. 2 fora da conferência do artigo"


def test_a_serie_scn_e_monotonica_e_fisicamente_ordenada():
    """Num homólogo, MW, Tb, SG e ω crescem com o número de carbono, e Pc e Tbr caem. Um erro
    de sinal ou de coeficiente quebra a monotonicidade antes de quebrar qualquer outra coisa."""
    ps = [ca.caracterizar(f"C{n}") for n in range(6, 20)]
    for campo, crescente in (("MW", True), ("Tb", True), ("SG", True), ("Tc", True),
                             ("omega", True), ("Pc", False)):
        vs = [getattr(p, campo) for p in ps]
        ordenado = all(b > a for a, b in zip(vs, vs[1:])) if crescente else all(b < a for a, b in zip(vs, vs[1:]))
        assert ordenado, f"{campo} não é monotônico na série SCN: {vs}"


def test_o_scn_nao_e_o_n_alcano_de_mesmo_carbono():
    """O ponto da fase: o corte SCN tem naftênicos e aromáticos, então NÃO coincide com a
    parafina normal de mesmo Nc. Se um dia coincidir, a caracterização foi desligada."""
    import chemicals
    p = ca.caracterizar("C7")
    cas = chemicals.CAS_from_any("C7H16")
    assert p.Tc != chemicals.Tc(cas) and p.omega != chemicals.omega(cas)
    assert p.Tc > chemicals.Tc(cas), "o corte é mais pesado que a parafina: Tc maior"
    assert p.omega < chemicals.omega(cas)


def test_a_fracao_plus_usa_o_MW_do_BOT_exatamente(mws):
    """O MW das frações plus é DADO, não correlação: tem de passar intacto."""
    for nome, mw in mws.items():
        p = ca.caracterizar(nome, mw)
        assert p.MW == mw, "o MW do BOT não pode ser recalculado"
        assert p.origem["MW"].startswith("DADO")
        assert p.tipo == ca.PLUS


def test_a_densidade_da_correlacao_bate_com_a_do_BOT(bot, mws):
    """A prova de que a caracterização representa o corte real: a SG de Riazi, aplicada ao MW
    do BOT, reproduz a densidade que o BOT declara para o mesmo pseudo-componente."""
    for nome, mw in mws.items():
        p = ca.caracterizar(nome, mw)
        rho_bot = bot["c20_pseudo"][nome]["rho_kg_m3"]
        rho = p.SG * 999.0
        assert abs(rho - rho_bot) / rho_bot < 0.05, f"{nome}: {rho:.1f} vs BOT {rho_bot}"


# ------------------------------------------------------------------ invariantes
def test_classificacao_cobre_a_composicao(z, mws):
    """Todo componente é real, corte SCN ou fração plus — nenhum fica sem representação."""
    tipos = {k: ca.classificar(k, mws) for k in z}
    assert set(tipos.values()) == {ca.REAL, ca.SCN, ca.PLUS}
    assert {k for k, t in tipos.items() if t == ca.PLUS} == {"C20+"}


def test_o_flash_nao_altera_a_composicao_global(z, mws):
    """Não há redistribuição: o estado carrega a composição original, componente a componente."""
    e = termo.flash_tp(338.15, 2.5e6, z, mws)
    assert e.ok and e.z == z


def test_determinismo(z, mws):
    p1, p2 = ca.caracterizar("C12"), ca.caracterizar("C12")
    assert (p1.Tc, p1.Pc, p1.omega, p1.MW) == (p2.Tc, p2.Pc, p2.omega, p2.MW)
    a, b = termo.flash_tp(338.15, 2.5e6, z, mws), termo.flash_tp(338.15, 2.5e6, z, mws)
    assert a == b


def test_independencia_da_ordem_dos_componentes(z, mws):
    """Reordenar a composição não pode mudar o resultado."""
    invertida = dict(reversed(list(z.items())))
    e1 = termo.flash_tp(338.15, 2.5e6, z, mws)
    e2 = termo.flash_tp(338.15, 2.5e6, invertida, mws)
    assert e1.vapor.fracao_molar == pytest.approx(e2.vapor.fracao_molar, rel=1e-9)
    assert e1.vapor.Z == pytest.approx(e2.vapor.Z, rel=1e-9)
    assert termo.mw_mistura(z, mws) == pytest.approx(termo.mw_mistura(invertida, mws), rel=1e-15)


def test_mw_da_mistura_fecha_contra_as_fases_do_flash(z, mws):
    """Σ zᵢ·MWᵢ com os MW adotados é o mesmo MW que sai das fases: β·MW_V + (1−β)·MW_L."""
    e = termo.flash_tp(338.15, 2.5e6, z, mws)
    assert termo.mw_mistura(z, mws) == pytest.approx(sum(f.fracao_molar * f.MW for f in e.fases), rel=1e-14)


def test_sem_fracao_pesada_continua_funcionando(mws):
    """Composição só de componentes reais: nenhum pseudo-componente, e o flash segue."""
    z = {"C1": 0.80, "C2": 0.12, "C3": 0.08}
    assert all(ca.classificar(k, mws) == ca.REAL for k in z)
    e = termo.flash_tp(300.0, 5.0e6, z, mws)
    assert e.ok and e.fases


@pytest.mark.parametrize("eps", [1e-12, 1e-6, 1e-3])
def test_limite_de_fracao_infima_do_pseudo(eps, mws):
    """Um traço de pseudo-componente não desestabiliza o flash."""
    e = termo.flash_tp(300.0, 5.0e6, {"C1": 1.0 - eps, "C20+": eps}, mws)
    assert e.ok and 0 < e.vapor.fracao_molar <= 1.0


def test_pseudo_componente_PURO_nao_converge_e_isso_volta_como_estado(mws):
    """Um único componente degenera o flash VL do backend (divisão por zero). O serviço não
    quebra — devolve estado com a mensagem. Limitação registrada: o caminho exige mistura."""
    for T, P in ((300.0, 1.0e5), (600.0, 1.0e5), (450.0, 2.5e6)):
        e = termo.flash_tp(T, P, {"C20+": 1.0}, mws)
        assert not e.ok and e.fases == ()
        assert "não convergiu" in e.mensagem


def test_cada_propriedade_do_pseudo_tem_origem(z, mws):
    for nome in z:
        if ca.classificar(nome, mws) == ca.REAL:
            continue
        p = ca.caracterizar(nome, mws.get(nome))
        assert set(p.origem) == {"MW", "Tb", "SG", "Tc", "Pc", "omega"}
        assert all(v.strip() for v in p.origem.values()) and p.nome == nome


# ------------------------------------------------------------------ o que NÃO é entregue
def test_h_cp_mu_e_k_do_fluido_de_poco_nao_existem(z, mws):
    """Sem Cp_ig dos pseudo-componentes não há entalpia nem cp, e o pacote não tem transporte:
    a fase nem tem esses campos, e o contrato de proveniência os declara ausentes."""
    e = termo.flash_tp(338.15, 2.5e6, z, mws)
    for f in e.fases:
        assert not any(hasattr(f, g) for g in ("h", "cp", "mu", "k"))
    for ident in ("entalpia_fluido_de_poco", "transporte_fluido_de_poco"):
        d = proveniencia.de(ident)
        assert d["validade"] == proveniencia.AUSENTE and d["consumidores"] == [] and d["nota"].strip()


def test_fracao_plus_sem_MW_e_erro_de_quem_chama(z):
    with pytest.raises(ValueError, match="MW do BOT"):
        termo.flash_tp(338.15, 2.5e6, z, {})
