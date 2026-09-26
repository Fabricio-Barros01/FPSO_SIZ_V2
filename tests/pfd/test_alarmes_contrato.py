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
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar

ARQ = Path(__file__).resolve().parents[2] / "docs" / "propostas" / "pendencias_propostas.toml"


# ------------------------------------------------------------------ contrato de propriedades
def test_contrato_descreve_o_codigo():
    assert contrato.conferir() == []


def test_contrato_cobre_toda_regra_de_propriedade():
    assert sorted(d["regra"] for d in contrato.descritores().values()) == contrato.regras_de_propriedade()


def test_contrato_cita_fonte_existente():
    for nome in contrato.descritores():
        assert all(f.strip() for f in contrato.fonte_de(nome))


# ------------------------------------------------------------------ alarmes
@pytest.fixture(scope="module")
def planta_propostas(planta_base):
    ctx = servico.Contexto(planta_base.dados, balanco=planta_base.balanco,
                           propostas=mod_propostas.carregar(ARQ))
    return dimensionar(contexto=ctx)


@pytest.mark.parametrize("planta", ["planta_base", "planta_propostas"])
def test_todo_tag_inviavel_tem_alarme_anotado(request, planta):
    p = request.getfixturevalue(planta)
    alarmes = inv.alarmes(p)
    assert alarmes, "sem TAG inviável não há o que investigar"
    for rt, ev, reg in alarmes:
        assert reg is not None, f"{rt.tag.tag} inviável sem investigação anotada em alarmes.toml"
        assert reg["hipoteses"] and ev.mensagem
        assert {h["classe"] for h in reg["hipoteses"]} <= set(inv.cfg()["classes"])


def test_variantes_tem_origem_e_existem():
    for a in inv.cfg()["alarme"]:
        for h in a["hipoteses"]:
            for nome in h.get("variantes", []):
                assert inv.variante(nome)["origem"].strip()


def test_sg001_so_os_casos_2_e_3_sao_inviaveis_isolados(planta_base):
    rt = planta_base.tag("SG-001")
    ev = inv.evidencia(rt)
    assert {n[:6] for n, _ in ev.casos_inviaveis} == {"BOT 02", "BOT 03"} and len(ev.casos_viaveis) == 14


def test_trens_em_paralelo_nao_mudam_o_teto(planta_base):
    """O teto de decantação depende da razão de vazões, de µ e de ΔSG, não da vazão: dividir
    por trens reduz o comprimento, não o teto (hipótese de modelo do SG-001)."""
    ctx = planta_base.contexto
    base = planta_base.tag("SG-001").resultado
    for nome in ("trens_2", "trens_3"):
        r = inv.executar_variante(ctx, "SG-001", inv.variante(nome)).resultado
        assert math.isclose(r.ceiling, base.ceiling, rel_tol=1e-12) and r.ceiling_case == base.ceiling_case


def test_variante_de_premissa_nao_toca_o_contexto(planta_base):
    ctx = planta_base.contexto
    antes = dict(ctx.prem)
    r = inv.executar_variante(ctx, "SG-001", inv.variante("eta_80")).resultado
    assert ctx.prem == antes and r.ceiling != planta_base.tag("SG-001").resultado.ceiling


def test_p001_um_passe_leva_ao_limite_de_dittus_boelter(planta_propostas):
    """Cadeia de hipóteses do P-001: com 1 passe o domínio de F deixa de ser o impedimento e
    aparece o da correlação do lado tubo (óleo laminar/transição)."""
    rt = planta_propostas.tag("P-001")
    assert "fator de correção F" in rt.resultado.message
    r = inv.executar_variante(planta_propostas.contexto, "P-001", inv.variante("passes_1"), rt.estado).resultado
    assert not r.feasible and "Dittus-Boelter" in r.message


def test_alarme_no_documento_do_mc(planta_base):
    d = mc.documento(planta_base.contexto, planta_base.tag("SG-001"))
    a = d["alarme"]
    assert a["registrado"] and a["estado"] == "aberta"
    variantes = [v for h in a["hipoteses"] for v in h["variantes"]]
    assert {v["nome"] for v in variantes} == {"eta_80", "eta_90", "trens_2", "trens_3"}
    assert not any(v["viavel"] for v in variantes)
    assert mc.documento(planta_base.contexto, planta_base.tag("V-001"))["alarme"] is None


def test_relatorio_de_alarmes_e_deterministico():
    import importlib.util

    caminho = Path(__file__).resolve().parents[2] / "tools" / "investigar_alarmes.py"
    spec = importlib.util.spec_from_file_location("investigar_alarmes", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    texto = mod.gerar()
    assert texto == mod.gerar()
    for tag in ("SG-001", "P-001", "P-002", "P-003", "B-001", "B-002", "B-003"):
        assert f"| {tag} | inviável (alarme)" in texto
    assert "(diferença 0.0e+00 mm)" in texto
    assert texto == (caminho.parents[1] / "docs" / "validacao" / "14-alarmes.md").read_text(encoding="utf-8")
