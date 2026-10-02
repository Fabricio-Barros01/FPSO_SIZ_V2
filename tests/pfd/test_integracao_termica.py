"""Integração térmica REALIZADA na planta (ADR 0005; docs/validacao/43).

O que estes testes cobram:

- o ponto fixo das propriedades fecha, e o U deixa de ser o do ponto de projeto;
- a energia fecha caso a caso: o que o pré-aquecedor não recuperou aparece INTEGRALMENTE nas
  duas utilidades;
- a integração não reabre o balanço — e isso é verificado, não presumido: as temperaturas de
  DESTINO (piso de tratamento, teto de estocagem) não mudam, e com elas o reciclo;
- quem consome carga residual é preparado com o estado REALIZADO, e a proveniência da entrada
  diz isso ao lado do número;
- o caso sem carga a recuperar sai como `sem_carga`, não como "não avaliável".
"""
import math

import pytest

from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import integracao_termica as itg
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar
from fpso_siz.sizing.rating import LIMITADO_PELA_AREA, LIMITADO_PELO_ALVO, NAO_AVALIAVEL

TOL_KW = 1e-6


def _citados_no_codigo(modulo, nomes):
    """Os `nomes` que aparecem em literal de texto ou em identificador do módulo, ignorando
    docstrings (que são explicação, não código)."""
    import ast
    import pathlib

    arvore = ast.parse(pathlib.Path(modulo.__file__).read_text(encoding="utf-8"))
    docs = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = getattr(no, "body", [])
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
                docs.add(id(corpo[0].value))
    textos = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docs:
            textos.append(no.value)
        for atributo in ("name", "id", "attr", "arg"):
            valor = getattr(no, atributo, None)
            if isinstance(valor, str):
                textos.append(valor)
    return sorted({n for n in nomes if any(n in t for t in textos)})


@pytest.fixture(scope="module")
def ctx(planta_base):
    c = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                         propostas=mod_propostas.padrao())
    return c


@pytest.fixture(scope="module")
def integracao(ctx):
    return ctx.integracao


def test_a_declaracao_descreve_o_codigo():
    """Nenhuma corrente, carga ou premissa é nomeada no módulo: tudo vem do TOML."""
    c = itg.cfg()
    assert c["tag_recuperador"] and c["carga_recuperada"] and c["fonte"]
    assert {l["id"] for l in c["lado"]} == {"tubo", "casco"}
    for l in c["lado"]:
        assert l["sentido"] in ("aquecer", "resfriar")
        assert all(l[k] for k in ("entrada", "saida", "capacidade", "destino_premissa",
                                  "corrente_destino", "carga_residual", "tag_residual", "fonte"))
    # nenhuma corrente, carga ou premissa aparece no CÓDIGO (literais e identificadores); em
    # comentário e docstring elas podem aparecer, e é onde a explicação precisa delas
    assert not _citados_no_codigo(itg, ("C-06", "C-07", "C-22", "C-23", "Q_pre", "Q_H", "Q_C",
                                        "T_trat", "T_store"))


def test_integracao_aplicavel_e_o_recuperador_dimensionado(integracao):
    assert integracao.aplicavel and not integracao.motivo
    assert integracao.resultado.status == servico.DIMENSIONADO
    assert len(integracao.casos) == len(integracao.estados)


def test_ponto_fixo_das_propriedades_fecha(integracao):
    tol = float(itg.cfg()["iteracao"]["tolerancia_K"])
    assert integracao.convergiu and integracao.desvio_K <= tol
    assert integracao.iteracoes >= 2, "uma passagem só não é ponto fixo"


def test_u_nao_e_o_do_ponto_de_projeto(ctx, integracao):
    """Reavaliar as propriedades na temperatura realizada tem de mudar o U de algum caso de
    turndown — se não mudasse, o laço seria decorativo."""
    uma_passagem, _, it, _, _ = itg.dimensionar_recuperador(ctx, max_iteracoes=1)
    assert it == 1
    u_final = {c.num: (c.operacao or {}).get("u") for c in integracao.casos if c.ativo}
    op1 = itg._operacao_por_caso(uma_passagem)
    u_inicial = {num: o.get("u") for num, o in op1.items()}
    comuns = [n for n in u_final if n in u_inicial and u_final[n] and u_inicial[n]]
    assert comuns
    assert any(abs(u_final[n] - u_inicial[n]) > 1e-6 for n in comuns)


def test_estados_do_rating_sao_os_declarados(integracao):
    permitidos = {LIMITADO_PELO_ALVO, LIMITADO_PELA_AREA, NAO_AVALIAVEL, itg.SEM_CARGA,
                  "sem_forca_motriz"}
    assert {c.estado_rating for c in integracao.casos} <= permitidos
    for c in integracao.casos:
        if not c.ativo:
            assert c.estado_rating == itg.SEM_CARGA and c.q_alvo == 0.0 and c.q_realizado == 0.0
        else:
            assert c.estado_rating != itg.SEM_CARGA


def test_um_caso_dimensiona_e_realiza_o_alvo_inteiro(integracao):
    dimensionantes = [c for c in integracao.casos if c.dimensionante]
    assert len(dimensionantes) == 1
    assert dimensionantes[0].fracao_realizada == pytest.approx(1.0, rel=1e-6)
    assert dimensionantes[0].estado_rating == LIMITADO_PELO_ALVO


def test_energia_fecha_caso_a_caso(integracao):
    """O que não foi recuperado aparece INTEGRALMENTE nas duas utilidades: é a conta que
    justifica cobrar o resíduo do aquecedor e do resfriador."""
    for c in integracao.casos:
        if not c.ativo or not c.avaliavel:
            continue
        nao = c.q_nao_recuperado
        assert nao >= -TOL_KW
        for l in c.lados:
            assert l.q_residual - l.q_residual_preliminar == pytest.approx(nao, abs=1e-6)
            # a saída realizada é consistente com a carga realizada e a capacidade do balanço
            sentido = 1.0 if l.aquece else -1.0
            esperado = l.t_in + sentido * c.q_realizado / l.capacidade
            assert l.t_out_real == pytest.approx(esperado, abs=1e-9)


def test_recuperacao_realizada_nunca_passa_do_alvo(integracao):
    for c in integracao.casos:
        if c.avaliavel:
            assert c.q_realizado <= c.q_alvo + TOL_KW
            assert 0 <= c.fracao_realizada <= 1 + 1e-9
    assert integracao.q_realizado_total <= integracao.q_alvo_total + TOL_KW


def test_a_integracao_nao_reabre_o_balanco(integracao, planta_base):
    """Enquanto a temperatura de DESTINO não muda, o reciclo do balanço não é tocado. A
    verificação é por caso e o resultado é declarado — não presumido."""
    assert integracao.destinos_alterados == [] if hasattr(integracao, "destinos_alterados") else True
    especificacoes = {l["id"]: l for l in itg.cfg()["lado"]}
    for r, ci, novo in zip(planta_base.balanco, integracao.casos, integracao.estados):
        for l in ci.lados:
            destino = especificacoes[l.id]["corrente_destino"]
            assert novo.T[destino] == pytest.approx(r.T[destino], abs=1e-9), (r.num, destino)
            for corrente in especificacoes[l.id]["correntes_no_destino"]:
                assert novo.T[corrente] == pytest.approx(r.T[corrente], abs=1e-9)
        assert not any(l.destino_cruzado for l in ci.lados), r.num


def test_estado_realizado_reescreve_so_o_declarado(integracao, planta_base):
    c = itg.cfg()
    reescritas = {c["carga_recuperada"], *(l["carga_residual"] for l in c["lado"])}
    saidas = {l["saida"] for l in c["lado"]} | {l["corrente_destino"] for l in c["lado"]}
    saidas |= {x for l in c["lado"] for x in l["correntes_no_destino"]}
    for r, novo, ci in zip(planta_base.balanco, integracao.estados, integracao.casos):
        assert novo.streams == r.streams and novo.P == r.P and novo.gas == r.gas
        assert {k for k in r.duties if novo.duties[k] != r.duties[k]} <= reescritas
        assert {k for k in r.T if novo.T[k] != r.T[k]} <= saidas
        if ci.ativo and ci.avaliavel:
            assert set(novo.integracao) <= reescritas | saidas
        else:
            assert novo is r   # caso sem carga: nada a reescrever


def test_quem_consome_residual_le_o_estado_realizado(ctx, integracao):
    """O aquecedor e o resfriador são preparados com o estado REALIZADO, e a proveniência da
    entrada declara isso: o número não se apresenta como do balanço preliminar."""
    c = itg.cfg()
    recuperador = c["tag_recuperador"]
    assert ctx.balanco_do_tag(recuperador) is ctx.balanco
    for l in c["lado"]:
        estados = ctx.balanco_do_tag(l["tag_residual"])
        assert estados is not ctx.balanco
        assert estados == list(integracao.estados)
        rt = servico.executar(ctx, ctx.estado_tag(l["tag_residual"]))
        ativos = [x for x in rt.entradas.casos if x.ativo]
        assert ativos
        com_nota = [x for x in ativos
                    if any("REALIZADA" in v.fonte or "RESIDUAL" in v.fonte for v in x.valores.values())]
        assert com_nota, l["tag_residual"]


def test_a_carga_do_aquecedor_cresce_quando_a_recuperacao_cai(ctx, integracao):
    """Consistência física do conjunto: menos recuperação, mais utilidade — nunca o contrário."""
    for c in integracao.casos:
        if not c.ativo or not c.avaliavel:
            continue
        for l in c.lados:
            assert l.q_residual >= l.q_residual_preliminar - TOL_KW
        if c.q_nao_recuperado > TOL_KW:
            assert all(l.q_residual > l.q_residual_preliminar for l in c.lados)


def test_planta_inteira_fica_completa_com_a_integracao(planta_base):
    """O conjunto integrado: nenhum TAG fica inviável nem aguardando entrada."""
    planta = dimensionar(contexto=servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                                                   propostas=mod_propostas.padrao()))
    estados = {t.tag.tag: t.status for t in planta.tags}
    assert all(s == servico.DIMENSIONADO for s in estados.values()), estados
    assert planta.completa


def _sem_geometria(planta_base, **kw):
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco, propostas=mod_propostas.padrao(), **kw)
    est = servico.estado_inicial(itg.cfg()["tag_recuperador"])
    est.editar("d_casco_max", 100.0)   # nenhum feixe cabe: o TAG fica inviável
    ctx.fixar_estado(est)
    return ctx


def test_recuperador_sem_geometria_invalida_a_integracao(planta_base):
    """Sem geometria instalada não há classificação, e a recuperação preliminar seria IDEALIZADA:
    a integração é INVÁLIDA (Fase C, nota 46) e os TAGs de carga residual NÃO são dimensionados
    com ela — ficam aguardando, com uma lacuna não editável que diz por quê."""
    ctx = _sem_geometria(planta_base)
    i = ctx.integracao
    assert not i.aplicavel and not i.valida and i.cenario == itg.INVALIDA and i.motivo
    assert i.casos == ()
    for l in itg.cfg()["lado"]:
        rt = servico.executar(ctx, ctx.estado_tag(l["tag_residual"]))
        assert rt.status == servico.AGUARDANDO
        lac = next(x for x in rt.entradas.lacunas if x.chave == itg.cfg()["lacuna"]["chave"])
        assert not lac.editavel and lac.casos and "bypass" in lac.dica


def test_bypass_so_quando_declarado(planta_base):
    """O cenário de bypass (Q_real = 0) é EXPLÍCITO: o aquecedor e o resfriador recebem a carga
    inteira — preliminar mais a recuperação que não houve — em todos os casos com carga."""
    ctx = _sem_geometria(planta_base, cenario_recuperador="bypass")
    i = ctx.integracao
    assert i.aplicavel and i.valida and i.cenario == itg.CENARIO_BYPASS and "BYPASS" in i.motivo
    ativos = [c for c in i.casos if c.ativo]
    assert ativos and all(c.q_realizado == 0.0 and c.estado_rating == itg.BYPASS for c in ativos)
    for c in ativos:
        for lado in c.lados:
            # sem recuperação, a utilidade leva a corrente da ENTRADA do pré-aquecedor ao destino
            alvo = max(lado.t_destino, lado.t_in) if lado.aquece else min(lado.t_destino, lado.t_in)
            assert lado.t_out_real == lado.t_in
            assert lado.q_residual == pytest.approx(lado.capacidade * abs(alvo - lado.t_in), rel=1e-12)
            assert lado.q_residual >= lado.q_residual_preliminar - 1e-9


# ------------------------------------------------------------------ saída (JSON e CSV)
def test_json_e_csv_da_integracao_saem_do_servico(tmp_path, planta_base):
    """A saída LÊ a integração; não recalcula nada. JSON estrito: não finito vira null."""
    import csv
    import json

    from fpso_siz.output import pfd as saida

    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                           propostas=mod_propostas.padrao())
    planta = dimensionar(contexto=ctx)
    arquivos = saida.gravar(planta, tmp_path)
    arq_json = tmp_path / saida.ARQ_INTEGRACAO
    arq_csv = tmp_path / "integracao_termica.csv"
    assert arq_json in arquivos and arq_csv in arquivos

    d = json.loads(arq_json.read_text(encoding="utf-8"))
    i = ctx.integracao
    assert d["aplicavel"] and d["tag_recuperador"] == itg.cfg()["tag_recuperador"]
    assert len(d["casos"]) == len(i.casos)
    assert d["total"]["realizado"] == pytest.approx(i.q_realizado_total)
    assert d["ponto_fixo"]["convergiu"] is True
    for caso, ci in zip(d["casos"], i.casos):
        assert caso["num"] == ci.num and caso["estado_rating"] == ci.estado_rating
        assert caso["carga_realizada_kW"] == pytest.approx(ci.q_realizado)
        assert len(caso["lados"]) == len(ci.lados)

    linhas = list(csv.DictReader(arq_csv.read_text(encoding="utf-8").splitlines()))
    assert len(linhas) == len(i.casos)
    assert [int(x["caso"]) for x in linhas] == [c.num for c in i.casos]
    assert all(set(x) == set(saida.COLUNAS_INTEGRACAO) for x in linhas)


def test_o_tag_que_nao_participa_nao_ganha_a_secao(tmp_path, planta_base):
    """Só o recuperador e quem consome carga residual carregam a integração no JSON do TAG."""
    import json

    from fpso_siz.output import pfd as saida

    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                           propostas=mod_propostas.padrao())
    planta = dimensionar(contexto=ctx)
    participam = {itg.cfg()["tag_recuperador"], *(l["tag_residual"] for l in itg.cfg()["lado"])}
    for t in planta.tags:
        saida.gravar_tag(ctx, t, tmp_path)
        d = json.loads((tmp_path / f"{t.tag.tag}.json").read_text(encoding="utf-8"))
        tem = d.get("integracao_termica") is not None
        assert tem == (t.tag.tag in participam), t.tag.tag


def test_conjunto_de_cascos_e_rating_chegam_ao_json_do_tag(tmp_path, planta_base):
    """`derivados_conjunto` é a ponte entre o que o motor avaliou e o que a saída mostra: sem
    ela o número do conjunto e do rating não sairia do motor."""
    import json

    from fpso_siz.output import pfd as saida

    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                           propostas=mod_propostas.padrao())
    rt = servico.executar(ctx, ctx.estado_tag(itg.cfg()["tag_recuperador"]))
    saida.gravar_tag(ctx, rt, tmp_path)
    d = json.loads((tmp_path / f"{rt.tag.tag}.json").read_text(encoding="utf-8"))
    conj = d["envelope"]["resultado"]["derivados_conjunto"]
    assert conj["rating_fora_do_projeto"] == 1.0
    assert conj["cascos_serie"] >= 1 and conj["area_total"] > 0
    assert len(conj["q_realizado_por_caso"]) == len(conj["q_alvo_por_caso"])
    dimensionam = [c["dimensiona"] for c in d["envelope"]["casos"]]
    assert sum(dimensionam) == 1
    # o caso só classificado não tem folga de comprimento comparável: sai como null
    assert all(c["folga"] is None for c in d["envelope"]["casos"] if not c["dimensiona"])


def test_a_planta_e_a_integracao_dao_o_MESMO_p001(planta_base):
    """Um caminho produtivo só: o resultado do recuperador na planta É o do ponto fixo.

    Sem isto a planta o dimensionaria numa passagem (propriedades na temperatura do alvo) e a
    integração no ponto fixo (propriedades na temperatura realizada) — dois números para o
    mesmo TAG na mesma execução."""
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                           propostas=mod_propostas.padrao())
    planta = dimensionar(contexto=ctx)
    rt = planta.tag(itg.cfg()["tag_recuperador"])
    assert rt is ctx.integracao.resultado
    assert ctx.integracao.iteracoes >= 2


def test_variante_de_estudo_nao_usa_o_laco(planta_base):
    """Uma variante (outro estado do mesmo TAG) é avaliada sozinha, numa passagem: ela serve
    para medir o efeito de UMA mudança, e não pode herdar o ponto fixo do estado da sessão."""
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                           propostas=mod_propostas.padrao())
    est = servico.estado_inicial(itg.cfg()["tag_recuperador"])
    est.editar("cascos_serie", 7.0)
    assert ctx.resultado_integrado(est) is None
    rt = servico.executar(ctx, est)
    assert rt is not ctx.integracao.resultado
