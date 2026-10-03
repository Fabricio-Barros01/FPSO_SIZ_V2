"""Segunda auditoria do P-001 (docs/validacao/46): atividade térmica × passagem de vazão,
atendimento × completude hidráulica, metodologia do rating no MC, continuidade preliminar →
pós-rating nos MC, ρ do casco pela corrente do casco e premissa única de comprimento.

Nenhum número da execução auditada é fixado: o que se prova é a regra (classificação, origem e
coerência entre estados e saídas)."""
import math
from dataclasses import replace

import pytest

from fpso_siz.core.configuracao import carregar
from fpso_siz.output.latex.tag import memorial as saida_mc
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd.entradas import Valor


def _conclusoes():
    return carregar("pfd/p_001_busca.toml")["avaliacao"]["conclusoes"]


def _crit(nome, status, valor=1.0, com_limite=True, natureza="", obrigatorio=True, motivo="m"):
    return servico._criterio(nome, "e", valor, None, "u", status, motivo=motivo, com_limite=com_limite,
                             natureza=natureza, obrigatorio=obrigatorio)


# ------------------------------------------------------------------ 1. Q = 0 com vazão
def test_carga_nula_com_vazao_tem_hidraulica_avaliada(planta_propostas):
    """O balanço não modela bypass (C-07 = C-06, C-23 = C-22 em massa): com Q = 0 as correntes
    atravessam o P-001, e a velocidade/perda de carga são avaliadas — não 'não aplicável'."""
    op = planta_propostas.tag("P-001").operacao
    balanco = {r.num: r for r in planta_propostas.balanco}
    sem_carga = [c for c in op.casos if c.termico["status"] == servico.TERMICO_TETO_NULO]
    assert sem_carga, "a base de casos tem casos sem carga no P-001"
    for c in sem_carga:
        r = balanco[c.num]
        assert r.duties["Q_pre"] == 0
        assert sum(r.streams["C-06"].values()) == sum(r.streams["C-07"].values()) > 0
        assert c.diagnosticos["vazao_tubo_kg_s"] > 0 and c.diagnosticos["vazao_casco_kg_s"] > 0
        h = c.hidraulico
        assert h["atendimento"] != servico.NAO_APLICAVEL and c.papel != servico.SEM_VAZAO
        crit = {k["criterio"]: k for k in h["criterios"]}
        teto = crit["velocidade_maxima_tubo"]
        assert teto["status"] in (servico.ATENDE, servico.NAO_ATENDE) and teto["valor"] > 0
        # a película é critério térmico: sem carga, não se aplica (com motivo)
        assert crit["pelicula_tubo"]["status"] == servico.NAO_APLICAVEL and crit["pelicula_tubo"]["motivo"]
        assert c.termico["motivo"]


def test_teto_nulo_tem_estado_termico_explicito(planta_propostas):
    """Recuperação zerada pelo teto Pinch (aproximação disponível < mínima da P-32), não pela
    geometria: estado próprio, com as duas aproximações; nada a iterar; saídas = entradas."""
    op = planta_propostas.tag("P-001").operacao
    balanco = {r.num: r for r in planta_propostas.balanco}
    nulos = [c for c in op.casos if c.Q_Pinch == 0]
    assert nulos
    for c in nulos:
        r, t = balanco[c.num], c.termico
        assert t["status"] == servico.TERMICO_TETO_NULO and c.Q_real == 0
        assert t["aproximacao_disponivel_K"] == r.T["C-22"] - r.T["C-06"]
        assert t["aproximacao_disponivel_K"] < t["aproximacao_minima_K"]
        assert t["fracao_recuperada"] is None, "0/0 não é recuperação plena nem parcial"
        assert c.convergencia["estado"] == servico.CONVERGENCIA_INTERVALO_NULO and c.convergencia["mensagem"]
        assert (c.t_fria_out, c.t_quente_out) == (r.T["C-06"], r.T["C-22"])
    av = op.avaliacao()["atendimento_termico"]
    assert av["casos_teto_nulo"] == [c.num for c in nulos]
    assert not set(av["casos_parciais"]) & set(av["casos_teto_nulo"])


def test_caso_de_projeto_da_p45_e_o_de_maior_vazao_volumetrica_com_vazao(planta_propostas):
    rt = planta_propostas.tag("P-001")
    op = rt.operacao
    vol = {c.num: c.diagnosticos["vazao_tubo_kg_s"] / c.diagnosticos["rho_tubo_kg_m3"] for c in op.casos}
    assert op.caso_projeto == max(vol, key=vol.get)
    assert [c.num for c in op.casos if c.papel == servico.PROJETO] == [op.caso_projeto]


def test_sem_vazao_e_a_unica_hidraulica_nao_aplicavel():
    h = servico._nao_aplicavel("sem vazão", _conclusoes())
    assert h["atendimento"] == h["completude"] == servico.NAO_APLICAVEL and h["motivo"]


# ------------------------------------------------------------------ 2. atendimento × completude
def test_resumo_separa_atendimento_completude_e_informativos():
    c = _conclusoes()
    so_valores = [_crit("v", servico.ATENDE),
                  _crit("dp_t", servico.SEM_CRITERIO, 10.0, com_limite=False, natureza=servico.CORRELACAO_APLICAVEL),
                  _crit("v_s", servico.SEM_CRITERIO, 1.0, com_limite=False, obrigatorio=False)]
    r = servico._resumo_hidraulico(so_valores, c)
    assert (r["atendimento"], r["completude"]) == (servico.ATENDE, servico.INCOMPLETA)
    assert r["conclusao"] == "Critérios avaliados atendidos; verificação hidráulica incompleta."
    assert [x["criterio"] for x in r["lacunas"]] == ["dp_t"], "valor sem limite deixa a verificação incompleta"

    ausente = [_crit("v", servico.ATENDE),
               _crit("dp_t", servico.NAO_AVALIADO, None, com_limite=False, motivo="Re na transição")]
    r = servico._resumo_hidraulico(ausente, c)
    assert r["atendimento"] == servico.ATENDE and r["completude"] == servico.INCOMPLETA
    assert r["lacunas"] == [{"criterio": "dp_t", "motivo": "Re na transição"}]

    indicativa = [_crit("v", servico.ATENDE),
                  _crit("dp_s", servico.SEM_CRITERIO, 5.0, com_limite=False, natureza=servico.ESTIMATIVA_INDICATIVA)]
    assert servico._resumo_hidraulico(indicativa, c)["completude"] == servico.INCOMPLETA

    nada = [_crit("dp_t", servico.SEM_CRITERIO, 10.0, com_limite=False)]
    assert servico._resumo_hidraulico(nada, c)["atendimento"] == servico.NAO_AVALIADO, \
        "sem critério vigente avaliado não há 'atende'"

    reprova = [_crit("v", servico.NAO_ATENDE), _crit("p", servico.ALERTA)]
    assert servico._resumo_hidraulico(reprova, c)["atendimento"] == servico.NAO_ATENDE

    completa = [_crit("v", servico.ATENDE)]
    assert servico._resumo_hidraulico(completa, c)["completude"] == servico.COMPLETA


def test_resumo_da_planta_nao_aprova_ausencias(planta_propostas):
    av = planta_propostas.tag("P-001").operacao.avaliacao()
    hid = av["atendimento_hidraulico"]
    assert "status" not in hid, "um só 'status' misturava atendimento e completude"
    ausentes = {c.num for c in planta_propostas.tag("P-001").operacao.casos
                for k in c.hidraulico["criterios"] if k["valor"] is None and k["obrigatorio"]}
    if ausentes or hid["lacunas"]:
        assert hid["completude"] == servico.INCOMPLETA
        assert "incompleta" in hid["conclusao"]
    for c in planta_propostas.tag("P-001").operacao.casos:
        for k in c.hidraulico["criterios"]:
            assert not (k["status"] == servico.ATENDE and not k["com_limite"]), "valor sem limite 'atendido'"
            if k["valor"] is None:
                assert k["status"] in (servico.NAO_AVALIADO, servico.NAO_APLICAVEL) and k["motivo"]


# ------------------------------------------------------------------ 6. ρ do casco
def test_rho_do_casco_vem_da_corrente_do_casco(planta_propostas):
    rt = planta_propostas.tag("P-001")
    for c in rt.operacao.casos:
        aux = rt.entradas.caso(c.num).auxiliares["rho_casco"]
        assert aux.origem == "propriedade" and aux.fonte.startswith("C-22")
        assert aux.propriedade == "densidade_fase"
        assert c.diagnosticos["rho_casco_kg_m3"] == aux.valor
        crit = {k["criterio"]: k for k in c.hidraulico["criterios"]}
        assert crit["perda_carga_casco"]["natureza"] == servico.ESTIMATIVA_INDICATIVA
        assert crit["perda_carga_tubo"]["natureza"] == servico.CORRELACAO_APLICAVEL
    # não há igualdade implícita entre as correntes: onde a emulsão (tubo) leva água, as ρ diferem
    assert any(c.diagnosticos["rho_casco_kg_m3"] != c.diagnosticos["rho_tubo_kg_m3"] for c in rt.operacao.casos)


def test_velocidade_do_casco_usa_a_rho_do_casco(planta_propostas):
    """v_s = (ṁ_s/n_op)/(ρ_s·S_m): com a mesma S_m, v_s·ρ_s/ṁ_s é constante entre os casos."""
    op = planta_propostas.tag("P-001").operacao
    k = [c.diagnosticos["velocidade_casco_m_s"] * c.diagnosticos["rho_casco_kg_m3"] / c.diagnosticos["vazao_casco_kg_s"]
         for c in op.casos]
    assert max(k) == pytest.approx(min(k), rel=1e-9)


# ------------------------------------------------------------------ 7. premissa de comprimento
class _CasoFalso:
    def __init__(self, valor):
        self.valores = {"l_tubo_max": valor}


def test_premissa_de_comprimento_distingue_default_de_limite_do_projeto():
    cfg = carregar("pfd/p_001_busca.toml")
    dmax = cfg["comprimento_m"]["max"]
    default = Valor(dmax / 2 + cfg["comprimento_m"]["min"] / 2, "metodo", "fonte", "fonte", revisao="pendente")
    pc = servico.premissa_comprimento(_CasoFalso(default), cfg)
    assert pc["natureza"] == "padrao_do_metodo" and not pc["aplicado_na_busca"] and pc["estado"] == "divergente"
    assert pc["explicacao"]
    confirmado = replace(default, revisao="confirmada")
    pc = servico.premissa_comprimento(_CasoFalso(confirmado), cfg)
    assert pc["natureza"] == "limite_do_projeto" and pc["aplicado_na_busca"] and pc["estado"] == "limite_aplicado"
    informado = Valor(dmax, "usuario", "ajustes")
    assert servico.premissa_comprimento(_CasoFalso(informado), cfg)["estado"] == "consistente"


def test_classificacao_e_premissa_usam_o_mesmo_limite(planta_propostas):
    op = planta_propostas.tag("P-001").operacao
    av = op.avaliacao()
    pc = av["premissa_comprimento"]
    crit = next(r for r in av["restricoes_geometricas"] if r["criterio"] == "comprimento_tubo")
    assert crit["limite"] == pc["limite_m"]
    if op.geometria.comprimento_tubo > pc["limite_m"]:
        esperado = servico.NAO_ATENDE if pc["natureza"] == "limite_do_projeto" else servico.DECISAO_PENDENTE
        assert crit["status"] == esperado
    if crit["status"] == servico.DECISAO_PENDENTE:
        assert "comprimento_tubo" in av["decisoes_pendentes"] and "comprimento_tubo" not in av["restricoes"]
        assert crit["motivo"] == pc["explicacao"]


def test_limite_do_projeto_e_aplicado_na_busca(planta_propostas, monkeypatch):
    """Confirmado o l_tubo_max, a busca só vê comprimentos dentro dele (sem rodar a busca)."""
    vistos = []
    def capturar(configuracoes, especificacoes, *a, **k):
        vistos.extend(especificacoes)
        return ()
    monkeypatch.setattr(servico, "buscar_layouts", capturar)
    cfg = carregar("pfd/p_001_busca.toml")
    limite = cfg["comprimento_m"]["min"]
    ctx = servico.Contexto(planta_propostas.dados, balanco=planta_propostas.balanco,
                           propostas=planta_propostas.contexto.propostas)
    estado = replace(servico.estado_inicial("P-001"), geral={"l_tubo_max": limite})
    rt = servico.executar(ctx, estado)
    assert vistos and all(e[1] <= limite for e in vistos)
    pc = rt.operacao.premissa_comprimento
    assert pc["aplicado_na_busca"] and pc["limite_m"] == limite


# ------------------------------------------------------------------ 3–5. memoriais
def test_mc_do_p001_descreve_o_rating_e_nao_um_tag_pendente(planta_propostas):
    ctx, rt = planta_propostas.contexto, planta_propostas.tag("P-001")
    tex = saida_mc.gerar(ctx, rt, "02/10/2026", ("0123456789ab", False))[1]
    metodologia = tex.split("\\section{Metodologia}")[1].split("\\section")[0]
    assert saida_mc.cfg()["textos"]["aguardando"] not in metodologia
    assert "rating" in metodologia and "sizing" in metodologia


def _conferir_continuidade(planta, ident):
    ctx, rt = planta.contexto, planta.tag(ident)
    ct = mc.documento(ctx, rt)["continuidade"]
    assert ct is not None and ct["documento_preliminar"]
    pre = {r.num: r for r in planta.balanco}
    pos = {r.num: r for r in planta.balanco_operacional}
    for li in ct["linhas"]:
        for g, v in zip(ct["grandezas"], li["valores"]):
            ler = (lambda e: e.T[g["id"]]) if g["tipo"] == "temperatura" else (lambda e: e.duties[g["id"]])
            assert (v["pre"], v["pos"]) == (ler(pre[li["num"]]), ler(pos[li["num"]]))
            if g["id"] == "Q_pre":
                assert v["delta"] == pytest.approx(-li["nao_recuperado"])
    assert ct["fechamento"]["atende"]
    return ct, saida_mc.gerar(ctx, rt, "02/10/2026", ("0123456789ab", False))[1]


def test_mc_do_p001_compara_preliminar_e_pos_rating(planta_propostas):
    ct, tex = _conferir_continuidade(planta_propostas, "P-001")
    assert {g["id"] for g in ct["grandezas"]} == {"Q_pre", "C-07", "C-23", "Q_H", "Q_C"}
    assert ct["referencia"]["num"] == planta_propostas.tag("P-001").operacao.caso_projeto
    assert ct["documento_preliminar"] in tex


@pytest.mark.parametrize("ident, carga, corrente", [("P-002", "Q_H", "C-07"), ("P-003", "Q_C", "C-23")])
def test_mc_dos_dependentes_justifica_as_cargas_pos_rating(planta_propostas, ident, carga, corrente):
    ct, tex = _conferir_continuidade(planta_propostas, ident)
    ids = {g["id"] for g in ct["grandezas"]}
    assert {"Q_pre", carga, corrente} <= ids and not ct["proprio"]
    assert "Cargas recebidas após o rating do P-001" in tex
    # a carga do TAG nesta memória é a do estado operacional, e a diferença é explicada pela
    # parcela não recuperada no P-001 (resíduo = ΔQ_TAG − não recuperado)
    i = [g["id"] for g in ct["grandezas"]].index(carga)
    for li in ct["linhas"]:
        v = li["valores"][i]
        assert v["residuo"] == pytest.approx(v["delta"] - li["nao_recuperado"])


def test_tabelas_da_continuidade_cabem_na_largura(planta_propostas):
    """A tabela de 12 colunas saía da moldura: agora no máximo `grandezas_por_tabela` grandezas
    (3 colunas cada) por tabela."""
    ct = mc.documento(planta_propostas.contexto, planta_propostas.tag("P-001"))["continuidade"]
    assert ct["por_tabela"] <= 2


# ------------------------------------------------------------------ gate
def test_gate_reprova_resumo_hidraulico_que_esconde_lacuna(planta_propostas):
    import importlib.util
    from pathlib import Path
    caminho = Path(__file__).resolve().parents[2] / "tools" / "auditar_saida_pfd.py"
    spec = importlib.util.spec_from_file_location("gate", caminho)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    rt = planta_propostas.tag("P-001")
    caso = rt.operacao.casos[0]
    assert not [a for a in gate._conferir_hidraulica(rt, caso) if a["erro"]]
    escondido = replace(caso, hidraulico=dict(caso.hidraulico, completude=servico.COMPLETA))
    assert [a for a in gate._conferir_hidraulica(rt, escondido) if a["erro"]]
    sem_carga = next(c for c in rt.operacao.casos if c.termico["status"] == servico.TERMICO_TETO_NULO)
    descartado = replace(sem_carga, hidraulico=servico._nao_aplicavel("x", _conclusoes()))
    assert [a for a in gate._conferir_hidraulica(rt, descartado) if a["erro"]]
    assert math.isfinite(caso.diagnosticos["rho_casco_kg_m3"])


def test_metodologia_do_template_comum_segue_o_estado_do_tag(planta_propostas):
    """Só TAG aguardando entrada diz que nenhuma equação foi avaliada; TAG dimensionado cujo
    método não declara a forma substituída não pode herdar essa frase."""
    ctx = planta_propostas.contexto
    aguardando = saida_mc.cfg()["textos"]["aguardando"]
    for rt in planta_propostas.tags:
        tex = saida_mc.gerar(ctx, rt, "02/10/2026", ("0123456789ab", False))[1]
        secao = tex.split("\\section{Metodologia}")[1].split("\\section")[0]
        assert (aguardando in secao) == (rt.status == servico.AGUARDANDO), rt.tag.tag
        if rt.etapa_balanco == "apos_rating_P-001":
            assert saida_mc.cfg()["textos"]["modo_automatico_operacional"] in tex, rt.tag.tag
