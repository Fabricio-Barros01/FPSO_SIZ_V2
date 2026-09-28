"""F10c — serviço por TAG: a planta e o TAG isolado passam pela mesma orquestração; o
balanço é resolvido uma vez por contexto; o manual não consulta balanço nem ChEDL; cache
por estado."""
import math

from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.cli import main
from fpso_siz.core.configuracao import exemplos
from fpso_siz.output import pfd
from fpso_siz.pfd import ajustes as mod_ajustes
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import manual, planta
from fpso_siz.termo import servico as termo
from fpso_siz.pfd.tags import tag, tags

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


CASOS = FIXTURES / "python_ref" / "design_cases_bot.json"


@pytest.fixture
def ctx():
    return servico.Contexto(carregar_casos(CASOS))


def _espiar(monkeypatch, modulo, nome):
    chamadas = []
    original = getattr(modulo, nome)

    def espia(*a, **k):
        chamadas.append(a)
        return original(*a, **k)
    monkeypatch.setattr(modulo, nome, espia)
    return chamadas


def test_planta_e_tag_isolado_delegam_ao_mesmo_servico(monkeypatch, tmp_path):
    executar = _espiar(monkeypatch, servico, "executar")
    balanco = _espiar(monkeypatch, servico, "resolver_todos")
    motor = _espiar(monkeypatch, servico, "size_envelope")
    p = planta.dimensionar(carregar_casos(CASOS))
    assert [a[1].id for a in executar] == [t.tag for t in tags()]
    assert len(balanco) == 1  # um balanço para os 11 TAGs
    assert len(motor) == sum(t.resultado is not None for t in p.tags) == 3
    executar.clear(), balanco.clear(), motor.clear()
    assert main(["dimensionar", "--sem-propostas", "--tag", "V-001", "--casos", str(CASOS), "--auto-balanco", "--saida",
                 str(tmp_path)]) == 0
    assert [a[1].id for a in executar] == ["V-001"] and len(balanco) == 1 and len(motor) == 1
    # o artefato do TAG isolado é o mesmo da planta, byte a byte
    pfd.gravar(p, tmp_path / "planta")
    for nome in ("V-001.json", "V-001_varredura.csv"):
        assert (tmp_path / nome).read_bytes() == (tmp_path / "planta" / nome).read_bytes()


def test_cache_por_estado_e_por_contexto(ctx):
    e = servico.estado_inicial("V-001")
    a = servico.executar(ctx, e)
    assert servico.executar(ctx, e) is a
    e.editar("tr_liquid", 6.0)
    b = servico.executar(ctx, e)
    assert b is not a and b.entradas.casos[0].valores["tr_liquid"].valor == 6
    outro = servico.Contexto(ctx.dados, alteracoes={"P_D1": 800.0})
    c = servico.executar(outro, e)
    assert c is not b and c.entradas.casos[0].valores["pressure"].valor == 800
    assert outro.alteracoes == {"P_D1": 800.0} and outro.identidade()["premissas"] == {"P_D1": 800.0}


def test_manual_nao_consulta_balanco_nem_chedl(monkeypatch, ctx):
    for nome in ("gas", "oleo", "salmoura_fracao", "agua_saturada", "emulsao"):
        monkeypatch.setattr(termo, nome, lambda *a, **k: pytest.fail("o manual consultou o ChEDL"))
    e = servico.estado_inicial("P-002", mod_ajustes.MANUAL)
    rt = servico.executar(ctx, e)
    assert not ctx.balanco_resolvido
    assert rt.entradas.modo == "manual" and rt.status == "aguardando_entrada"
    origens = {v.origem for c in rt.entradas.casos for v in c.valores.values()}
    assert origens <= {"lacuna", "metodo", "recomendada"}
    # insumos do TAG (utilidade) só existem no automático; no manual a entrada final é pedida
    assert {"m_casco", "t_casco_in", "k_casco"} <= {l.chave for l in rt.entradas.lacunas}
    assert all(c.ativo for c in rt.entradas.casos)  # a regra de carga térmica depende do balanço


def test_manual_atividade_por_vazao_informada(ctx):
    e = servico.estado_inicial("B-002", mod_ajustes.MANUAL)
    e.editar("q_oil", 0.0, casos=[1])
    rt = servico.executar(ctx, e)
    c1 = rt.entradas.caso(1)
    assert not c1.ativo and "sem vazão" in c1.motivo
    assert all(1 not in l.casos for l in rt.entradas.lacunas)


def test_lacuna_lista_dependentes(ctx):
    rt = servico.executar(ctx, servico.estado_inicial("P-002"))
    t_in = next(l for l in rt.entradas.lacunas if l.chave == "t_agua_in")
    # P-46: a utilidade vai nos tubos do P-002
    assert {"m_tubo", "cp_tubo", "t_tubo_in", "rho_tubo", "mu_tubo", "k_tubo"} <= set(t_in.dependentes)


def test_revisao_confirmada_desatualizada_e_default_nao_revisavel(ctx):
    e = servico.estado_inicial("V-001")
    rt = servico.executar(ctx, e)
    tipos = {(v.origem, v.tipo, v.revisao) for v in rt.entradas.casos[0].valores.values()}
    assert ("metodo", "grade", "") in tipos and ("recomendada", "", "pendente") in tipos
    x = next(r for r in rt.entradas.revisoes() if r.chave == "tr_liquid")
    e.confirmar("tr_liquid", {n: (x.valor, x.fonte) for n in x.casos})
    rt = servico.executar(ctx, e)
    assert {c.valores["tr_liquid"].revisao for c in rt.entradas.casos} == {"confirmada"}
    e.confirmar("tr_liquid", {1: (x.valor, "outra fonte")})
    rt = servico.executar(ctx, e)
    assert rt.entradas.caso(1).valores["tr_liquid"].revisao == "desatualizada"
    assert rt.entradas.preliminar


def test_avulso_exemplo_pendencias_sem_fonte():
    cfg, origem = manual.ler_exemplo("alves_komesu")
    specs = servico.especificacoes_de("separator", "stewart_arnold", pfd=False)
    imp = manual.importar(cfg, origem, "separator", "stewart_arnold", specs)
    e = manual.avulso("ak", "separator", "stewart_arnold", imp=imp)
    rt = servico.executar(servico.Contexto(None), e)
    assert {l.chave for l in rt.entradas.lacunas} == {"tr_oil", "tr_water"}  # sem fonte no catálogo
    c = next(c for c in rt.entradas.casos if c.valores["q_oil"].faixa)
    assert c.valores["q_oil"].faixa == (180.0, 260.0) and math.isnan(c.valores["q_oil"].valor)
    e.editar("tr_oil", 10.0)
    e.editar("tr_water", 10.0)
    rt = servico.executar(servico.Contexto(None), e)
    assert rt.status == "dimensionado" and any(n.endswith("]") for n in rt.resultado.case_names)  # cantos


def test_importacao_erros_e_casamento_por_nome(ctx):
    specs = servico.especificacoes_de("knockout", "stewart_arnold_2f")
    casos = ctx.casos()
    with pytest.raises(ValueError, match="declara equipment"):
        manual.importar(exemplos()["bomba"], "x", "knockout", "stewart_arnold_2f", specs, casos)
    with pytest.raises(ValueError, match="declara method"):
        manual.importar({"method": "outro", "case": [{"name": "a"}]}, "x", "knockout", "stewart_arnold_2f", specs)
    with pytest.raises(ValueError, match="sem blocos"):
        manual.importar({}, "x", "knockout", "stewart_arnold_2f", specs)
    with pytest.raises(ValueError, match="sem 'name'"):
        manual.importar({"case": [{}]}, "x", "knockout", "stewart_arnold_2f", specs)
    with pytest.raises(ValueError, match="repetidos"):
        manual.importar({"case": [{"name": "a"}, {"name": "a"}]}, "x", "knockout", "stewart_arnold_2f", specs)
    with pytest.raises(ValueError, match="sem correspondente"):
        manual.importar({"case": [{"name": "a"}, {"name": "b"}]}, "x", "knockout", "stewart_arnold_2f", specs, casos)
    with pytest.raises(ValueError, match="desativado"):
        manual.importar({"case": [{"name": "a", "enabled": False}]}, "x", "knockout", "stewart_arnold_2f", specs,
                        casos)
    imp = manual.importar({"case": [{"name": casos[2][1], "q_oil": 5, "enabled": False},
                                    {"name": casos[0][1], "q_oil": [1, 2]}]}, "f.toml", "knockout",
                          "stewart_arnold_2f", specs, casos)
    assert imp.por_caso == {3: {"q_oil": 5.0}, 1: {"q_oil": (1.0, 2.0)}} and imp.inativos == {3: "desativado em f.toml"}
    with pytest.raises(ValueError, match="nomes de caso únicos"):
        manual.avulso("x", "knockout", "stewart_arnold_2f", nomes=["a", "a"])
    with pytest.raises(FileNotFoundError):
        manual.ler_arquivo(FIXTURES / "nao_existe.toml")
    with pytest.raises(ValueError, match="exemplo desconhecido"):
        manual.ler_exemplo("nada")


def test_associar_avulso_varios_casos(ctx):
    casos = ctx.casos()
    e = manual.avulso("a", "knockout", "stewart_arnold_2f", nomes=[casos[1][1], casos[4][1]])
    e.editar("q_oil", 3.0, casos=[2])
    e.definir_atividade(1, "fora")
    e.confirmar("tr_liquid", {2: (5.0, "f")})
    novo = manual.associar(e, tag("V-001"), casos)
    assert novo.por_caso == {5: {"q_oil": 3.0}} and novo.inativos == {2: "fora"}
    assert novo.revisoes == {("tr_liquid", 5): (5.0, "f")}
    with pytest.raises(ValueError, match="sem correspondente"):
        manual.associar(manual.avulso("b", "knockout", "stewart_arnold_2f", nomes=["x", "y"]), tag("V-001"), casos)
    with pytest.raises(ValueError, match="não é compatível"):
        manual.associar(e, tag("B-001"), casos)


def test_contexto_sem_arquivo_e_estado_incompativel(ctx):
    vazio = servico.Contexto(None)
    with pytest.raises(ValueError, match="carregue um arquivo de casos"):
        vazio.casos()
    with pytest.raises(ValueError, match="carregue um arquivo de casos"):
        vazio.resultados_balanco  # noqa: B018
    e = servico.estado_inicial("V-001")
    e.metodo = "outro"
    with pytest.raises(ValueError, match="dimensionado por knockout/stewart_arnold_2f"):
        servico.preparar(ctx, e)


def test_dimensionar_arquivo_no_contrato_do_julia():
    eq, m, casos, r = servico.dimensionar_arquivo(exemplos()["alves_komesu"])
    assert r.feasible and r.x == 6300
    with pytest.raises(ValueError, match="mas --equipamento"):
        servico.dimensionar_arquivo(exemplos()["bomba"], "separator")
    with pytest.raises(ValueError, match="informe --equipamento"):
        servico.dimensionar_arquivo({"case": [{"name": "a"}]})


def test_planta_so_manual_nao_resolve_o_balanco(monkeypatch):
    dados = carregar_casos(CASOS)
    aj = mod_ajustes.Ajustes(tags={t.tag: servico.estado_inicial(t.tag, mod_ajustes.MANUAL) for t in tags()})
    ctx = servico.Contexto(dados)
    p = planta.dimensionar(contexto=ctx, ajustes=aj)
    assert not ctx.balanco_resolvido and {t.entradas.modo for t in p.tags} == {"manual"}
    assert not p.completa
