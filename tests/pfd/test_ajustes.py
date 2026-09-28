"""F10c — arquivo de ajustes (esquema 2): ida e volta exata, leitura do legado F10b,
validação, contexto e o escritor TOML determinístico."""
import tomllib

from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.output import ajustes as saida
from fpso_siz.pfd import ajustes as A
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import manual, planta

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


CASOS = FIXTURES / "python_ref" / "design_cases_bot.json"


@pytest.fixture(scope="module")
def ctx():
    return servico.Contexto(carregar_casos(CASOS), alteracoes={"BSW_pre": 0.02})


def sessao_mista():
    """Automático com entradas/revisões/substituições, manual com importação parcial e
    atividade, avulso com faixa: tudo o que o arquivo precisa guardar."""
    aj = A.Ajustes()
    v1 = servico.estado_inicial("V-001")
    v1.editar("tr_liquid", 6.0, anteriores={n: ("recomendada", "S&A \"Tab.\" 3.2\n", 5.0) for n in range(1, 17)})
    v1.editar("q_oil", 95.0, casos=[3], anteriores={3: ("propriedade", "C-10", 1.5)})
    v1.confirmar("dm_gas", {n: (140.0, "S&A §3.7.1") for n in range(1, 17)})
    to = servico.estado_inicial("TO-001", A.MANUAL)
    to.arquivo = "rascunho.toml"
    to.importado_caso = {1: {"q_oil": 10.0}, 2: {"q_oil": 11.0}}
    to.importado_geral = {"rho_oil": 850}
    to.definir_atividade(5, "parada")
    to.editar("dm_water", 800.0)
    b1 = servico.estado_inicial("B-001")
    b1.editar("h_sucao", 8, casos=[1, 2])
    cfg, origem = manual.ler_exemplo("alves_komesu")
    imp = manual.importar(cfg, origem, "separator", "stewart_arnold",
                          servico.especificacoes_de("separator", "stewart_arnold", pfd=False))
    av = manual.avulso("ak", "separator", "stewart_arnold", imp=imp)
    av.editar("tr_oil", 10.0)
    aj.tags = {"V-001": v1, "TO-001": to, "B-001": b1}
    aj.avulsos = {"ak": av}
    return aj


def test_ida_e_volta_byte_a_byte(ctx):
    aj = sessao_mista()
    texto = saida.texto(saida.forma_canonica(aj, ctx))
    lido = A.ler(tomllib.loads(texto))
    assert saida.texto(saida.forma_canonica(lido, ctx)) == texto
    assert lido.tags["V-001"].substituidos[("q_oil", 3)] == ("propriedade", "C-10", 1.5)
    assert lido.tags["TO-001"].inativos == {5: "parada"} and lido.avulsos["ak"].nomes_casos == aj.avulsos["ak"].nomes_casos
    assert any(isinstance(v, tuple) for d in lido.avulsos["ak"].importado_caso.values() for v in d.values())
    assert lido.contexto["premissas"] == {"BSW_pre": 0.02} and lido.contexto["esquema"] == 2
    assert "\\\"Tab.\\\" 3.2\\n" in texto  # aspas e quebra de linha escapadas
    for e in lido.todos():  # o arquivo relido prepara os mesmos equipamentos
        assert servico.preparar(ctx, e).case_set() == servico.preparar(ctx, aj.estado(e.id)).case_set()


def test_ordem_canonica_e_sem_caminhos_nem_datas(ctx, tmp_path):
    texto = saida.texto(saida.forma_canonica(sessao_mista(), ctx))
    assert texto.index('[tag."B-001"]') < texto.index('[tag."TO-001"]') < texto.index('[tag."V-001"]')
    assert texto.index("tr_liquid = 6.0") < texto.index("[[tag.\"V-001\".revisao]]")
    assert str(tmp_path) not in texto and "2026" not in texto and str(FIXTURES) not in texto
    arq = saida.gravar(sessao_mista(), ctx, tmp_path / "x" / "aj.toml")
    assert arq.read_text(encoding="utf-8") == texto


def test_legado_f10b_equivale_ao_automatico(planta_ajustada, ajustes_sinteticos):
    aj = A.ler(ajustes_sinteticos)
    assert aj.legado and not aj.contexto and {e.modo for e in aj.todos()} == {"automatico"}
    assert all(not e.revisoes for e in aj.todos())
    p = planta.dimensionar(planta_ajustada.dados, ajustes=aj, balanco=planta_ajustada.contexto.resultados_balanco)
    for a, b in zip(p.tags, planta_ajustada.tags, strict=True):
        assert a.status == b.status
        if a.resultado is not None:
            assert (a.resultado.x, a.resultado.driver_case) == (b.resultado.x, b.resultado.driver_case)


@pytest.mark.parametrize("dados, mensagem", [
    ({"contexto": {"esquema": 1}}, "esquema 1 não suportado"),
    ({"contexto": {"esquema": 2}, "outro": {}}, "seções desconhecidas"),
    ({"contexto": {"esquema": 2}, "tag": {"X-1": {}}}, "TAGs desconhecidos"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"metodo": "m"}}}, "falta 'equipamento'"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "modo": "x"}}}, "modo 'x'"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "cor": 1}}}, "desconhecidos"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m",
                                                     "caso": {"1": {"inativo": "x"}}}}}, "só é informada no modo manual"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m",
                                                     "caso": {"1": {"x": 1}}}}}, "campos desconhecidos"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "caso": {"a": {}}}}},
     "não é um número de caso"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "entradas": {"a": "1"}}}},
     "não é número finito"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "entradas": {"a": [1, 2]}}}},
     "não é número finito"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "modo": "manual",
                                                     "entradas": {"a": [1, 2, 3]}}}}, "faixa deve ter"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "revisao": [{"x": 1}]}}},
     "chave e casos"),
    ({"contexto": {"esquema": 2}, "tag": {"V-001": {"equipamento": "e", "metodo": "m", "revisao": {}}}},
     "lista de tabelas"),
    ({"contexto": {"esquema": 2}, "avulso": {"V-001": {"equipamento": "e", "metodo": "m", "casos": ["a"]}}},
     "nome é de um TAG"),
    ({"contexto": {"esquema": 2}, "avulso": {"a": {"equipamento": "e", "metodo": "m", "casos": ["x", "x"]}}},
     "nomes únicos"),
    ({"contexto": {"esquema": 2}, "avulso": {"a": {"equipamento": "e", "metodo": "m", "modo": "automatico",
                                                    "casos": ["x"]}}}, "modo 'automatico'"),
    ({"contexto": {"esquema": 2}, "tag": []}, "esperada tabela"),
    ([1], "esperada tabela"),
])
def test_leitura_invalida(dados, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        A.ler(dados)


def test_validacao_na_montagem(ctx):
    for campo, mensagem in (("geral", "entrada desconhecida"), ("importado_geral", "entrada desconhecida")):
        e = servico.estado_inicial("V-001", A.MANUAL)
        getattr(e, campo)["nada"] = 1.0
        with pytest.raises(ValueError, match=mensagem):
            servico.preparar(ctx, e)
    e = servico.estado_inicial("V-001")
    e.geral["t_agua_in"] = 1.0  # insumo de outro TAG
    with pytest.raises(ValueError, match="entrada desconhecida"):
        servico.preparar(ctx, e)
    for grupo in ("inativos", "importado_caso"):
        e = servico.estado_inicial("V-001", A.MANUAL)
        getattr(e, grupo)[99] = "x" if grupo == "inativos" else {}
        with pytest.raises(ValueError, match="caso '99' não existe"):
            servico.preparar(ctx, e)
    e = servico.estado_inicial("V-001")
    e.geral["q_oil"] = (1.0, 2.0)  # faixa só no manual
    with pytest.raises(ValueError, match="não é número finito"):
        servico.preparar(ctx, e)


def test_contexto_divergencias(ctx):
    atual = ctx.identidade()
    assert A.comparar_contexto(atual, atual) == [] and A.comparar_contexto({}, atual) == []
    gravado = {**atual, "casos_sha256": "0" * 64, "casos": [1], "premissas": {}, "fpso_siz": "0.0",
               "configuracao": "x", "propriedades": {}}
    divs = {d.campo: d.bloqueante for d in A.comparar_contexto(gravado, atual)}
    assert divs == {"casos_sha256": True, "casos": True, "premissas": True, "fpso_siz": False,
                    "configuracao": False, "propriedades": False}
    e = servico.estado_inicial("V-001")
    e.metodo = "outro"
    [d] = A.comparar_contexto({}, atual, [e, manual.avulso("a", "pump", "moran", nomes=["x"])])
    assert d.campo == "metodo" and d.tag == "V-001" and d.bloqueante
    assert A.identidade_configuracao() == atual["configuracao"]


def test_edicao_restauracao_e_troca_de_modo():
    e = servico.estado_inicial("V-001", A.MANUAL)
    e.editar("q_oil", 1.0, anteriores={1: ("usuario", "", 0.5), 2: ("lacuna", "", None)})
    assert ("q_oil", 1) not in e.substituidos and e.substituidos[("q_oil", 2)] == ("lacuna", "", None)
    e.editar("q_oil", 2.0, anteriores={2: ("usuario", "", 1.0)})  # a 1ª substituição é a que fica
    assert e.substituidos[("q_oil", 2)] == ("lacuna", "", None)
    e.restaurar("q_oil", casos=[2], todos=[1, 2, 3])
    assert e.geral == {} and e.por_caso == {1: {"q_oil": 2.0}, 3: {"q_oil": 2.0}}
    assert e.chaves_ajustadas() == ["q_oil"] and e.ajustado("q_oil", 1) and not e.ajustado("q_oil", 2)
    e.restaurar("q_oil")
    assert not e.chaves_ajustadas() and not e.substituidos
    e.editar("q_gas", (1.0, 2.0))
    e.editar("rho_oil", 3.0, casos=[4])
    e.importado_geral = {"z": 1.0}
    e.definir_atividade(2, "x")
    e.definir_atividade(2, None)
    e.definir_atividade(3, "y")
    assert e.restringir([1, 2]) == [3, 4] and e.inativos == {} and e.por_caso == {}
    assert e.para_automatico() == ["q_gas"] and e.modo == A.AUTOMATICO and not e.importado_geral


def test_escritor_toml_escapes_e_tipos():
    d = {"a": {"b": "x\"\\\t\u0001y", "c": True, "d": [1, 2.5], "vazia": {}, "lista": [{"k": 1}]},
         "chave com espaço": {"n": 1e-05}}
    texto = saida.texto(d)
    assert tomllib.loads(texto) == {**d, "a": {**d["a"], "d": [1, 2.5]}}
    assert '"chave com espaço"' in texto and "\\u0001" in texto
    with pytest.raises(ValueError, match="não finito"):
        saida.texto({"a": float("nan")})
    with pytest.raises(TypeError, match="não gravável"):
        saida.texto({"a": object()})


def test_exemplo_do_readme_e_valido():
    """O exemplo de ajustes_pfd.toml documentado em docs/esquemas/README.md é lido pelo
    próprio leitor (a documentação não descreve um formato que o programa rejeita)."""
    readme = (FIXTURES.parents[1] / "docs" / "esquemas" / "README.md").read_text(encoding="utf-8")
    bloco = readme.split("## Arquivo de ajustes")[1].split("```toml\n")[1].split("```")[0]
    aj = A.ler(tomllib.loads(bloco))
    assert set(aj.tags) == {"TO-001", "V-001"} and set(aj.avulsos) == {"ko"}
    assert aj.tags["V-001"].inativos == {5: "parada programada"} and aj.contexto["premissas"] == {"eta_pump": 0.8}
