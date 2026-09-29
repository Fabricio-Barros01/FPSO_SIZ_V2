"""Trem de separação SG-001 → V-001 → V-002 (balanco/trem.py), parte do EstadoProcesso.

O que estes testes prendem:

1. quem entra no trem: os 12 casos sem gás de lift; os 4 com lift ficam "não avaliáveis
   termodinamicamente para integração completa", sem composição suposta;
2. a composição do caso pela Nota 4 (docs/validacao/38): re-flashada, devolve o
   `produced_gas_sm3d` no FWKO e o `oil_sm3d` de óleo morto; fecha Σz, mol, massa e componente;
   é só a mistura das duas fases de um mesmo flash; e `z_base` (BOT) não é tocado;
3. o trem é uma SEQUÊNCIA: cada estágio recebe o líquido do anterior, nas condições do estado,
   e mudar P_D1 ou P_D2 nas premissas move o estágio;
4. o fechamento é do TREM (global e por componente); `ok` exige os três estágios;
5. o trem é PRODUTIVO nos casos avaliáveis: o gás de cada estágio que o balanço usa é o do flash,
   e a proveniência do caso diz isso; nos não avaliáveis, Standing.
"""
import dataclasses
import math

import pytest

from fpso_siz.balanco import trem
from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_caso
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.termo import proveniencia
from fpso_siz.termo import servico as termo

TOL = 1.0e-12       # folga sobre a precisão de máquina, não critério físico
COM_LIFT = {9, 11, 15, 16}


@pytest.fixture(scope="module")
def avaliaveis(resultados):
    return [r for r in resultados if r.avaliavel]


@pytest.fixture(scope="module")
def trens(avaliaveis):
    return [r.trem for r in avaliaveis]


@pytest.fixture
def sem_memoria():
    """O flash do trem é memorizado; quem troca `termo.flash_tp` precisa limpar a memória."""
    trem._flash.cache_clear()
    yield
    trem._flash.cache_clear()


# ------------------------------------------------------------------ quem é avaliável
def test_doze_casos_avaliaveis_e_os_quatro_com_lift_nao(resultados):
    assert {r.num for r in resultados if not r.avaliavel} == COM_LIFT
    assert len([r for r in resultados if r.avaliavel]) == 12
    for r in resultados:
        if r.num in COM_LIFT:
            assert not r.trem.avaliavel and r.trem.estagios == [] and r.recombinacao is None
            assert trem.cfg()["avaliacao"]["estado_nao_avaliavel"] in r.trem.motivo
            assert r.vapor("C-04") is None and r.gas_padrao == {}


def test_a_lacuna_do_lift_esta_declarada():
    lac = {x["id"]: x for x in trem.lacunas()}
    assert lac["composicao_gas_de_lift"]["situacao"] == "ausente"
    assert "não supor composição" in lac["composicao_gas_de_lift"]["decisao"]


# ------------------------------------------------------------------ recombinação (Nota 4)
def test_a_recombinacao_reproduz_as_vazoes_do_bot(avaliaveis):
    tol = trem.cfg()["recombinacao"]["tolerancia_reproducao"]
    for r in avaliaveis:
        rc = r.recombinacao
        assert (rc.T_ref_C, rc.P_ref_kPa) == (r.caso["T_C"], r.P["C-04"])
        assert rc.reproducao.q_gas_fwko_sm3d == pytest.approx(r.caso["produced_gas_sm3d"], rel=tol)
        assert rc.reproducao.q_oleo_tanque_m3d == pytest.approx(r.caso["oil_sm3d"], rel=tol)
        assert rc.reproducao.ok and rc.ok


def test_a_recombinacao_fecha_composicao_mol_massa_e_componente(avaliaveis):
    tol = trem.cfg()["recombinacao"]["tolerancia_fechamento"]
    for r in avaliaveis:
        rc = r.recombinacao
        assert rc.erro_soma_z <= tol and rc.erro_molar <= tol and rc.erro_massico <= tol
        assert rc.componente[1] <= tol
        assert rc.massa_oleo_tanque_kg_d + rc.massa_gas_padrao_kg_d == pytest.approx(rc.massa_kg_d, rel=1e-14)


def test_a_recombinacao_e_so_a_mistura_das_duas_fases(avaliaveis):
    """Nenhum componente é ajustado: z_caso está na linha de amarração do flash de referência
    (re-flashado na mesma condição, dá as MESMAS fases) e é a média ponderada exata de y e x."""
    for r in avaliaveis[:3]:
        rc = r.recombinacao
        y, x = rc.vapor_ref.composicao, rc.liquido_ref.composicao
        n = rc.n_total_kmol_d
        for k, zk in rc.z_caso.items():
            assert zk == pytest.approx((rc.n_gas_kmol_d * y[k] + rc.n_liquido_kmol_d * x[k]) / n, rel=1e-14, abs=1e-18)
        de_novo = termo.flash_tp(c_para_k(rc.T_ref_C), kpa_para_pa(rc.P_ref_kPa), rc.z_caso, r.mws_plus)
        for k in rc.z_caso:
            assert de_novo.vapor.composicao[k] == pytest.approx(y[k], rel=1e-7, abs=1e-14)
            assert de_novo.liquido.composicao[k] == pytest.approx(x[k], rel=1e-7, abs=1e-14)


def test_a_composicao_do_bot_nunca_e_sobrescrita(avaliaveis, dados):
    for r in avaliaveis:
        base = {k: v for k, v in dados.composicoes[r.fluid].items() if v > 0}
        assert r.composicao == base == r.recombinacao.z_base
        assert r.recombinacao.z_caso != base


# ------------------------------------------------------------------ a sequência
def test_o_trem_percorre_os_tres_estagios_na_ordem(trens):
    ordem = [e["id"] for e in trem.cfg()["estagio"]]
    assert ordem == ["SG-001", "V-001", "V-002"]
    for t in trens:
        assert t.completo and [e.ponto for e in t.estagios] == ordem, t.interrompido


def test_a_alimentacao_de_cada_estagio_e_o_liquido_do_anterior(trens):
    for t in trens:
        assert t.estagios[0].z == t.recombinacao.z_caso
        assert t.estagios[0].n_entrada_kmol_d == t.recombinacao.n_total_kmol_d
        for anterior, seguinte in zip(t.estagios, t.estagios[1:]):
            assert seguinte.z == anterior.x and seguinte.n_entrada_kmol_d == anterior.n_liquido_kmol_d


def test_as_condicoes_sao_as_do_estado(avaliaveis):
    """O trem é refeito até as T convergidas do reciclo não se afastarem das que ele usou mais do
    que a tolerância de acoplamento (trem.toml [acoplamento])."""
    tol = trem.cfg()["acoplamento"]["tolerancia_condicao_C"]
    for r in avaliaveis:
        for e in r.trem.estagios:
            assert e.P_kPa == r.P[e.corrente_gas]
            assert abs(e.T_C - r.T[e.corrente_gas]) <= tol


@pytest.mark.parametrize("chave, estagio", [("P_D1", 1), ("P_D2", 2)])
def test_o_estagio_segue_a_pressao_das_premissas(dados, chave, estagio):
    """P_D1 e P_D2 são premissas: mudá-las move o estágio e a vazão de gás que o balanço usa."""
    base = resolver_caso(dados.caso(2), dados)
    outro = resolver_caso(dados.caso(2), dados, premissas(dados, **{chave: 450.0 if chave == "P_D1" else 150.0}))
    eb, eo = base.trem.estagios[estagio], outro.trem.estagios[estagio]
    assert eo.P_kPa != eb.P_kPa and eo.beta != eb.beta
    gas = ("G_D1", "G_D2")[estagio - 1]
    assert outro.gas[gas] == eo.q_vapor_sm3d != base.gas[gas]


def test_o_liquido_fica_mais_pesado_a_cada_estagio(trens):
    for t in trens:
        mws = [e.liquido.MW for e in t.estagios]
        assert mws == sorted(mws)
        b = [e.beta for e in t.estagios]
        assert b[0] > b[1] > b[2]


def test_a_quantidade_absoluta_e_propagada(trens):
    for t in trens:
        for e in t.estagios:
            assert e.n_vapor_kmol_d == pytest.approx(e.beta * e.n_entrada_kmol_d, rel=1e-15)
            assert e.n_liquido_kmol_d == pytest.approx((1 - e.beta) * e.n_entrada_kmol_d, rel=1e-15)
            assert e.m_vapor_kg_d == pytest.approx(e.n_vapor_kmol_d * e.vapor.MW, rel=1e-15)
            assert e.m_oleo_tanque_kg_d + e.m_gas_dissolvido_kg_d == pytest.approx(e.m_liquido_kg_d, rel=1e-12)


# ------------------------------------------------------------------ fechamento
def test_o_trem_fecha_global_e_por_componente(trens):
    for t in trens:
        f = t.fechamento
        assert f.ok and f.ok_parcial and f.estagios == f.esperados == 3
        assert f.erro_molar_relativo < TOL and f.erro_massico_relativo < TOL and f.erro_componente_max < TOL
        assert t.n_vapor_total + t.n_liquido_final == pytest.approx(t.recombinacao.n_total_kmol_d, rel=1e-12)


def test_cada_flash_do_trem_fecha(trens):
    for t in trens:
        assert all(e.fechamento.ok for e in t.estagios)


def _condicoes(r):
    return [(e.ponto, e.corrente_gas, e.T_C, e.P_kPa) for e in r.trem.estagios]


def test_trem_interrompido_nao_e_trem_completo(avaliaveis, dados, monkeypatch, sem_memoria):
    """Um estágio sem líquido encerra a cascata: o que rodou fecha (ok_parcial), mas o trem não
    é completo e `ok` não passa."""
    original = termo.flash_tp

    def so_vapor(T, P, z, mws_plus):
        v = original(T, P, z, mws_plus).vapor
        unica = dataclasses.replace(v, fracao_molar=1.0, fracao_massica=1.0, composicao=dict(z),
                                    MW=termo.mw_mistura(z, mws_plus))
        return termo.EstadoTermodinamico(T=T, P=P, z=dict(z), fases=(unica,))

    r = avaliaveis[0]
    monkeypatch.setattr(termo, "flash_tp", so_vapor)
    t = trem.resolver(r.recombinacao, _condicoes(r), r.mws_plus, dados.T_std_C, dados.P_std_kPa)
    assert len(t.estagios) == 1 and not t.completo and "sem fase líquida" in t.interrompido
    assert t.fechamento.ok_parcial and not t.fechamento.ok and t.fechamento.esperados == 3
    assert math.isfinite(t.n_liquido_final)


def test_flash_que_nao_converge_interrompe_sem_inventar(avaliaveis, dados, monkeypatch, sem_memoria):
    def falha(T, P, z, mws_plus):
        return termo.EstadoTermodinamico(T=T, P=P, z=dict(z), ok=False, mensagem="não convergiu")

    r = avaliaveis[0]
    monkeypatch.setattr(termo, "flash_tp", falha)
    t = trem.resolver(r.recombinacao, _condicoes(r), r.mws_plus, dados.T_std_C, dados.P_std_kPa)
    assert len(t.estagios) == 1 and t.interrompido.startswith("SG-001")
    assert not t.fechamento.ok and not t.fechamento.ok_parcial and t.fechamento.estagios == 0


def test_referencia_sem_duas_fases_nao_se_recombina(avaliaveis, dados, monkeypatch, sem_memoria):
    def monofasico(T, P, z, mws_plus):
        return termo.EstadoTermodinamico(T=T, P=P, z=dict(z), ok=False, mensagem="sem convergência")

    r = avaliaveis[0]
    monkeypatch.setattr(termo, "flash_tp", monofasico)
    with pytest.raises(ValueError, match="não bifásica"):
        trem.recombinar(r.composicao, r.mws_plus, 1.0, 1.0, r.rho["O"], r.VM, r.caso["T_C"], r.P["C-04"],
                        dados.T_std_C, dados.P_std_kPa)


def test_o_flash_do_trem_e_memorizado(avaliaveis):
    e = avaliaveis[0].trem.estagios[1]
    assert trem.flash(e.T_C, e.P_kPa, e.z, avaliaveis[0].mws_plus) is trem.flash(e.T_C, e.P_kPa, dict(e.z),
                                                                                  avaliaveis[0].mws_plus)


# ------------------------------------------------------------------ produtivo, com proveniência
def test_o_balanco_consome_o_gas_do_trem(avaliaveis):
    for r in avaliaveis:
        est = {e.corrente_gas: e for e in r.trem.estagios}
        for cid, chave in (("C-04", "G_F"), ("C-09", "G_D1"), ("C-17", "G_D2")):
            e = est[cid]
            assert r.gas[chave] == e.q_vapor_sm3d == r.q(cid, "G")
            assert r.vapor(cid) is e.vapor
        assert r.gas["dRsF"] is None and r.gas["dRsD1"] is None
        assert r.gas["G_in"] == r.recombinacao.q_gas_padrao_sm3d


def test_o_liquido_leva_o_gas_que_ainda_libera(avaliaveis):
    k_dia = 1 / 86400
    for r in avaliaveis:
        f = r.trem.estagios[0]
        assert r.streams["C-06"]["G"] == pytest.approx(f.m_gas_dissolvido_kg_d * k_dia, rel=1e-9)
        assert r.q("C-06", "G") == pytest.approx(f.q_gas_dissolvido_sm3d, rel=1e-9)


def test_a_proveniencia_do_caso_diz_de_onde_veio_o_gas(resultados):
    for r in resultados:
        if r.avaliavel:
            assert r.proveniencia == proveniencia.consumidas("balanco", avaliavel=True)
            assert "fracao_vapor_estagio" in r.proveniencia and "gas_liberado_por_estagio" not in r.proveniencia
        else:
            assert r.proveniencia == proveniencia.consumidas("balanco", avaliavel=False)
            assert r.proveniencia["gas_liberado_por_estagio"]["origem"] == ["Standing"]
            assert "fracao_vapor_estagio" not in r.proveniencia


# ------------------------------------------------------------------ TVP
def test_tvp_do_liquido_final_e_lida_pelo_estado(resultados, dados):
    """O EstadoProcesso lê a TVP na temperatura da premissa declarada, pela mesma função do
    trem; nos casos não avaliáveis ela não existe (NaN), e a restrição não é verificada neles."""
    T = premissas(dados)[trem.cfg()["tvp"]["premissa_T"]]
    for r in resultados[:2] + [x for x in resultados if not x.avaliavel][:1]:
        v = trem.tvp_kpa(r.trem, T, r.mws_plus)
        assert r.T_tvp_C == T
        assert math.isfinite(v) and v > 0 and r.tvp_kPa == v if r.avaliavel else math.isnan(r.tvp_kPa)
