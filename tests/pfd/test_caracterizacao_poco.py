"""Fase 4 — caracterização dos pseudo-componentes do fluido de poço.

A mudança é de REPRESENTAÇÃO FÍSICA: cortes SCN C6–C19 e frações plus C20+/C20++ deixam de
depender de um nome de banco de dados (o backend resolvia "C7" como n-heptano) e passam a ser
pseudo-componentes caracterizados por Riazi & Al-Sahhaf (1996).

Os testes cobrem, nesta ordem: a transcrição das correlações contra as conferências internas do
próprio artigo; os invariantes da transformação; e o que a caracterização NÃO entrega.
"""
import json
import math
from pathlib import Path

import pytest

from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import caracterizacao as ca
from fpso_siz.pfd import estado_termodinamico as et

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


# ------------------------------------------------------------------ invariantes da transformação
def test_a_composicao_nao_e_transformada(z, mws):
    """O invariante central: NÃO há redistribuição. Cada componente mantém a sua fração."""
    enviada, mapa = ca.transformar(z, mws)
    assert enviada == z, "a composição enviada ao backend tem de ser a original"
    assert set(mapa) == set(z)
    for nome, info in mapa.items():
        assert info["fracao"] == z[nome], f"{nome}: fração alterada"


def test_fechamento_e_ausencia_de_negativas(z, mws):
    enviada, _ = ca.transformar(z, mws)
    assert sum(enviada.values()) == pytest.approx(1.0, abs=1e-12)
    assert all(v >= 0 for v in enviada.values())


def test_a_quantidade_atribuida_a_cada_pseudo_e_conservada(z, mws):
    """O que vai para pseudo-componente é exatamente o que estava nesses componentes."""
    _, mapa = ca.transformar(z, mws)
    for tipo in (ca.SCN, ca.PLUS):
        original = sum(v for k, v in z.items() if ca.classificar(k, mws) == tipo)
        transferida = sum(i["fracao"] for i in mapa.values() if i["tipo"] == tipo)
        assert transferida == pytest.approx(original, abs=1e-15), tipo


def test_determinismo(z, mws):
    a = ca.transformar(z, mws)
    b = ca.transformar(z, mws)
    assert a[0] == b[0]
    assert {k: (v["tipo"], v["fracao"]) for k, v in a[1].items()} == \
           {k: (v["tipo"], v["fracao"]) for k, v in b[1].items()}
    p1, p2 = ca.caracterizar("C12"), ca.caracterizar("C12")
    assert (p1.Tc, p1.Pc, p1.omega, p1.MW) == (p2.Tc, p2.Pc, p2.omega, p2.MW)


def test_independencia_da_ordem_dos_componentes(z, mws):
    """Reordenar a composição não pode mudar caracterização nem resultado."""
    invertida = dict(reversed(list(z.items())))
    a, _ = ca.transformar(z, mws)
    b, _ = ca.transformar(invertida, mws)
    assert a == b or (set(a) == set(b) and all(a[k] == b[k] for k in a))
    e1 = et.flash_poco(338.15, 2.5e6, z, mws)
    e2 = et.flash_poco(338.15, 2.5e6, invertida, mws)
    assert e1.fracao_vapor == pytest.approx(e2.fracao_vapor, rel=1e-9)
    assert e1.vapor.Z == pytest.approx(e2.vapor.Z, rel=1e-9)


def test_sem_fracao_pesada_continua_funcionando(mws):
    """Composição só de componentes reais: nenhum pseudo-componente, e o flash segue."""
    z = {"C1": 0.80, "C2": 0.12, "C3": 0.08}
    enviada, mapa = ca.transformar(z, mws)
    assert enviada == z and all(i["tipo"] == ca.REAL for i in mapa.values())
    e = et.flash_poco(300.0, 5.0e6, z, mws)
    assert e.ok and e.fases


@pytest.mark.parametrize("eps", [1e-12, 1e-6, 1e-3])
def test_limite_de_fracao_infima_do_pseudo(eps, mws):
    """Um traço de pseudo-componente não desestabiliza o flash, e o efeito é monotônico."""
    e = et.flash_poco(300.0, 5.0e6, {"C1": 1.0 - eps, "C20+": eps}, mws)
    assert e.ok and 0 < e.fracao_vapor <= 1.0


def test_pseudo_componente_PURO_nao_converge_e_isso_volta_como_estado(mws):
    """Limite oposto: um único componente degenera o flash VL do backend (divisão por zero).
    O serviço NÃO pode quebrar — devolve estado com a mensagem, que é o contrato. Fica
    registrado como limitação: o caminho exige mistura."""
    for T, P in ((300.0, 1.0e5), (600.0, 1.0e5), (450.0, 2.5e6)):
        e = et.flash_poco(T, P, {"C20+": 1.0}, mws)
        assert not e.ok and e.fases == ()
        assert "não convergiu" in e.mensagem


def test_rastreabilidade_original_para_o_que_vai_ao_backend(z, mws):
    """Para cada componente: o tipo, a fração e — se pseudo — de onde saiu cada propriedade."""
    _, mapa = ca.transformar(z, mws)
    assert any(i["tipo"] == ca.SCN for i in mapa.values())
    assert any(i["tipo"] == ca.PLUS for i in mapa.values())
    for nome, i in mapa.items():
        if i["pseudo"] is None:
            continue
        p = i["pseudo"]
        assert set(p.origem) == {"MW", "Tb", "SG", "Tc", "Pc", "omega"}
        assert all(v.strip() for v in p.origem.values())
        assert p.nome == nome


# ------------------------------------------------------------------ o que NÃO é entregue
def test_h_e_cp_do_fluido_de_poco_sao_bloqueados(z, mws):
    """Sem Cp_ig dos pseudo-componentes não há entalpia nem cp — e isso é por construção, não
    um zero nem um valor suposto."""
    e = et.flash_poco(338.15, 2.5e6, z, mws)
    assert e.ok
    for f in e.fases:
        assert math.isnan(f.h) and math.isnan(f.cp)
        assert math.isnan(f.mu) and math.isnan(f.k)
    assert math.isnan(e.h)
    assert any("Cp_ig" in a for a in e.avisos)
    assert any("Cp_ig" in b["grandeza"] for b in ca.bloqueios())


def test_os_bloqueios_estao_declarados_com_motivo():
    for b in ca.bloqueios():
        assert b["grandeza"].strip() and b["motivo"].strip() and b["situacao"].strip()


def test_fracao_plus_sem_MW_e_erro_de_quem_chama(z):
    with pytest.raises(ValueError, match="MW do BOT"):
        et.flash_poco(338.15, 2.5e6, z, {})
