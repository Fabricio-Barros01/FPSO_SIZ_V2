"""F10x — valores PROPOSTOS para as lacunas (config/pfd/pendencias_propostas.toml):
leitura, esquema, campos, tipos, unidade, faixa, status, arquivo ausente e integração com o
serviço por TAG, o JSON, o MC e a CLI. A proposta só preenche lacuna e nunca se confunde
com valor de referência nem com valor calculado."""
import copy
import json
import math
import tomllib
from pathlib import Path

import pytest

from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.cli import main
from fpso_siz.output.latex.tag import memorial as saida_mc
from fpso_siz.output.pfd import estrutura_tag
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd import propostas as mod
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "src" / "fpso_siz" / "config" / "pfd" / "pendencias_propostas.toml"
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
TAGS_COM_LACUNA = ["B-001", "B-002", "B-003", "P-001", "P-002", "P-003", "TO-001", "TO-002"]


def _item(**mudar):
    base = dict(tag="B-001", chave="h_sucao", valor=5.0, unidade="m", status="proposto",
                origem="proposta do usuário (teste)", justificativa="teste")
    base.update(mudar)
    return {k: v for k, v in base.items() if v is not None}


def _ler(*itens, esquema=1):
    return mod.ler({"esquema": esquema, "proposta": list(itens)}, "teste.toml")


@pytest.fixture(scope="module")
def propostas():
    return mod.carregar(ARQ)


@pytest.fixture(scope="module")
def planta_propostas(planta_base, propostas):
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco, propostas=propostas)
    return dimensionar(contexto=ctx)


# ------------------------------------------------------------------ o arquivo do repositório
def test_arquivo_do_repositorio_cobre_exatamente_as_lacunas(planta_base, propostas):
    """O arquivo nasce do inventário: uma proposta por lacuna do `pfd` sem ajustes."""
    lacunas = {(t.tag.tag, l.chave) for t in planta_base.tags for l in t.entradas.lacunas}
    assert {(p.tag, p.chave) for p in propostas.itens} == lacunas
    assert len(propostas.itens) == 43 and len(propostas.sha256) == 64


def test_todo_item_e_proposto_e_sem_referencia():
    bruto = tomllib.loads(ARQ.read_text(encoding="utf-8"))
    for d in bruto["proposta"]:
        assert d["status"] == "proposto" and d["origem"].startswith(mod.PREFIXO_ORIGEM)
        assert not set(d) & set(mod.PROIBIDOS) and d["justificativa"].strip()


# ------------------------------------------------------------------ validação
@pytest.mark.parametrize("campo", mod.OBRIGATORIOS)
def test_campo_obrigatorio(campo):
    with pytest.raises(ValueError, match="faltam os campos"):
        _ler(_item(**{campo: None}))


@pytest.mark.parametrize("status", ["aprovado", "validado", "confirmado", "Proposto", ""])
def test_so_status_proposto_entra(status):
    with pytest.raises(ValueError, match="só status = 'proposto'"):
        _ler(_item(status=status))


@pytest.mark.parametrize("mudar, msg", [
    (dict(unidade="mm"), "unidade 'mm', mas o descritor usa 'm'"),
    (dict(valor="5"), "não é número finito"),
    (dict(valor=True), "não é número finito"),
    (dict(valor=math.nan), "não é número finito"),
    (dict(valor=1000.0), "fora da faixa do descritor"),
    (dict(tag="P-002", chave="t_agua_in", unidade="°C", valor=130.0), "acima do limite de 120.0"),
    (dict(tag="X-999"), "TAG desconhecido"),
    (dict(chave="nao_existe"), "não tem a entrada"),
    (dict(tag="V-001", chave="tr_liquid", unidade="min"), "proposta só preenche lacuna"),   # recomendada
    (dict(chave="rugosidade", unidade="mm", valor=0.05), "proposta só preenche lacuna"),    # default com fonte
    (dict(tag="V-001", chave="q_oil", unidade="m³/h"), "proposta só preenche lacuna"),      # regra do balanço
    (dict(origem="Moran (2016)"), "origem deve começar por"),
    (dict(justificativa="  "), "justificativa deve ser texto não vazio"),
    (dict(casos=[0]), "casos deve ser lista"),
    (dict(casos="1"), "casos deve ser lista"),
])
def test_valores_invalidos(mudar, msg):
    with pytest.raises(ValueError, match=msg):
        _ler(_item(**mudar))


def test_campos_proibidos_e_desconhecidos():
    with pytest.raises(ValueError, match="não cita fonte nem referência"):
        _ler({**_item(), "fonte": "BOT"})
    with pytest.raises(ValueError, match="campos desconhecidos"):
        _ler({**_item(), "extra": 1})


def test_duplicidade_e_casos_disjuntos():
    with pytest.raises(ValueError, match="mais de uma vez"):
        _ler(_item(), _item())
    with pytest.raises(ValueError, match="mais de uma vez"):
        _ler(_item(casos=[1, 2]), _item(casos=[2]))
    p = _ler(_item(casos=[1]), _item(casos=[2], valor=6.0))
    assert p.de("B-001", "h_sucao", 2).valor == 6.0 and p.de("B-001", "h_sucao", 3) is None


def test_esquema_e_estrutura():
    with pytest.raises(ValueError, match="esquema"):
        _ler(_item(), esquema=2)
    with pytest.raises(ValueError, match="nenhuma tabela"):
        mod.ler({"esquema": 1}, "t.toml")
    with pytest.raises(ValueError, match="não é uma tabela"):
        mod.ler({"esquema": 1, "proposta": [1]}, "t.toml")


def test_arquivo_ausente_e_toml_invalido(tmp_path):
    with pytest.raises(ValueError, match="não encontrado"):
        mod.carregar(tmp_path / "nao_existe.toml")
    ruim = tmp_path / "ruim.toml"
    ruim.write_text("esquema = [", encoding="utf-8")
    with pytest.raises(ValueError, match="TOML inválido"):
        mod.carregar(ruim)


def test_casos_citados_devem_existir(planta_base):
    with pytest.raises(ValueError, match="casos inexistentes"):
        servico.Contexto(planta_base.dados, propostas=_ler(_item(casos=[17])))


# ------------------------------------------------------------------ integração
@pytest.mark.parametrize("ident", TAGS_COM_LACUNA)
def test_propostas_fecham_as_lacunas_com_origem_propria(planta_propostas, propostas, ident):
    rt = planta_propostas.tag(ident)
    assert rt.entradas.lacunas == [] and rt.status in ("dimensionado", "inviavel")
    for p in propostas.do_tag(ident):
        for c in rt.entradas.casos:
            v = c.valores.get(p.chave) or c.insumos.get(p.chave)
            if not c.ativo or v is None or v.nao_aplicavel:
                continue
            assert (v.origem, v.valor, v.revisao) == ("proposta", p.valor, "pendente")
            assert "status proposto, a confirmar" in v.fonte


def test_valores_com_fonte_e_calculados_nao_mudam(planta_base, planta_propostas):
    """V-001/V-002 (sem lacunas) e o SG-001 dão o mesmo resultado com e sem propostas; os
    valores do balanço e dos defaults com fonte dos TAGs com proposta também."""
    for ident in ("V-001", "V-002", "SG-001"):
        a, b = planta_base.tag(ident).resultado, planta_propostas.tag(ident).resultado
        assert (a.feasible, a.x, a.y, a.ceiling) == (b.feasible, b.x, b.y, b.ceiling) or \
            (math.isnan(a.x) and math.isnan(b.x) and a.ceiling == b.ceiling)
    # Os três trocadores consomem deliberadamente o balanço térmico realizado pelo rating
    # integrado; os demais continuam invariantes às propostas que apenas fecham lacunas.
    for ident in set(TAGS_COM_LACUNA) - {"P-001", "P-002", "P-003"}:
        for ca, cb in zip(planta_base.tag(ident).entradas.casos, planta_propostas.tag(ident).entradas.casos):
            for k, va in ca.valores.items():
                if va.origem in ("balanco", "propriedade", "premissa", "recomendada", "metodo"):
                    assert cb.valores[k] == va, (ident, ca.num, k)


def test_p42_prevalece_sobre_a_proposta(planta_propostas):
    """Tratador em caso sem água (casos 1 e 4–7): gotícula não aplicável, nunca proposta."""
    rt = planta_propostas.tag("TO-001")
    assert {c.num for c in rt.entradas.casos if c.valores["dm_water"].nao_aplicavel} == {1, 4, 5, 6, 7}


def test_ajuste_do_usuario_prevalece_sobre_a_proposta(planta_base, propostas):
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco, propostas=propostas)
    estado = servico.estado_inicial("B-001")
    estado.editar("h_sucao", 7.0, None, {})
    rt = servico.executar(ctx, estado)
    v = rt.entradas.casos[0].valores["h_sucao"]
    assert (v.origem, v.valor) == ("usuario", 7.0)


def test_propostas_levam_os_tratadores_ao_dimensionamento(planta_propostas):
    """Com a gotícula proposta (1000 µm, premissa do autor), TO-001/TO-002 dimensionam e o MC
    ganha o diagrama d × Leff."""
    for ident in ("TO-001", "TO-002"):
        rt = planta_propostas.tag(ident)
        assert rt.status == "dimensionado"
        assert mc.documento(planta_propostas.contexto, rt)["calculo"]["series"]["diagrama"]


def test_trocador_integrado_mostra_perfil_e_resistencias(planta_propostas):
    rt = planta_propostas.tag("P-001")
    s = mc.documento(planta_propostas.contexto, rt)["calculo"]["series"]
    assert rt.status == "dimensionado" and len(s["perfil_tq"]) == 2 and s["resistencias"]
    assert rt.operacao is not None


def test_rating_alimenta_utilidades_sem_reusar_balanco_ideal(planta_propostas):
    """P-002/P-003 são preparados do segundo passe, inclusive quando Q_real cai."""
    planta = planta_propostas
    p001 = planta.tag("P-001")
    p002 = planta.tag("P-002")
    p003 = planta.tag("P-003")
    ideal = {r.num: r for r in resolver_todos(planta.dados, planta.prem)}
    entradas = {tag.tag.tag: {c.num: c for c in tag.entradas.casos} for tag in (p002, p003)}
    houve_reducao = False
    for estado in planta.balanco:
        op = p001.operacao.caso(estado.num)
        anterior = ideal[estado.num]
        if op.Q_real < op.Q_Pinch:
            houve_reducao = True
            assert estado.duties["Q_H"] > anterior.duties["Q_H"]
            assert estado.duties["Q_C"] != anterior.duties["Q_C"]
        quente = entradas["P-002"][estado.num]
        fria = entradas["P-003"][estado.num]
        assert quente.valores["t_casco_in"].valor == estado.T["C-07"]
        assert fria.valores["t_casco_in"].valor == estado.T["C-23"]
        if quente.ativo:
            delta = quente.insumos["t_agua_in"].valor - quente.insumos["t_agua_out"].valor
            assert quente.valores["m_tubo"].valor * quente.valores["cp_tubo"].valor * delta == pytest.approx(
                estado.duties["Q_H"] * 1000)
        if fria.ativo:
            delta = fria.insumos["t_agua_out"].valor - fria.insumos["t_agua_in"].valor
            assert fria.valores["m_tubo"].valor * fria.valores["cp_tubo"].valor * delta == pytest.approx(
                estado.duties["Q_C"] * 1000)
    assert houve_reducao


def test_json_e_mc_separam_as_propostas(planta_propostas, tmp_path):
    ctx, rt = planta_propostas.contexto, planta_propostas.tag("B-001")
    js = estrutura_tag(ctx, rt)
    assert js["proveniencia"]["propostas"]["arquivo"] == ARQ.name
    assert js["casos"][0]["valores"]["h_sucao"]["origem"] == "proposta"
    doc = mc.documento(ctx, rt)
    assert {x["chave"] for x in doc["pendencias"]["propostas"]} >= {"h_sucao", "npsh_requerido"}
    assert doc["identificacao"]["propostas"]["sha256"] == ctx.propostas.sha256
    tex = saida_mc.gerar(ctx, rt, "26/09/2026", ("0123456789ab", False))[1]
    assert "Valores PROPOSTOS pelo usuário, a confirmar" in tex and ARQ.name.replace("_", r"\_") in tex


def test_sem_propostas_nada_muda(planta_base):
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco)
    assert not ctx.propostas and mc.documento(ctx, planta_base.tag("B-001"))["pendencias"]["propostas"] == []


# ------------------------------------------------------------------ CLI e modo interativo
def test_cli_pfd_com_propostas(tmp_path):
    assert main(["pfd", "--casos", str(CASOS), "--propostas", str(ARQ), "--saida", str(tmp_path)]) == 1
    j = json.loads((tmp_path / "TO-001.json").read_text(encoding="utf-8"))
    assert j["status"] == "dimensionado" and j["lacunas"] == []


def test_cli_recusa_arquivo_invalido(tmp_path, capsys):
    ruim = tmp_path / "p.toml"
    d = tomllib.loads(ARQ.read_text(encoding="utf-8"))
    d2 = copy.deepcopy(d)
    d2["proposta"][0]["status"] = "validado"
    ruim.write_text("esquema = 1\n" + "".join(
        f'[[proposta]]\n' + "".join(f"{k} = {json.dumps(v, ensure_ascii=False)}\n" for k, v in x.items())
        for x in d2["proposta"]), encoding="utf-8")
    assert main(["pfd", "--casos", str(CASOS), "--propostas", str(ruim)]) == 2
    assert "só status = 'proposto'" in capsys.readouterr().err
    assert main(["dimensionar", "--tag", "B-001", "--casos", str(CASOS), "--auto-balanco",
                 "--propostas", str(tmp_path / "x.toml")]) == 2


@pytest.mark.latex
@pytest.mark.parametrize("ident", ["TO-001", "P-001", "P-003", "B-001"])
def test_mc_com_propostas_compila(planta_propostas, tmp_path, ident):
    from fpso_siz.output.latex import compilacao

    if not compilacao.disponivel():
        pytest.skip("latexmk ausente")
    tex = saida_mc.gravar(planta_propostas.contexto, planta_propostas.tag(ident), tmp_path, data="26/09/2026",
                          git=("0123456789ab", False))
    assert compilacao.compilar(tex).exists()


# ------------------------------------------------------------------ padrão da aplicação (decisão 2026-09-26)
def test_padrao_do_pacote_e_o_arquivo_versionado():
    p = mod.padrao()
    assert p.arquivo == mod.ARQUIVO_PADRAO and p.itens == mod.carregar(ARQ).itens


def test_cli_carrega_as_propostas_por_padrao(tmp_path, capsys):
    assert main(["pfd", "--casos", str(CASOS), "--saida", str(tmp_path / "a")]) == 1
    j = json.loads((tmp_path / "a" / "TO-001.json").read_text(encoding="utf-8"))
    assert j["status"] == "dimensionado" and j["proveniencia"]["propostas"]["arquivo"] == mod.ARQUIVO_PADRAO
    assert main(["pfd", "--casos", str(CASOS), "--sem-propostas", "--saida", str(tmp_path / "b")]) == 1
    j = json.loads((tmp_path / "b" / "TO-001.json").read_text(encoding="utf-8"))
    assert j["status"] == "aguardando_entrada" and j["proveniencia"]["propostas"] is None
    assert main(["pfd", "--casos", str(CASOS), "--sem-propostas", "--propostas", str(ARQ)]) == 2
    assert "não os dois" in capsys.readouterr().err


def test_sessao_usa_o_padrao_e_permite_desligar():
    from fpso_siz.output.terminal.sessao import Sessao

    assert Sessao(casos=CASOS)._propostas.arquivo == mod.ARQUIVO_PADRAO
    s = Sessao(casos=CASOS, propostas=False)
    assert s._propostas is None and s._flag_sem_propostas() == {"sem-propostas": True}
    assert Sessao(casos=CASOS)._flag_sem_propostas() == {"sem-propostas": False}
