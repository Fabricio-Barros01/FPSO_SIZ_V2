"""Gate de sanidade da saída (tools/auditar_saida_pfd.py) e o defeito que ele achou.

O defeito: a grade de varredura de CADA caso é a do caso, e a do envelope é a da união.
Com o mesmo passo e origens diferentes, o x escolhido pelo envelope não existe na
varredura individual, e o MC procurava a linha por igualdade de float — o critério
governante do caso saía vazio e o memorial imprimia um travessão sem justificativa
(P-002: 8 de 10 casos; P-003: 15 de 16). A correção é na origem: o critério vem de
`governing_of` sobre as restrições congeladas do caso, que não depende de grade nenhuma.
"""
import importlib.util
import json
import math
from pathlib import Path

import pytest

from fpso_siz.pfd import memorial as mc

RAIZ = Path(__file__).resolve().parents[2]
TROCADORES = ("P-002", "P-003")


def _identidade_falsa(gate):
    return dict(commit="0" * 12, arvore_suja=False, fpso_siz="0", faltando=[], completa=True,
                casos=dict(arquivo="x", origem="x", sha256="0" * 64, n_casos=0), oleo="vivo",
                propostas="não usadas", topologia="projeto_p46", regra_fwko="eficiencia",
                premissas_alteradas={}, modos_dos_tags={}, versoes_propriedades={})


def _gate():
    spec = importlib.util.spec_from_file_location("auditar_saida_pfd", RAIZ / "tools" / "auditar_saida_pfd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _gate()


@pytest.fixture(scope="module")
def relatorio(gate, planta_propostas, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("auditoria")
    return gate.auditar_planta(planta_propostas.contexto, planta_propostas, pasta)


# ------------------------------------------------------------------ o defeito do P-002/P-003
@pytest.mark.parametrize("ident", TROCADORES)
def test_a_grade_do_caso_nao_contem_o_x_do_envelope(planta_propostas, ident):
    """Sem isto, o teste seguinte não prova nada: é preciso haver caso desalinhado."""
    r = planta_propostas.tag(ident).resultado
    fora = [n for n, pc in zip(r.case_names, r.per_case) if r.x not in {li.x for li in pc.sweep}]
    assert fora, f"{ident}: nenhum caso desalinhado — o teste de regressão ficaria vazio"


@pytest.mark.parametrize("ident", TROCADORES)
def test_todo_caso_do_mc_tem_criterio_governante(planta_propostas, ident):
    rt = planta_propostas.tag(ident)
    doc = mc.documento(planta_propostas.contexto, rt)
    linhas = doc["calculo"]["tabela"]["linhas"]
    assert linhas and all(li["governante"] for li in linhas), \
        [li["caso"] for li in linhas if not li["governante"]]
    assert all(s["governante"] for s in doc["calculo"]["series"]["casos"])


@pytest.mark.parametrize("ident", ("V-001", "SG-001", "P-002", "B-001"))
def test_governante_bate_com_a_varredura_individual_onde_a_grade_contem_o_x(planta_propostas, ident):
    """A correção não mudou rótulo nenhum: onde a busca antiga funcionava, o resultado é o
    mesmo; ela só passou a responder onde antes devolvia vazio."""
    rt = planta_propostas.tag(ident)
    r = rt.resultado
    govs = mc.governantes(rt, r.x)
    conferidos = 0
    for i, pc in enumerate(r.per_case):
        linha = next((li for li in pc.sweep if li.x == r.x), None)
        if linha is None:
            continue
        assert govs[i] == linha.governing
        conferidos += 1
    assert conferidos, f"{ident}: nenhum caso alinhado para conferir a equivalência"


def test_capacidades_batem_com_as_da_varredura_individual(planta_propostas):
    """Mesma origem no diagrama do MC: as capacidades envelopadas vinham da linha da
    varredura de cada caso e agora vêm de `per_constraint` sobre as restrições do caso."""
    rt = planta_propostas.tag("V-001")
    r = rt.resultado
    caps = mc.capacidades(rt, r.x)
    esperado = {}
    for pc in r.per_case:
        linha = next((li for li in pc.sweep if li.x == r.x), None)
        for chave, v in (linha.per_constraint.items() if linha else ()):
            esperado[chave] = max(esperado.get(chave, -math.inf), v)
    assert caps == esperado and caps


# ------------------------------------------------------------------ ausência declarada
def test_vaso_bifasico_declara_o_campo_que_nao_se_aplica(planta_propostas):
    rt = planta_propostas.tag("V-001")
    declarados = rt.entradas.metodo.campos_nao_aplicaveis(rt.resultado)
    assert declarados and all(motivo for motivo in declarados.values())
    doc = mc.documento(planta_propostas.contexto, rt)
    rotulos = {x["rotulo"] for x in doc["calculo"]["resultados"]}
    assert not (rotulos & set(declarados))                       # o MC não imprime o campo vazio
    assert {x["campo"] for x in doc["calculo"]["nao_aplicaveis"]} == set(declarados)


def test_vaso_trifasico_com_teto_nao_declara_nada(planta_propostas):
    rt = planta_propostas.tag("SG-001")
    assert rt.entradas.metodo.campos_nao_aplicaveis(rt.resultado) == {}


def test_o_contrato_nao_declara_nada_por_padrao():
    from fpso_siz.core.contrato import MetodoDimensionamento
    assert MetodoDimensionamento().campos_nao_aplicaveis(None) == {}


# ------------------------------------------------------------------ o gate
def test_a_planta_atual_passa_no_gate(relatorio):
    assert relatorio["aprovada"], relatorio["erros"]
    assert not relatorio["contagem"]["ERRO_NUMERICO"] and not relatorio["contagem"]["ERRO_OUTPUT"]


def test_o_gate_classifica_toda_ausencia(relatorio, gate):
    assert {a["categoria"] for a in relatorio["achados"]} <= set(gate.CATEGORIAS)
    assert all(a["justificativa"] for a in relatorio["achados"])
    assert relatorio["contagem"]["NAO_APLICAVEL"] and relatorio["contagem"]["INVIAVEL"]


def test_o_gate_confere_os_tres_niveis(relatorio, planta_propostas):
    """Se o JSON do núcleo ou o do MC deixassem de reproduzir o motor, o gate reprovaria."""
    assert [t["tag"] for t in relatorio["tags"]] == [t.tag.tag for t in planta_propostas.tags]
    assert all(t["mc_consistente"] for t in relatorio["tags"])


def test_travessao_sem_justificativa_reprova(gate, planta_propostas, tmp_path, monkeypatch):
    """O defeito do P-002 reintroduzido à força: o gate tem de pegá-lo como ERRO_OUTPUT."""
    monkeypatch.setattr(mc, "governantes", lambda rt, x, pares=None: [None] * len(rt.resultado.case_names))
    _, achados = gate.auditar_tag(planta_propostas.contexto, planta_propostas.tag("P-002"), tmp_path)
    perdidos = [a for a in achados if a["caminho"].endswith(".governante")]
    assert perdidos and all(a["categoria"] == "ERRO_OUTPUT" and a["erro"] for a in perdidos)


def test_resultado_principal_nao_finito_reprova(gate, planta_propostas, tmp_path, monkeypatch):
    rt = planta_propostas.tag("V-001")
    m = rt.entradas.metodo
    original = m.result_fields
    from dataclasses import replace as _replace
    monkeypatch.setattr(type(m), "result_fields",
                        lambda self, r: [_replace(f, value=math.nan) if f.highlight else f
                                         for f in original(r)])
    _, achados = gate.auditar_tag(planta_propostas.contexto, rt, tmp_path)
    assert any(a["categoria"] == "ERRO_NUMERICO" and a["erro"] for a in achados)


def test_o_gate_grava_resumo_e_sai_com_codigo(gate, planta_propostas, tmp_path):
    rel = gate.auditar_planta(planta_propostas.contexto, planta_propostas, tmp_path)
    texto = gate.resumo_md(rel)
    assert "APROVADA" in texto and all(t.tag.tag in texto for t in planta_propostas.tags)
    json.dumps(gate.limpar(rel), allow_nan=False)                # resumo.json é JSON estrito
    assert (tmp_path / "P-002.json").is_file() and (tmp_path / "mc").is_dir()


# ------------------------------------------------------------------ identidade da execução
def test_a_identidade_registra_tudo_que_muda_dimensionamento(relatorio, gate, planta_propostas):
    ident = relatorio["identidade"]
    assert ident["completa"] and not ident["faltando"]
    assert set(gate.IDENTIDADE_OBRIGATORIA) <= set(ident)
    assert ident["commit"] and ident["regra_fwko"]
    assert ident["casos"]["sha256"] == planta_propostas.contexto.dados.sha256
    assert ident["oleo"] == "vivo" and ident["topologia"] == "projeto_p46"
    assert ident["propostas"]["sha256"] == planta_propostas.contexto.propostas.sha256
    assert set(ident["modos_dos_tags"]) == {t.tag.tag for t in planta_propostas.tags}
    assert "commit" in gate.resumo_md(relatorio)


def test_identidade_acompanha_as_opcoes(gate, planta_oleo_morto, tmp_path):
    """Trocar a opção troca a identidade: o relatório não pode dizer o que não foi rodado."""
    ident = gate.identidade(planta_oleo_morto.contexto, planta_oleo_morto)
    assert ident["oleo"] == "morto" and ident["propostas"] == "não usadas"


def test_identidade_incompleta_reprova(gate, planta_propostas, tmp_path, monkeypatch):
    """Auditoria que não se sabe de que commit veio não é gate: reprova mesmo sem achado."""
    monkeypatch.setattr(gate.saida_mc, "proveniencia_git", lambda: (None, None))
    rel = gate.auditar_planta(planta_propostas.contexto, planta_propostas, tmp_path)
    assert not rel["aprovada"] and rel["identidade"]["faltando"] == ["commit"] and not rel["erros"]


@pytest.mark.parametrize("resultado,codigo", [(True, 0), (False, 1)])
def test_codigo_de_saida_do_gate(gate, tmp_path, monkeypatch, resultado, codigo):
    """O gate existe para rodar sozinho ao fim de cada fase: erro de aceite tem de sair != 0."""
    falso = dict(casos="x", sha256="0" * 64, tags=[], achados=[], aprovada=resultado,
                 identidade=_identidade_falsa(gate),
                 contagem=dict.fromkeys(gate.CATEGORIAS, 0),
                 erros=[] if resultado else [gate.achado("ERRO_OUTPUT", "c", None, "porque sim") | {"tag": "T"}])
    monkeypatch.setattr(gate, "auditar", lambda *a, **k: falso)
    monkeypatch.setattr(gate.sys, "argv", ["auditar", "--saida", str(tmp_path)])
    assert gate.main() == codigo
    assert (tmp_path / "resumo.md").is_file() and (tmp_path / "resumo.json").is_file()


def test_falha_da_propria_auditoria_sai_com_2(gate, tmp_path, monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("balanço não convergiu")
    monkeypatch.setattr(gate, "auditar", explode)
    monkeypatch.setattr(gate.sys, "argv", ["auditar", "--saida", str(tmp_path)])
    assert gate.main() == 2
