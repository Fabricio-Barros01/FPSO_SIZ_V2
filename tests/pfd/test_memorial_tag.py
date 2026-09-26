"""F11 — memorial de cálculo (MC) por TAG: numeração, conteúdo do núcleo, determinismo,
exportação dos CSV e igualdade PDF × JSON (compilação com `-m latex`)."""
import json
import math
import re
import shutil
import subprocess
from dataclasses import asdict

import pytest

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.trace import Rastro, TraceEntry
from fpso_siz.output.latex import compilacao, formatacao
from fpso_siz.output.latex.tag import memorial as saida_mc
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd.tags import tags

DATA = "26/09/2026"
GIT = ("0123456789ab", False)   # proveniência fixada: os bytes não dependem do checkout


def test_numeracao_cobre_os_11_tags_sem_repeticao():
    tab = carregar("memorial_tag.toml")["numeracao"]
    assert set(tab) == {t.tag for t in tags()}
    assert sorted(tab.values()) == list(range(1, len(tab) + 1))
    assert [k for k, _ in sorted(tab.items(), key=lambda kv: kv[1])][:3] == ["SG-001", "P-001", "P-002"]
    assert mc.numero("V-001") == (4, "MC-SEN-SEP-EQP-004-0")
    assert mc.numero("nao-e-tag") == (None, None)


def test_rastro_documental_nao_muda_a_projecao():
    """Os operandos ficam fora de `entries`: a projeção (JSON, fixtures do Julia) é a mesma."""
    tr = Rastro()
    tr.anotar("gas", "V_t", coef=1.0)
    tr.iteracoes["gas"] = [{"i": 1}]
    tr.trace("gas", "Eq.", "V_t", "f", 2.0, "m/s")
    assert [asdict(e) for e in tr] == [asdict(TraceEntry("gas", "Eq.", "V_t", "f", 2.0, "m/s"))]
    assert tr.operandos[("gas", "V_t")] == {"coef": 1.0}


@pytest.fixture(scope="module")
def docs(planta_base):
    ctx = planta_base.contexto
    return {t.tag.tag: (t, mc.documento(ctx, t)) for t in planta_base.tags}


def test_documento_de_cada_tag_tem_as_secoes(docs):
    for tag, (rt, d) in docs.items():
        assert d["identificacao"]["numero"] == mc.numero(tag)[1]
        assert d["identificacao"]["status"] == rt.status
        assert d["conteudo"]["objetivo"] and d["conteudo"]["referencias"]
        assert [c["num"] for c in d["casos"]] == list(range(1, 17))
        assert (d["calculo"] is None) == (rt.resultado is None)


def test_lacunas_do_mc_batem_com_as_do_pfd(docs):
    for rt, d in docs.values():
        assert [(l["chave"], tuple(l["casos"])) for l in d["lacunas"]] == \
            [(l.chave, l.casos) for l in rt.entradas.lacunas]
        assert all(l["origem_esperada"] for l in d["lacunas"])


def test_regra_do_fwko_e_p43_no_mc(docs):
    _, d = docs["V-001"]
    assert d["identificacao"]["regra_fwko"] == "eficiencia"
    assert "P-43" in [p["id"] for p in d["premissas"]]
    _, sg = docs["SG-001"]
    assert "P-42" in [p["id"] for p in sg["premissas"]]


def test_tex_deterministico_e_sem_numero_de_dado_digitado(planta_base, tmp_path):
    ctx = planta_base.contexto
    rt = planta_base.tag("V-001")
    a = saida_mc.gravar(ctx, rt, tmp_path / "a", data=DATA, git=GIT)
    b = saida_mc.gravar(ctx, rt, tmp_path / "b", data=DATA, git=GIT)
    assert a.read_bytes() == b.read_bytes()
    for arq in (tmp_path / "a").glob("*.csv"):
        assert arq.read_bytes() == (tmp_path / "b" / arq.name).read_bytes()
    tex = a.read_text(encoding="utf-8")
    # os gráficos leem CSV: o d escolhido não aparece em nenhum \addplot
    assert all(".csv}" in li for li in tex.splitlines() if li.startswith(r"\addplot") and "fill between" not in li)
    assert "MC-SEN-SEP-EQP-004-0_diagrama.csv" in tex


def test_csv_do_diagrama_contem_o_ponto_escolhido(planta_base, tmp_path):
    rt = planta_base.tag("V-001")
    saida_mc.gravar(planta_base.contexto, rt, tmp_path, data=DATA, git=GIT)
    linhas = (tmp_path / "MC-SEN-SEP-EQP-004-0_diagrama.csv").read_text(encoding="utf-8").splitlines()
    cab = linhas[0].split(",")
    assert cab[:2] == ["x", "y"] and "banda_min" in cab and "cap_gas" in cab
    ponto = (tmp_path / "MC-SEN-SEP-EQP-004-0_ponto.csv").read_text(encoding="utf-8").splitlines()[1]
    assert ponto == f"{rt.resultado.x!r},{rt.resultado.y!r}"


def test_formatacao_4_algarismos():
    assert formatacao.sig(4700.0) == "4.700"
    assert formatacao.sig(11.743162292078477) == "11{,}74"
    assert formatacao.sig(259406455.03) == r"2{,}594\times10^{8}"
    assert formatacao.sig(9999.6) == r"1{,}000\times10^{4}"
    assert formatacao.sig(math.nan) == r"\text{--}" and formatacao.sig(0.0) == "0"
    assert formatacao.texto_sig(0.0036) == "3,600×10-3"
    assert formatacao.tx("a^b_c {x} 5%") == r"a\^{}b\_c \{x\} 5\%"
    assert formatacao.unid("kg/m^3") == "kg/m³" and formatacao.unid("–") == ""


def test_substituicao_nao_inventa_operando():
    assert saida_mc.substituir(r"@a@\cdot @k:c@", {"a": 2.0}, {"a": "m"}, {"c": 0.5}) == r"2{,}000\,\text{m}\cdot 0{,}5"
    with pytest.raises(KeyError):
        saida_mc.substituir("@falta@", {})


# ------------------------------------------------------------------ compilação (lento)
def _texto_pdf(pdf):
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def _normal(s):
    return re.sub(r"\s+", "", s).replace("−", "-")


@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel() or not shutil.which("pdftotext"), reason="latexmk/pdftotext ausentes")
@pytest.mark.parametrize("ident", [t.tag for t in tags()])
def test_pdf_compila_e_iguala_o_json(planta_base, tmp_path, ident):
    """PDF × JSON: o cartão de resultados e o teto exportados no JSON do TAG aparecem no
    PDF com a regra de 4 algarismos; as lacunas aparecem pela chave."""
    from fpso_siz.output.pfd import estrutura_tag

    ctx, rt = planta_base.contexto, planta_base.tag(ident)
    pdf = compilacao.compilar(saida_mc.gravar(ctx, rt, tmp_path, data=DATA, git=GIT))
    texto = _normal(_texto_pdf(pdf))
    js = estrutura_tag(ctx, rt)
    doc = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    assert doc["identificacao"]["numero"] in texto
    if js["envelope"] is not None:
        for campo in js["envelope"]["resultado"]["cartao"]:
            if isinstance(campo["valor"], float):
                assert _normal(formatacao.texto_sig(campo["valor"])) in texto, campo
    for lac in js["lacunas"]:
        assert _normal(lac["chave"]) in texto


# ------------------------------------------------------------------ F11.2 — V-001
def test_v001_caso_governante_e_resultado(docs):
    rt, d = docs["V-001"]
    c = d["calculo"]
    assert c["caso_governante"] == "BOT 03 — Early Life Blend" == rt.resultado.driver_case
    assert c["viavel"] and c["selecao"]["d"] == rt.resultado.x == 4700.0
    assert c["selecao"]["leff"] == rt.resultado.y
    assert [e["id"] for e in c["equacoes"]] == ["cd", "vt", "re", "k", "gas", "liquido", "leff", "lss", "sr", "volume"]
    assert all(x["atende"] for x in c["criterios"])


@pytest.mark.parametrize("ident", ["V-001", "V-002"])
def test_knockout_conta_a_mao_reproduz_o_rastro(docs, ident):
    """O passo a passo refeito à mão, só com os operandos impressos no MC (valores
    completos), dá o resultado do rastro."""
    _, d = docs[ident]
    eq = {e["id"]: e for e in d["calculo"]["equacoes"]}
    o = eq["cd"]["operandos"]
    assert o["cd_entrada"] + o["relaxacao"] * (o["a"] / o["re"] + o["b"] / math.sqrt(o["re"]) + o["c"]
                                               - o["cd_entrada"]) == eq["cd"]["resultado"]
    o = eq["vt"]["operandos"]
    assert o["coef"] * math.sqrt(((o["rho_l"] - o["rho_g"]) / o["rho_g"]) * (o["dm"] / o["cd"])) == eq["vt"]["resultado"]
    o = eq["re"]["operandos"]
    assert o["coef"] * o["rho_g"] * o["dm"] * o["vt"] / o["mu_g"] == eq["re"]["resultado"]
    o = eq["k"]["operandos"]
    assert math.sqrt((o["rho_g"] / (o["rho_l"] - o["rho_g"])) * (o["cd"] / o["dm"])) == eq["k"]["resultado"]
    o = eq["gas"]["operandos"]
    assert o["coef"] * (o["t_k"] * o["z"] * o["q_g"] / o["p_kpa"]) * o["k"] == eq["gas"]["resultado"]
    o = eq["liquido"]["operandos"]
    assert o["coef"] * o["tr"] * o["q_l"] == eq["liquido"]["resultado"]
    s = d["calculo"]["selecao"]
    assert s["dleff_gas"] == eq["gas"]["resultado"] and s["d2leff_liq"] == eq["liquido"]["resultado"]
    assert max(s["dleff_gas"] / s["d"], s["d2leff_liq"] / (s["d"] * s["d"])) == s["leff"]
    assert max(s["leff"] + s["d"] / 1000, s["fator"] * s["leff"]) == s["lss"]
    assert s["lss"] / (s["d"] / 1000) == s["sr"]
    assert math.isclose(math.pi * (s["d"] / 1000) ** 2 * s["lss"] / 4, s["volume"], rel_tol=1e-15)
    if ident != "V-001":
        return
    # números do cartão em 4 algarismos (o que o leitor confere no PDF)
    assert [formatacao.texto_sig(s[k]) for k in ("leff", "lss", "sr", "volume")] == ["11,74", "16,44", "3,499", "285,3"]


def test_v001_constantes_de_campo_convertidas(docs):
    _, d = docs["V-001"]
    conv = {e["id"]: e["conversao"] for e in d["calculo"]["equacoes"] if e["conversao"]}
    assert set(conv) == {"vt", "gas", "liquido"}
    assert math.isclose(conv["vt"]["convertido"], 0.0119 * 0.3048)
    assert math.isclose(conv["liquido"]["convertido"], 42406.573, rel_tol=1e-8)
    assert abs(conv["liquido"]["desvio"]) < 1e-3 < abs(conv["gas"]["desvio"])   # 0,08 % × 0,86 %


# ------------------------------------------------------------------ F11.3 — V-002 e SG-001
def test_v002_governante_e_ponto(docs):
    rt, d = docs["V-002"]
    c = d["calculo"]
    assert c["caso_governante"] == rt.resultado.driver_case and c["selecao"]["d"] == rt.resultado.x
    assert formatacao.texto_sig(c["selecao"]["sr"]) == formatacao.texto_sig(rt.resultado.derivados["sr"])


def test_sg001_diagnostico_sem_intersecao(docs):
    rt, d = docs["SG-001"]
    c = d["calculo"]
    assert rt.status == "inviavel" and not c["viavel"] and c["selecao"] is None
    diag = c["diagnostico"]
    assert diag["caso_teto"] == "BOT 02 — Early Life" == c["caso_governante"]
    assert diag["teto"] == rt.resultado.ceiling and formatacao.texto_sig(diag["teto"]) == "3.612"
    assert diag["x_min_banda"] > diag["teto"]           # por isso não há interseção
    assert [x["atende"] for x in c["criterios"]] == [False, False]
    s = c["series"]
    assert s["teto"][0]["x"] == diag["teto"] and s["minimo"][0]["x"] == diag["x_min_banda"]
    abaixo = [li for li in s["diagrama"] if li["x"] <= diag["teto"]]
    assert abaixo and not any(li["banda_min"] <= li["y"] <= li["banda_max"] for li in abaixo)
    assert "ponto" not in s


def test_sg001_conta_a_mao_da_decantacao(docs):
    _, d = docs["SG-001"]
    eq = {e["id"]: e for e in d["calculo"]["equacoes"]}
    o = eq["ho"]["operandos"]
    assert o["coef"] * o["tr_o"] * o["dsg"] * (o["dm"] * o["dm"]) / o["mu_o"] == eq["ho"]["resultado"]
    o = eq["dsg"]["operandos"]
    assert o["sg_w"] - o["sg_o"] == eq["dsg"]["resultado"]
    o = eq["dmax_wio"]["operandos"]
    assert o["h"] / o["beta"] == eq["dmax_wio"]["resultado"] == d["calculo"]["diagnostico"]["teto"]
    o = eq["liquido"]["operandos"]
    assert o["coef"] * (o["tr_o"] * o["q_o"] + o["tr_w"] * o["q_w"]) == eq["liquido"]["resultado"]


@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel() or not shutil.which("pdftotext"), reason="latexmk/pdftotext ausentes")
def test_sg001_pdf_mostra_a_inviabilidade(planta_base, tmp_path):
    ctx, rt = planta_base.contexto, planta_base.tag("SG-001")
    tex = saida_mc.gravar(ctx, rt, tmp_path, data=DATA, git=GIT)
    texto = _normal(_texto_pdf(compilacao.compilar(tex)))
    assert _normal("MEMORIAL DE CÁLCULO – DIAGNÓSTICO") in texto
    assert _normal("não atende") in texto and "3.612mm" in texto and "5.600mm" in texto
    assert (tmp_path / "MC-SEN-SEP-EQP-001-0_teto.csv").exists()
    assert (tmp_path / "MC-SEN-SEP-EQP-001-0_minimo.csv").exists()


# ------------------------------------------------------------------ F11.4 — aguardando entrada
AGUARDANDO = ["TO-001", "TO-002", "P-001", "P-002", "P-003", "B-001", "B-002", "B-003"]


@pytest.mark.parametrize("ident", AGUARDANDO)
def test_aguardando_entrada_tem_lacunas_do_pfd_e_metodologia(planta_base, docs, ident):
    from fpso_siz.output.pfd import estrutura_tag

    rt, d = docs[ident]
    assert rt.status == "aguardando_entrada" and d["calculo"] is None
    js = estrutura_tag(planta_base.contexto, rt)
    assert [(l["chave"], l["casos"]) for l in d["lacunas"]] == [(l["chave"], l["casos"]) for l in js["lacunas"]]
    assert d["pendencias"]["lacunas"] == [l["chave"] for l in js["lacunas"]]
    assert d["conteudo"]["metodologia"]
    _, tpl = saida_mc.contexto(planta_base.contexto, rt, DATA, GIT)
    assert tpl["status"] == "aguardando" and all("@" not in m["latex"] for m in tpl["metodologia"])


def test_mc_com_ajustes_sinteticos_cobre_todos_os_metodos(planta_ajustada):
    """Com as entradas sintéticas dos testes os 11 TAGs dimensionam: o MC de cada método sai
    do mesmo gerador (métodos sem substituição declarada mostram o rastro do caso)."""
    ctx = planta_ajustada.contexto
    for rt in planta_ajustada.tags:
        d = mc.documento(ctx, rt)
        c = d["calculo"]
        assert c["viavel"] and c["rastro"] and c["resultados"]
        if c["selecao"]:
            s = c["selecao"]
            assert s["lss"] in (s["lss_gas"], s["lss_liq"]) or s["lss"] == max(s["lss_gas"], s["lss_liq"])
        saida_mc.gerar(ctx, rt, DATA, GIT)


@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel(), reason="latexmk ausente")
@pytest.mark.parametrize("ident", ["SG-001", "TO-001", "P-001", "B-001", "B-002", "P-003"])
def test_mc_com_ajustes_sinteticos_compila(planta_ajustada, tmp_path, ident):
    rt = planta_ajustada.tag(ident)
    assert compilacao.compilar(saida_mc.gravar(planta_ajustada.contexto, rt, tmp_path, data=DATA, git=GIT)).exists()


# ------------------------------------------------------------------ F10x.1 — gráficos de trocador e bomba
@pytest.mark.parametrize("ident", ["P-001", "P-002", "P-003"])
def test_trocador_perfil_tq_e_parcelas_de_u(planta_ajustada, ident):
    """Com as entradas sintéticas dos testes: o perfil T × Q liga as temperaturas terminais do
    caso governante e as parcelas de 1/U somam exatamente o 1/U do dimensionamento."""
    rt = planta_ajustada.tag(ident)
    d = mc.documento(planta_ajustada.contexto, rt)
    s = d["calculo"]["series"]
    i = mc.indice_governante(rt.resultado)
    entrada, cons = mc.restricoes(rt)[i]
    perfil = s["perfil_tq"]
    assert [p["t_tubo"] for p in perfil] == [entrada.t_tubo_in, entrada.t_tubo_out]
    assert perfil[-1]["t_casco"] == entrada.t_casco_in and perfil[0]["t_casco"] == cons.t_casco_out
    assert perfil[-1]["q_kw"] == cons.q / 1000
    assert math.isclose(sum(x["r"] for x in s["resistencias"]), 1 / s["u"], rel_tol=1e-15)
    assert s["u"] == rt.resultado.derivados["u"]
    assert math.isclose(sum(x["fracao"] for x in s["resistencias"]), 1.0, rel_tol=1e-12)


@pytest.mark.parametrize("ident", ["B-001", "B-002", "B-003"])
def test_bomba_curva_do_sistema_e_npsh(planta_ajustada, ident):
    rt = planta_ajustada.tag(ident)
    r = rt.resultado
    s = mc.documento(planta_ajustada.contexto, rt)["calculo"]["series"]
    i = mc.indice_governante(r)
    curva = s["curva_sistema"]
    assert curva[0]["q"] == 0 and curva[0]["h"] == curva[0]["h_est"]          # sem vazão, só a estática
    fr = carregar("memorial_tag.toml")["graficos"]["fracoes_vazao"]
    projeto = curva[fr.index(1.0)]
    assert projeto["q"] == s["ponto_bomba"][0]["q"] and projeto["h"] == s["ponto_bomba"][0]["h"]
    assert s["ponto_bomba"][0]["h"] == r.y - r.slack[i]                        # a exigência do caso no DN
    hs = [p["h"] for p in curva if math.isfinite(p["h"])]
    assert hs == sorted(hs)                                                    # H cresce com Q
    assert len(s["npsh"]) == len(r.case_names)
    assert all(x["npsh_disponivel"] >= x["npsh_exigido"] for x in s["npsh"])  # DN admissível em todo caso
