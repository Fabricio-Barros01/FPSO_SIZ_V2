"""F10c — serviço por TAG: a planta e o TAG isolado passam pela mesma orquestração; o
balanço é resolvido uma vez por contexto; o manual não consulta balanço nem ChEDL; cache
por estado; paridade numérica com a F10b."""
import math

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.cli import main
from fpso_siz.core.configuracao import exemplos
from fpso_siz.output import pfd
from fpso_siz.pfd import ajustes as mod_ajustes
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import fluidos, manual, planta
from fpso_siz.pfd.tags import tag, tags

from conftest import FIXTURES

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


def test_paridade_numerica_com_a_f10b(planta_referencia):
    """Mesmos estados, lacunas, inativos e envelopes que a F10b registrou (balanço de referência)."""
    planta_base = planta_referencia
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco, oleo_vivo=False, topologia_julia=True)
    assert {t.tag.tag: t.status for t in planta_base.tags} == {
        "B-001": "aguardando_entrada", "B-002": "aguardando_entrada", "B-003": "aguardando_entrada",
        "P-001": "aguardando_entrada", "P-002": "aguardando_entrada", "P-003": "aguardando_entrada",
        "SG-001": "inviavel", "TO-001": "aguardando_entrada", "TO-002": "aguardando_entrada",
        "V-001": "dimensionado", "V-002": "dimensionado"}
    v1, v2 = planta_base.tag("V-001").resultado, planta_base.tag("V-002").resultado
    assert (v1.x, v1.driver_case, v2.x, v2.driver_case) == (4850, "BOT 08 — Mid Life", 4700, "BOT 03 — Early Life Blend")
    for t in planta_base.tags:
        so = servico.executar(ctx, servico.estado_inicial(t.tag.tag))
        assert so.status == t.status and so.entradas.lacunas == t.entradas.lacunas
        for a, b in zip(so.entradas.casos, t.entradas.casos, strict=True):
            assert (a.ativo, a.motivo) == (b.ativo, b.motivo)
            assert all(a.valores[k].valor == b.valores[k].valor or (math.isnan(a.valores[k].valor)
                       and math.isnan(b.valores[k].valor)) for k in a.valores)


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
        monkeypatch.setattr(fluidos, nome, lambda *a, **k: pytest.fail("o manual consultou o ChEDL"))
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


F10B = __import__("json").loads((FIXTURES / "pfd" / "f10b_resultados.json").read_text(encoding="utf-8"))
P42_TAGS = {"SG-001", "TO-001", "TO-002"}
P42_CHAVES = {"dm_water", "dm_oil", "tr_water", "rho_water", "mu_water"}
P44_TAGS = {"B-001", "B-002", "B-003"}
P44_CHAVES = {"piso_caso_projeto", "transicao_turndown"}   # extensões do V2 (F10x.6)
P45_TAGS = {"P-001", "P-002", "P-003"}
P45_CHAVES = {"banda_caso_projeto", "cascos_serie", "cascos_paralelo"}   # extensões do V2 (F10x.7)
MARCAS_V2 = ("P-44", "P-45", "F10x.7")


def _sem_p44(monkeypatch):
    """Desliga as extensões F10x.6–F10x.7 (P-44/P-44b das bombas; P-45, cascos em série e
    paralelo e a reotimização dos trocadores): sem os descritores de extensão e sem as
    recomendações correspondentes nos TAGs (o código que a F10b tinha). A alocação do PFD F1
    (P-46 desligada) vem de topologia_julia=True."""
    from fpso_siz.pfd.tags import tags
    from fpso_siz.sizing.bomba import MoranPumpSizing
    from fpso_siz.sizing.trocador import SaariLMTD
    for t in tags():
        for k, rec in list(t.recomendadas.items()):
            if any(m in rec["fonte"] for m in MARCAS_V2):
                monkeypatch.delitem(t.recomendadas, k)
    for classe, chaves in ((MoranPumpSizing, P44_CHAVES), (SaariLMTD, P45_CHAVES)):
        original = classe.parameters
        monkeypatch.setattr(classe, "parameters",
                            lambda self, o=original, c=chaves: [s for s in o(self) if s.key not in c])


@pytest.fixture
def plantas_f10b(monkeypatch, planta_referencia, ajustes_sinteticos):
    """As plantas com a premissa P-42 (sem fase aquosa) desligada e o balanço de referência: o
    código que a F10b tinha."""
    from fpso_siz.pfd import entradas
    from fpso_siz.sizing import separador, tratador
    monkeypatch.setattr(entradas, "_fase_aquosa", lambda metodo, valores: valores)
    monkeypatch.setattr(separador, "sem_fase_aquosa", lambda fu: False)
    monkeypatch.setattr(tratador, "sem_fase_aquosa", lambda fu: False)
    _sem_p44(monkeypatch)
    base = planta.dimensionar(planta_referencia.dados, balanco=planta_referencia.balanco, oleo_vivo=False,
                              topologia_julia=True)
    return {"sem_ajustes": base,
            "ajustes_sinteticos": planta.dimensionar(base.dados, ajustes=ajustes_sinteticos, balanco=base.balanco,
                                                     oleo_vivo=False, topologia_julia=True)}


@pytest.mark.parametrize("modo", ["sem_ajustes", "ajustes_sinteticos"])
def test_resultados_iguais_aos_da_f10b(modo, plantas_f10b, tmp_path):
    """Regressão: sem a P-42 e sem a P-44, valores de entrada, lacunas, estados, envelopes e planta.csv
    iguais aos que a F10b gravou (fixture gerada pelo código da F10b, via git archive). O
    efeito da P-42 é conferido à parte, em test_efeito_da_p42_restrito_a_fase_aquosa."""
    import hashlib
    import json
    p = plantas_f10b[modo]
    assert F10B["casos_sha256"] == p.dados.sha256
    esperado = F10B[modo]
    for t in p.tags:
        e = esperado[t.tag.tag]
        assert t.status == e["status"] and [[l.chave, list(l.casos)] for l in t.entradas.lacunas] == e["lacunas"]
        valores = [[c.num, c.ativo, {k: (None if math.isnan(v.valor) else v.valor) for k, v in c.valores.items()}]
                   for c in t.entradas.casos]
        assert hashlib.sha256(json.dumps(valores, sort_keys=True).encode()).hexdigest() == e["valores_sha256"]
        if e["envelope"] is None:
            assert t.resultado is None
        else:
            r = t.resultado
            obtido = {"viavel": r.feasible, "x": None if math.isnan(r.x) else r.x,
                      "y": None if math.isnan(r.y) else r.y, "caso_governante": r.driver_case, "mensagem": r.message}
            assert obtido == {k: e["envelope"][k] for k in obtido}
            folgas = list(r.slack) + [None] * (len(r.case_names) - len(r.slack))
            assert folgas == e["envelope"]["folgas"]
    pfd.gravar(p, tmp_path)
    assert hashlib.sha256((tmp_path / "planta.csv").read_bytes()).hexdigest() == esperado["planta_csv_sha256"]


def _num(x):
    return None if isinstance(x, float) and math.isnan(x) else x


def _valor(v):
    return (v.origem, _num(v.valor), v.faixa, v.fonte, v.revisao, v.anterior)


@pytest.mark.parametrize("modo", ["sem_ajustes", "ajustes_sinteticos"])
def test_efeito_da_p42_restrito_a_fase_aquosa(modo, plantas_f10b, planta_referencia, planta_referencia_ajustada):
    """P-42 (BOT Tab. 2.2.2.3 Notas 5 e 11; 2.3.1.1): nos casos sem água (1, 4–7), só as entradas
    dos critérios aquosos do SG-001/TO-001/TO-002 deixam de ser pedidas/revisadas e só o teto do
    SG-001 muda de caso. P-44 (F10x.6): só as bombas ganham as recomendações da banda por caso
    de projeto (e o B-001, o piso nulo do óleo limpo). Todo o resto é idêntico ao código da F10b."""
    antes = plantas_f10b[modo]
    depois = planta_referencia if modo == "sem_ajustes" else planta_referencia_ajustada
    for a, d in zip(antes.tags, depois.tags, strict=True):
        assert a.tag.tag == d.tag.tag and a.status == d.status
        sem_agua = {c.num for c in d.entradas.casos if "q_water" in c.valores and c.valores["q_water"].valor == 0}
        mudou = False
        p44 = d.tag.tag in P44_TAGS | P45_TAGS
        for ca, cd in zip(a.entradas.casos, d.entradas.casos, strict=True):
            extras = P44_CHAVES if d.tag.tag in P44_TAGS else P45_CHAVES if d.tag.tag in P45_TAGS else set()
            assert (ca.num, ca.ativo, set(ca.valores) | extras) == (cd.num, cd.ativo, set(cd.valores))
            for k, vd in cd.valores.items():
                if p44 and any(m in vd.fonte for m in MARCAS_V2):
                    assert vd.origem == "recomendada" or k in extras
                elif p44 and k in extras:
                    assert vd.origem == "metodo"
                elif vd.nao_aplicavel:
                    mudou = True
                    assert d.tag.tag in P42_TAGS and cd.num in sem_agua and k in P42_CHAVES
                    assert ca.valores[k].origem in ("lacuna", "recomendada", "metodo") and "P-42" in vd.fonte
                else:
                    assert _valor(vd) == _valor(ca.valores[k]), (d.tag.tag, cd.num, k)
        esperadas = [(l.chave, tuple(n for n in l.casos if not (n in sem_agua and l.chave in P42_CHAVES)))
                     for l in a.entradas.lacunas]
        assert [(l.chave, l.casos) for l in d.entradas.lacunas] == [x for x in esperadas if x[1]]
        ra, rd = a.resultado, d.resultado
        assert (ra is None) == (rd is None)
        if rd is None:
            continue
        if p44:
            continue    # efeito da P-44 conferido em test_p44_*
        chave = [(r.feasible, _num(r.x), _num(r.y), r.driver_case, list(r.slack)) for r in (ra, rd)]
        assert chave[0] == chave[1], d.tag.tag
        if d.tag.tag == "SG-001":
            assert ra.ceiling_case == "BOT 06 — Mid Life" and rd.ceiling_case == "BOT 02 — Early Life"
            assert rd.ceiling > ra.ceiling
        else:
            assert (ra.message, _num(ra.ceiling), ra.ceiling_case) == (rd.message, _num(rd.ceiling), rd.ceiling_case)
        assert mudou == (d.tag.tag in P42_TAGS)
