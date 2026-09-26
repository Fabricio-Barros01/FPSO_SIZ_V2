"""F13 — contrato das propriedades de fluido e alarmes de inviabilidade.

A unidade do BOT é um projeto básico real: TAG inviável é alarme (premissa, numérico ou
modelo) e tem de estar anotado e investigado; a variante roda pelo mesmo motor e não muda
o resultado padrão."""
import math
from pathlib import Path

import pytest

from fpso_siz.pfd import contrato, investigacao as inv
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as mc



# ------------------------------------------------------------------ contrato de propriedades
def test_contrato_descreve_o_codigo():
    assert contrato.conferir() == []


def test_contrato_cobre_toda_regra_de_propriedade():
    assert sorted(d["regra"] for d in contrato.descritores().values()) == contrato.regras_de_propriedade()


def test_contrato_cita_fonte_existente():
    for nome in contrato.descritores():
        assert all(f.strip() for f in contrato.fonte_de(nome))


# ------------------------------------------------------------------ alarmes
@pytest.mark.parametrize("planta", ["planta_base", "planta_oleo_morto", "planta_propostas"])
def test_todo_tag_inviavel_tem_alarme_anotado(request, planta):
    p = request.getfixturevalue(planta)
    alarmes = inv.alarmes(p)
    for rt, ev, reg in alarmes:
        assert reg is not None, f"{rt.tag.tag} inviável sem investigação anotada em alarmes.toml"
        assert reg["hipoteses"] and ev.mensagem
        assert {h["classe"] for h in reg["hipoteses"]} <= set(inv.cfg()["classes"])


def test_variantes_tem_origem_e_existem():
    for a in inv.cfg()["alarme"]:
        for h in a["hipoteses"]:
            for nome in h.get("variantes", []):
                assert inv.variante(nome)["origem"].strip()


def test_sg001_so_os_casos_2_e_3_sao_inviaveis_isolados(planta_oleo_morto):
    rt = planta_oleo_morto.tag("SG-001")
    ev = inv.evidencia(rt)
    assert {n[:6] for n, _ in ev.casos_inviaveis} == {"BOT 02", "BOT 03"} and len(ev.casos_viaveis) == 14


def test_oleo_vivo_explica_o_alarme_do_sg001(planta_base, planta_oleo_morto):
    """Hipótese de premissa confirmada: com a viscosidade de óleo vivo o teto de decantação
    dos casos 2 e 3 sobe (h_o ∝ 1/µ_o) e o SG-001 tem solução; os outros TAGs sem óleo vivo
    no critério não mudam de estado."""
    vivo, morto = planta_base.tag("SG-001"), planta_oleo_morto.tag("SG-001")
    assert morto.status == "inviavel" and vivo.status == "dimensionado"
    assert vivo.resultado.ceiling > vivo.resultado.x > morto.resultado.ceiling
    assert not inv.alarmes(planta_base)
    assert {t.tag.tag for t, _, _ in inv.alarmes(planta_oleo_morto)} == {"SG-001"}
    assert inv.registro("SG-001")["estado"] == "explicada"


def test_trens_em_paralelo_nao_mudam_o_teto(planta_oleo_morto):
    """O teto de decantação depende da razão de vazões, de µ e de ΔSG, não da vazão: dividir
    por trens reduz o comprimento, não o teto (hipótese de modelo do SG-001)."""
    ctx = planta_oleo_morto.contexto
    base = planta_oleo_morto.tag("SG-001").resultado
    for nome in ("trens_2", "trens_3"):
        r = inv.executar_variante(ctx, "SG-001", inv.variante(nome)).resultado
        assert math.isclose(r.ceiling, base.ceiling, rel_tol=1e-12) and r.ceiling_case == base.ceiling_case


def test_variante_de_premissa_nao_toca_o_contexto(planta_base):
    ctx = planta_base.contexto
    antes = dict(ctx.prem)
    r = inv.executar_variante(ctx, "SG-001", inv.variante("eta_80")).resultado
    assert ctx.prem == antes and r.ceiling != planta_base.tag("SG-001").resultado.ceiling


def test_variante_de_premissa_herda_o_modo_do_oleo(planta_oleo_morto, planta_base):
    """O contexto novo da variante mantém a viscosidade do contexto original: com óleo morto a
    variante η = 0,80 segue inviável e com teto abaixo do diâmetro do caso com óleo vivo."""
    rt = inv.executar_variante(planta_oleo_morto.contexto, "SG-001", inv.variante("eta_80"))
    assert rt.status == "inviavel" and rt.resultado.ceiling < planta_base.tag("SG-001").resultado.x


def test_p001_um_passe_leva_ao_limite_de_dittus_boelter(planta_propostas):
    """Cadeia de hipóteses do P-001: com 1 passe o domínio de F deixa de ser o impedimento e
    aparece o da correlação do lado tubo (óleo laminar/transição)."""
    rt = planta_propostas.tag("P-001")
    assert "fator de correção F" in rt.resultado.message
    r = inv.executar_variante(planta_propostas.contexto, "P-001", inv.variante("passes_1"), rt.estado).resultado
    assert not r.feasible and "Dittus-Boelter" in r.message


def test_alarme_no_documento_do_mc(planta_base, planta_oleo_morto):
    d = mc.documento(planta_oleo_morto.contexto, planta_oleo_morto.tag("SG-001"))
    a = d["alarme"]
    assert a["registrado"] and a["estado"] == "explicada"
    variantes = [v for h in a["hipoteses"] for v in h["variantes"]]
    assert {v["nome"] for v in variantes} == {"eta_80", "eta_90", "trens_2", "trens_3"}
    assert not any(v["viavel"] for v in variantes)
    assert mc.documento(planta_base.contexto, planta_base.tag("V-001"))["alarme"] is None
    assert mc.documento(planta_base.contexto, planta_base.tag("SG-001"))["alarme"] is None


def test_relatorio_de_alarmes_e_deterministico():
    import importlib.util

    caminho = Path(__file__).resolve().parents[2] / "tools" / "investigar_alarmes.py"
    spec = importlib.util.spec_from_file_location("investigar_alarmes", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    texto = mod.gerar()
    assert texto == mod.gerar()
    for tag in ("SG-001", "P-001", "P-002", "P-003"):
        assert f"| {tag} | inviável (alarme)" in texto
    assert "| B-001 | DN 600 mm" in texto and "Estudo da P-44" in texto
    assert "(diferença 0.0e+00 mm)" in texto
    assert texto == (caminho.parents[1] / "docs" / "validacao" / "14-alarmes.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ P-44 (F10x.6)
def test_p44_resolve_as_bombas(planta_propostas):
    """Com a P-44 as três bombas têm linha: DN pelo caso de maior vazão, com a banda nele; os
    demais casos abaixo do teto. Sem ela (variante sem_p44), o alarme anterior volta."""
    ctx = planta_propostas.contexto
    esperado = {"B-001": 600.0, "B-002": 250.0, "B-003": 125.0}
    for ident, dn in esperado.items():
        rt = planta_propostas.tag(ident)
        assert rt.status == "dimensionado" and rt.resultado.x == dn
        op = mc.documento(ctx, rt)["calculo"]["series"]["operacao"]
        projeto = [o for o in op if o["papel"] == "projeto"]
        assert len(projeto) == 1 and projeto[0]["q"] == max(o["q"] for o in op)
        casos = rt.entradas.casos
        v_min = next(c.valores["v_min"].valor for c in casos if c.ativo)
        assert v_min <= projeto[0]["v"] <= next(c.valores["v_max"].valor for c in casos if c.ativo)
        assert all(o["v"] <= projeto[0]["v"] for o in op)
        assert inv.executar_variante(ctx, ident, inv.variante("sem_p44")).status == "inviavel"
        assert inv.registro(ident)["estado"] == "explicada"


def test_p44_piso_nulo_so_no_oleo_limpo(planta_propostas):
    for ident, v_min in (("B-001", 0.0), ("B-002", 1.0), ("B-003", 1.0)):
        c = next(c for c in planta_propostas.tag(ident).entradas.casos if c.ativo)
        assert c.valores["v_min"].valor == v_min
        assert c.valores["piso_caso_projeto"].valor == 1.0 and c.valores["transicao_turndown"].valor == 1.0
        assert all("P-44" in c.valores[k].fonte for k in ("piso_caso_projeto", "transicao_turndown"))
    c = next(c for c in planta_propostas.tag("B-001").entradas.casos if c.ativo)
    assert c.valores["v_min"].origem == "recomendada" and "P-44" in c.valores["v_min"].fonte


def test_p44b_so_no_caso_6_do_b001(planta_propostas):
    """A política de transição (P-44b) só entra no turndown mais profundo (caso 6, ~4 % da vazão de projeto)."""
    op = mc.documento(planta_propostas.contexto, planta_propostas.tag("B-001"))["calculo"]["series"]["operacao"]
    assert [o["caso"][:6] for o in op if o["politica_transicao"]] == ["BOT 06"]
    assert all(not o["politica_transicao"] for o in op if o["papel"] == "projeto")


# ------------------------------------------------------------------ topologia (F13.2 → P-46, F10x.7)
@pytest.mark.parametrize("ident", ["P-002", "P-003"])
def test_p46_oleo_no_casco_e_a_base_e_o_julia_fica_na_paridade(planta_propostas, ident):
    """P-46: na planta, o óleo vai no casco e a água nos tubos; a alocação do PFD F1 (óleo no
    tubo) é a topologia de paridade. As duas fecham a mesma carga do balanço."""
    from fpso_siz.pfd.tags import tag, topologia_alternativa
    t = tag(ident)
    julia = topologia_alternativa(t.topologia_julia)
    assert t.entradas["m_tubo"]["regra"] == "vazao_utilidade" and julia.entradas["m_casco"]["regra"] == "vazao_utilidade"
    ctx_j = servico.Contexto(planta_propostas.dados, balanco=planta_propostas.balanco, topologia_julia=True,
                             propostas=planta_propostas.contexto.propostas)
    rt_j = servico.executar(ctx_j, servico.estado_inicial(ident))
    rt = planta_propostas.tag(ident)
    for cj, cb in zip(rt_j.entradas.casos, rt.entradas.casos, strict=True):
        if cb.ativo:
            assert math.isclose(cb.valores["m_tubo"].valor, cj.valores["m_casco"].valor, rel_tol=1e-12)
            assert cb.valores["m_casco"].valor == cj.valores["m_tubo"].valor
            assert "IAPWS" in cb.valores["rho_tubo"].fonte
    # as propostas seguem a topologia-base: na do Julia o k do óleo (agora no tubo) fica lacuna
    assert rt_j.resultado is None and [lac.chave for lac in rt_j.entradas.lacunas] == ["k_tubo"]


def test_topologia_de_outro_tag_e_recusada(planta_propostas):
    v = {"rotulo": "teste", "topologia": "p_002_oleo_tubo", "origem": "teste"}
    with pytest.raises(ValueError, match="topologia de P-002"):
        inv.executar_variante(planta_propostas.contexto, "P-003", v)


def test_p001_emulsao_no_casco_segue_sem_correlacao(planta_propostas):
    """Óleo/óleo: trocar os lados não tira o óleo laminar do tubo (Re < 10⁴ com 1 passe)."""
    ctx = planta_propostas.contexto
    v = dict(inv.variante("p_001_emulsao_casco"))
    assert "fator de correção F" in inv.executar_variante(ctx, "P-001", v).resultado.message
    v["geral"] = {"passes_tubo": 1.0}
    assert "Dittus-Boelter" in inv.executar_variante(ctx, "P-001", v).resultado.message
