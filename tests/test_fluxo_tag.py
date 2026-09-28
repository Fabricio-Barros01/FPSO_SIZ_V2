"""F10c — fluxo por equipamento/TAG no modo interativo, roteirizado de ponta a ponta:
automático, manual, importação, preenchimento parcial, edição por caso, restauração,
revisão, redimensionamento, retomada, reaproveitamento com a Planta e troca de contexto.
O que a sessão grava tem de ser idêntico ao que o comando que ela imprime grava."""
import copy
import json
import tomllib

import pytest

from fpso_siz.output import ajustes as saida_ajustes
from fpso_siz.output.terminal import sessao as mod_sessao
from fpso_siz.pfd import ajustes as mod_ajustes
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd.entradas import especificacoes
from fpso_siz.pfd.manual import exemplos_de
from fpso_siz.pfd.tags import tag, tags
from roteiro import CASOS, abrir_tag, comandos_repetir, op, repetir_comando, rodar, tag_op


@pytest.fixture(autouse=True)
def metodos_registrados():
    import fpso_siz.sizing
    fpso_siz.sizing.registrar()


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    """Sessões roteirizadas rodam numa pasta temporária: um roteiro desalinhado nunca
    grava no repositório."""
    monkeypatch.chdir(tmp_path)


def _chave_op(ident, chave, insumos=True):
    t = tag(ident)
    chaves = [*especificacoes(t)[2], *(t.insumos if insumos else ())]
    return str(chaves.index(chave) + 1)


def _lacunas(ident, modo=mod_ajustes.AUTOMATICO):
    from fpso_siz.balanco.dados import carregar_casos
    ctx = servico.Contexto(carregar_casos(CASOS))
    return servico.executar(ctx, servico.estado_inicial(ident, modo)).entradas.lacunas


def test_tag_automatico_pendencia_revisao_exportacao_e_comando(tmp_path):
    pasta = tmp_path / "to"
    rc, out, s = rodar(*abrir_tag("TO-001", "automatico"),
                       op("tag", "pendencias"), op("escopo", "todos"), "800",
                       op("tag", "revisar"), op("revisar", "confirmar_todos"),
                       op("tag", "exportar"), str(pasta), "", "0", "0", "0")
    assert rc == 0
    # P-42: só os 11 casos com fase aquosa pedem a gotícula após coalescência
    assert "! FALTA 1 ENTRADA(S), AFETANDO 11 CASO(S) ATIVO(S)" in out and "dm_water" in out
    assert "RECOMENDADAS E DEFAULTS COM FONTE — REVISÃO PENDENTE" in out
    assert "✓ Viável" in out and "valor(es) confirmados com a fonte" in out
    cmd = comandos_repetir(out)
    assert cmd == [["dimensionar", "--sem-propostas", "--tag", "TO-001", "--casos", str(CASOS), "--auto-balanco",
                    "--ajustes", str(pasta / saida_ajustes.NOME), "--saida", str(pasta)]]
    feitos = {p: p.read_bytes() for p in (pasta / "TO-001.json", pasta / "TO-001_varredura.csv")}
    for p in feitos:
        p.unlink()
    assert repetir_comando(out) == [0]
    assert all(p.read_bytes() == b for p, b in feitos.items())
    j = json.loads(feitos[pasta / "TO-001.json"])
    assert j["status"] == "dimensionado" and not j["preliminar"] and not j["revisoes"]
    assert {v["revisao"] for c in j["casos"] for v in c["valores"].values()} <= {"", "confirmada"}
    # P-42: o valor vale só nos casos com água (gravado por caso); os sem água ficam não aplicável
    com_agua = (2, 3, *range(8, 17))
    dm = {c["num"]: c["valores"]["dm_water"]["origem"] for c in j["casos"]}
    assert all(dm[n] == "usuario" for n in com_agua) and all(dm[n] == "nao_aplicavel" for n in (1, 4, 5, 6, 7))
    aj = tomllib.loads((pasta / saida_ajustes.NOME).read_text(encoding="utf-8"))
    to = aj["tag"]["TO-001"]
    assert "entradas" not in to and to["revisao"]
    assert {int(n): sub["entradas"] for n, sub in to["caso"].items()} == {n: {"dm_water": 800.0} for n in com_agua}


def test_tag_manual_parcial_salvar_e_retomar(tmp_path):
    """Manual: não consulta o balanço; preenche uma entrada, adia as outras, salva e retoma
    depois sem perder nada."""
    n = len(_lacunas("V-001", mod_ajustes.MANUAL))
    arq = tmp_path / "aj.toml"
    rc, out, s = rodar(*abrir_tag("V-001", "manual"), op("tag", "pendencias"),
                       op("escopo", "todos"), "250", *(["0"] * (n - 1)),
                       "0", "0", op("principal", "ajustes"), op("ajustes", "salvar"), str(arq), "0", "0")
    assert rc == 0 and f"ajustes salvos em {arq}" in out
    e = s.ajustes.tags["V-001"]
    assert e.modo == "manual" and e.geral == {"q_oil": 250.0}
    assert not s.ctx.balanco_resolvido  # o manual não resolveu o balanço
    rc, out, s2 = rodar(op("principal", "equipamento"), tag_op("V-001"), "0", "0", "0", ajustes=arq)
    assert "Equipamento: V-001" not in out  # o modo salvo dispensa a escolha
    assert f"FALTA {n - 1} ENTRADA(S)" in out and "manual" in out
    assert s2.ajustes.tags["V-001"].geral == {"q_oil": 250.0}


def _rascunho_v001(pasta):
    """Arquivo de casos com os 16 casos do V-001 casados pelo NOME, com os valores do modo
    automático e um valor não finito em cada caso (a lacuna explícita de um rascunho)."""
    ctx = servico.Contexto(__import__("fpso_siz.balanco.dados", fromlist=["x"]).carregar_casos(CASOS))
    rt = servico.executar(ctx, servico.estado_inicial("V-001"))
    linhas = ['equipment = "knockout"', ""]
    for c in rt.entradas.casos:
        linhas += ["[[case]]", f'name = "{c.nome}"']
        for k, v in c.valores.items():
            if k == "mu_gas":
                linhas.append("mu_gas = nan")
            elif not v.lacuna and v.faixa == () and v.valor == v.valor:
                linhas.append(f"{k} = {v.valor!r}")
        linhas.append("")
    arq = pasta / "rascunho_v_001.toml"
    arq.write_text("\n".join(linhas), encoding="utf-8")
    return arq


def test_tag_importa_rascunho_casando_por_nome(tmp_path):
    arq = _rascunho_v001(tmp_path)
    rc, out, s = rodar(*abrir_tag("V-001", "arquivo"), str(len(exemplos_de("knockout")) + 1), str(arq),
                       "0", "0", "0")
    assert rc == 0 and f"Importado de {arq.name}: 16 caso(s); 16 valor(es) não finito(s)" in out
    e = s.ajustes.tags["V-001"]
    assert e.modo == "manual" and e.arquivo == arq.name and sorted(e.importado_caso) == list(range(1, 17))
    fx = tomllib.loads(arq.read_text(encoding="utf-8"))["case"]
    rt = servico.executar(s.ctx, e)
    assert [c.valores["q_oil"].valor for c in rt.entradas.casos] == [c["q_oil"] for c in fx]
    assert {c.valores["q_oil"].origem for c in rt.entradas.casos} == {"arquivo"}
    assert [l.chave for l in rt.entradas.lacunas] == ["mu_gas"]  # o nan do rascunho continua pendente


def test_editar_por_caso_substituido_restaurar_e_exportar(tmp_path):
    pasta = tmp_path / "v1"
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"),
                       op("tag", "editar"), _chave_op("V-001", "q_oil"), op("escopo", "escolher"), "3", "95",
                       op("tag", "editar"), _chave_op("V-001", "tr_liquid"), op("escopo", "escolher"), "3-4", "6",
                       op("tag", "exportar"), str(pasta), "",
                       op("tag", "restaurar"), "2", op("escopo", "escolher"), "4",
                       "0", "0", "0")
    assert rc == 0
    assert "Esta entrada é final do método: sobrescrevê-la não reescreve o balanço" in out
    assert "tr_liquid: entrada do usuário removida" in out
    e = s.ajustes.tags["V-001"]
    assert e.por_caso == {3: {"q_oil": 95.0, "tr_liquid": 6.0}}
    assert e.substituidos[("tr_liquid", 3)][0] == "recomendada" and ("tr_liquid", 4) not in e.substituidos
    assert e.substituidos[("q_oil", 3)][0] == "propriedade"
    j = json.loads((pasta / "V-001.json").read_text(encoding="utf-8"))
    c3 = j["casos"][2]
    assert c3["valores"]["q_oil"]["origem"] == "usuario" and c3["valores"]["q_oil"]["valor"] == 95
    assert c3["valores"]["q_oil"]["anterior"]["origem"] == "propriedade"
    rastro = {x["var"]: x for x in c3["rastro"] if x["block"] == "entradas"}
    assert "substitui propriedade" in rastro["q_oil"]["formula"] and "sem alterar o balanço" in rastro["q_oil"]["formula"]
    assert j["casos"][1]["valores"]["q_oil"]["origem"] == "propriedade"  # os outros casos não mudam


def test_revisar_confirmar_um_e_editar_item():
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), op("tag", "revisar"),
                       op("revisar", "confirmar"), "1", op("revisar", "editar"), "1", "7", "0",
                       "0", "0", "0")
    assert rc == 0
    e = s.ajustes.tags["V-001"]
    assert {k for k, _ in e.revisoes} == {"dm_gas"} and len(e.revisoes) == 16
    assert e.geral == {"tr_liquid": 7.0}
    assert all(e.substituidos[("tr_liquid", n)] == ("recomendada", tag("V-001").recomendadas["tr_liquid"]["fonte"], 5.0)
               for n in range(1, 17))
    rt = servico.executar(s.ctx, e)
    assert {x.chave for x in rt.entradas.revisoes()} == {"d_step", "sr_min", "sr_max", "sr_target"}


def test_revisao_desatualizada_volta_a_pendente():
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), op("tag", "revisar"), op("revisar", "confirmar_todos"),
                       op("tag", "editar"), _chave_op("V-001", "tr_liquid"), op("escopo", "todos"), "6",
                       "0", "0", "0")
    rt = servico.executar(s.ctx, s.ajustes.tags["V-001"])
    revs = rt.entradas.revisoes()
    assert [(x.chave, x.estado, x.origem) for x in revs] == [("tr_liquid", "desatualizada", "usuario")]
    assert "revisão desatualizada" in out


def test_equipamento_planta_equipamento_reaproveita(monkeypatch):
    chamadas = []
    original = servico.preparar

    def contar(ctx, estado):
        chamadas.append(estado.id)
        return original(ctx, estado)
    monkeypatch.setattr(servico, "preparar", contar)
    ids = [t.tag for t in tags()]
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), "0", "0",
                       op("principal", "planta"), op("planta", "abrir"), str(ids.index("V-001") + 1), "0", "0", "0")
    assert rc == 0
    assert chamadas.count("V-001") == 1 and sorted(set(chamadas)) == sorted(ids)
    assert all(chamadas.count(i) == 1 for i in ids)  # a planta não recalculou o que já estava pronto


def test_trocar_premissa_invalida_o_contexto(monkeypatch):
    chamadas = []
    original = servico.preparar
    monkeypatch.setattr(servico, "preparar", lambda ctx, e: chamadas.append(e.id) or original(ctx, e))
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), "0", "0",
                       op("principal", "premissas"), "P_D1=800", "",
                       op("principal", "equipamento"), tag_op("V-001"), "0", "0", "0")
    assert chamadas == ["V-001", "V-001"]
    rt = s.ctx.cache["V-001"][1]
    assert {c.valores["pressure"].valor for c in rt.entradas.casos} == {800.0}
    assert "premissas: P_D1 = 800.0" in out


def test_novo_arquivo_de_casos_pede_reconciliacao(tmp_path):
    bruto = json.loads(CASOS.read_text(encoding="utf-8"))
    bruto["cases"] = bruto["cases"][:-1]
    novo = tmp_path / "bot15.json"
    novo.write_text(json.dumps(bruto), encoding="utf-8")
    passos = [*abrir_tag("V-001", "automatico"), op("tag", "editar"), _chave_op("V-001", "tr_liquid"),
              op("escopo", "escolher"), "16", "6", "0", "0", op("principal", "casos"), op("casos", "trocar"), str(novo)]
    rc, out, s = rodar(*passos, "0", "0", "0")  # cancela: mantém o arquivo anterior
    assert s.dados.origem == CASOS.name and s.ajustes.tags["V-001"].por_caso == {16: {"tr_liquid": 6.0}}
    rc, out, s = rodar(*passos, op("reconciliar", "adotar_sessao"), "0", "0")
    assert s.dados.origem == "bot15.json" and s.ajustes.tags["V-001"].por_caso == {}
    assert "V-001: ajustes de casos inexistentes descartados: 16." in out


def _gravar_ajustes(tmp_path, alteracoes, texto=None):
    from fpso_siz.balanco.dados import carregar_casos
    ctx = servico.Contexto(carregar_casos(CASOS), alteracoes=alteracoes)
    aj = mod_ajustes.Ajustes(tags={"V-001": servico.estado_inicial("V-001")})
    aj.tags["V-001"].editar("tr_liquid", 6.0)
    arq = tmp_path / "aj.toml"
    saida_ajustes.gravar(aj, ctx, arq)
    if texto is not None:
        arq.write_text(texto(arq.read_text(encoding="utf-8")), encoding="utf-8")
    return arq


def test_abrir_ajustes_com_premissas_divergentes(tmp_path):
    arq = _gravar_ajustes(tmp_path, {"BSW_pre": 0.02})
    rc, out, s = rodar(op("principal", "ajustes"), op("ajustes", "abrir"), str(arq), "0", "0", "0")
    assert "premissas alteradas nos ajustes {'BSW_pre': 0.02}" in out and s.ajustes.tags == {}
    rc, out, s = rodar(op("reconciliar", "adotar_arquivo"), "0", ajustes=arq)
    assert s.alt == {"BSW_pre": 0.02} and s.ajustes.tags["V-001"].geral == {"tr_liquid": 6.0}
    rc, out, s = rodar(op("reconciliar", "adotar_sessao"), "0", ajustes=arq)
    assert s.alt == {} and s.ajustes.tags["V-001"].geral == {"tr_liquid": 6.0}


def test_abrir_ajustes_com_metodo_incompativel_descarta_o_tag(tmp_path):
    arq = _gravar_ajustes(tmp_path, {}, lambda t: t.replace('metodo = "stewart_arnold_2f"', 'metodo = "outro"'))
    rc, out, s = rodar(op("reconciliar", "adotar_sessao"), "0", ajustes=arq)
    assert "V-001: os ajustes usam knockout/outro" in out and "V-001: estado descartado" in out
    assert s.ajustes.tags == {}


def test_abrir_ajustes_legado_e_invalido(tmp_path):
    leg = tmp_path / "leg.toml"
    leg.write_text('["V-001"]\ntr_liquid = 6\n', encoding="utf-8")
    ruim = tmp_path / "ruim.toml"
    ruim.write_text('[contexto]\nesquema = 9\n', encoding="utf-8")
    rc, out, s = rodar(op("principal", "ajustes"), op("ajustes", "abrir"), str(leg), op("ajustes", "ver"),
                       op("ajustes", "abrir"), str(ruim), op("ajustes", "descartar"), "s", "0", "0")
    assert "formato da F10b" in out and "esquema 9 não suportado" in out and "ajustes descartados." in out
    assert "V-001" in out and s.ajustes.tags == {}


def test_planta_filtro_e_exportacao_igual_ao_comando(tmp_path):
    pasta = tmp_path / "planta"
    rc, out, s = rodar(op("principal", "planta"), op("planta", "filtro"), "1", op("planta", "exportar"), str(pasta), "",
                       "0", "0")
    assert rc == 0 and "filtro: BOT 01 — Early Life" in out
    linha = next(li for li in out.splitlines() if "[B-002" in li and "filtro" not in li and "→" in li.split("[B-002")[0]
                 and li.count("[") == 1 and "-]" in li)
    assert linha
    assert comandos_repetir(out) == [["pfd", "--sem-propostas", "--casos", str(CASOS), "--ajustes", str(pasta / saida_ajustes.NOME),
                                      "--saida", str(pasta)]]
    feitos = {p: p.read_bytes() for p in pasta.iterdir() if p.name != saida_ajustes.NOME}
    assert len(feitos) == 23
    for p in feitos:
        p.unlink()
    assert repetir_comando(out) == [1]
    assert all(p.read_bytes() == b for p, b in feitos.items())


def test_planta_pendencias_percorre_o_formulario_do_tag():
    n = len(_lacunas("B-001"))
    rc, out, s = rodar(op("principal", "planta"), op("planta", "pendencias"),
                       op("escopo", "todos"), "12", *(["0"] * (n - 1)))
    assert "Pendências de B-001" in out
    assert s.ajustes.tags["B-001"].geral == {"h_geometrica": 12.0}
    assert set(s.ajustes.tags) == {"B-001"}  # nada é aplicado a outros TAGs


def test_edicao_invalida_e_desfeita_e_enter_adia():
    lac = [l.chave for l in _lacunas("P-002")]
    i_in, i_out = lac.index("t_agua_in"), lac.index("t_agua_out")
    resp = []
    for i, _ in enumerate(lac):
        if i == i_in:
            resp += [op("escopo", "todos"), "100"]
        elif i == i_out:
            resp += [op("escopo", "todos"), "120"]
        elif i == 0:
            resp += [op("escopo", "todos"), ""]
        else:
            resp += ["0"]
    rc, out, s = rodar(*abrir_tag("P-002", "automatico"), op("tag", "pendencias"), *resp, "0", "0", "0")
    assert "edição desfeita" in out and "sentido da troca" in out
    assert f"adiado: {lac[0]} continua pendente." in out
    assert s.ajustes.tags["P-002"].geral == {"t_agua_in": 100.0}


def test_atividade_no_manual_e_acao_indisponivel():
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), op("tag", "atividade"), "0", "0", "0")
    assert "indisponível: só no modo manual." in out
    rc, out, s = rodar(*abrir_tag("V-001", "manual"), op("tag", "atividade"), "3", "",
                       op("tag", "atividade"), "4", "parada programada", op("tag", "atividade"), "3", "0", "0", "0")
    assert s.ajustes.tags["V-001"].inativos == {4: "parada programada"}
    rt = servico.executar(s.ctx, s.ajustes.tags["V-001"])
    assert [c.num for c in rt.entradas.casos if not c.ativo] == [4]
    assert all(4 not in l.casos for l in rt.entradas.lacunas)


def test_rastro_varredura_e_entradas_do_tag():
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), op("tag", "rastro"), "8", op("tag", "varredura"),
                       op("tag", "entradas"), "", "0", "0", "0")
    assert "V-001 · BOT 08 — Mid Life" in out and "propriedades" in out and "◀" in out
    assert "ENTRADAS · BOT 01 — Early Life" in out and "correlação" in out and "balanço" in out
    rc, out, s = rodar(*abrir_tag("B-001", "automatico"), op("tag", "entradas"), "1", "0", "0", "0")
    assert "premissa P-" in out and "lacuna" in out  # a premissa mantém o identificador


def test_trocar_modo_e_voltar_ao_automatico():
    rc, out, s = rodar(*abrir_tag("V-001", "automatico"), op("tag", "modo"), op("preenchimento", "manual"),
                       op("tag", "modo"), op("preenchimento", "automatico"), "0", "0", "0")
    assert "V-001: preenchimento manual." in out and "V-001: preenchimento automático (balanço preliminar)." in out
    assert s.ajustes.tags["V-001"].modo == "automatico"


def test_avulso_associado_a_tag_compativel():
    import fpso_siz.sizing  # noqa: F401
    from fpso_siz.core import registro
    eq = str([e.method_id for e in registro.equipments()].index("knockout") + 1)
    rc, out, s = rodar(op("principal", "equipamento"), str(len(tags()) + 1), eq, "", op("preenchimento", "arquivo"),
                       "1", op("tag", "associar"), "1", "0", "0", "0")
    assert "associado a V-001" in out
    e = s.ajustes.tags["V-001"]
    assert e.modo == "manual" and e.arquivo == "exemplo:knockout" and not s.ajustes.avulsos
    assert e.importado_geral and not e.importado_caso


def test_avulso_automatico_pede_tag_compativel():
    import fpso_siz.sizing  # noqa: F401
    from fpso_siz.core import registro
    eq = str([e.method_id for e in registro.equipments()].index("knockout") + 1)
    rc, out, s = rodar(op("principal", "equipamento"), str(len(tags()) + 1), eq, "",
                       op("preenchimento", "automatico"), "2", "0", "0", "0")
    assert "Qual TAG compatível?" in out and "V-002 · Vaso desgaseificador 2" in out
    assert s.ajustes.tags["V-002"].modo == "automatico" and not s.ajustes.avulsos


# ------------------------------------------------------------------ menus vêm da configuração
def test_despacho_cobre_exatamente_os_ids_do_toml():
    from fpso_siz.core.configuracao import carregar
    menus = carregar("interativo.toml")["menus"]
    assert set(menus) == set(mod_sessao.DESPACHO)
    for nome, m in menus.items():
        assert [a["id"] for a in m["acoes"]] and set(mod_sessao.DESPACHO[nome]) == {a["id"] for a in m["acoes"]}, nome
        for metodo in filter(None, mod_sessao.DESPACHO[nome].values()):
            assert callable(getattr(mod_sessao.Sessao, metodo)), metodo


def test_menu_segue_textos_e_ordem_do_toml(monkeypatch):
    from fpso_siz.core.configuracao import carregar
    cfg = copy.deepcopy(carregar("interativo.toml"))
    acoes = cfg["menus"]["principal"]["acoes"]
    acoes.reverse()
    for a in acoes:
        a["rotulo"] = f"«{a['id'].upper()}»"
    cfg["menus"]["principal"]["titulo"] = "Menu renomeado"
    real = mod_sessao.carregar
    monkeypatch.setattr(mod_sessao, "carregar", lambda nome: cfg if nome == "interativo.toml" else real(nome))
    rc, out, s = rodar("1", "0", "0")  # a 1ª opção agora é 'ajustes'
    bloco = out.split("Menu renomeado")[1].split("Sair")[0]
    linhas = [li.split() for li in bloco.strip().splitlines()][:-1]  # a última é o '0' de sair
    assert [li[1] for li in linhas] == [f"«{a['id'].upper()}»" for a in acoes]
    assert "Ajustes da sessão" in out


def test_resultado_parcial_salvo_e_reproduzido(tmp_path):
    """TAG ainda aguardando entrada: exporta mesmo assim, e o comando reproduz (código 1)."""
    pasta = tmp_path / "b1"
    n = len(_lacunas("B-001"))
    rc, out, s = rodar(*abrir_tag("B-001", "automatico"), op("tag", "pendencias"), op("escopo", "todos"), "12",
                       *(["0"] * (n - 1)), op("tag", "exportar"), str(pasta), "", "0", "0", "0")
    feitos = {p: p.read_bytes() for p in (pasta / "B-001.json", pasta / "B-001_varredura.csv")}
    for p in feitos:
        p.unlink()
    assert repetir_comando(out) == [1]
    assert all(p.read_bytes() == b for p, b in feitos.items())
    j = json.loads(feitos[pasta / "B-001.json"])
    assert j["status"] == "aguardando_entrada" and j["envelope"] is None and len(j["lacunas"]) == n - 1
    assert feitos[pasta / "B-001_varredura.csv"].decode("utf-8").count("\n") == 1  # só o cabeçalho


def test_ajustes_abertos_sem_casos_conferem_o_bot_depois(tmp_path, monkeypatch):
    arq = _gravar_ajustes(tmp_path, {})
    bruto = json.loads(CASOS.read_text(encoding="utf-8"))
    bruto["cases"][0]["T_C"] += 1
    outro = tmp_path / "outro.json"
    outro.write_text(json.dumps(bruto), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc, out, s = rodar(op("principal", "casos"), str(outro), "0", "0", casos=None, ajustes=arq)
    assert "O arquivo de casos mudou" in out and s.dados is None  # cancelado: nada aplicado em silêncio
    rc, out, s = rodar(op("principal", "casos"), str(CASOS), op("casos", "trocar"), str(outro),
                       op("reconciliar", "adotar_sessao"), "0", "0", casos=None, ajustes=arq)
    assert out.count("O arquivo de casos mudou") == 1 and s.dados.origem == "outro.json"
    assert s.ajustes.tags["V-001"].geral == {"tr_liquid": 6.0}
