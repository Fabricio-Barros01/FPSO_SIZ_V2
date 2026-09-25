"""F10v — verificação física do balanço (docs/validacao/11-verificacao-balanco.md).

Não muda número: confere, caso a caso, a premissa da fase aquosa (P-42: sem água fictícia;
BSW_saída = min(BSW_entrada; especificação) em cada separador; só o óleo do TO-002 chega à
especificação) e a consistência física do resultado. Os achados de premissa (diluição,
T do FWKO, sal na base do óleo) ficam fixados: se mudarem, o teste acusa."""
import math

import pytest

from fpso_siz.balanco import indicadores
from fpso_siz.balanco.balancos import topologia
from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import COMP

SEM_AGUA = [1, 4, 5, 6, 7]
TOL = 1e-12


@pytest.fixture(scope="module")
def prem(dados):
    return premissas(dados)


@pytest.fixture(scope="module")
def v(resultados, prem):
    return indicadores.verificacao_fisica(resultados, prem)


def test_agua_fecha_e_sai_pela_agua_livre_e_pelo_bsw_do_oleo(v, resultados):
    assert v["sem_fase_aquosa"] == SEM_AGUA  # BOT Tab. 2.2.2.3: BSW nulo (Nota 5: water cut de 0 a 95 %)
    for a in v["agua"]:
        entra = sum(a["entra"].values())
        assert abs(a["residuo"]) <= TOL * max(1, entra) * len(resultados)
        if a["num"] not in SEM_AGUA:
            assert entra > 0 and a["reciclo"] > 0
    assert v["saidas_agua"] == ["C-05", "C-25"]  # água livre do FWKO e BSW do óleo tratado
    assert v["maior_residuo_agua"] < TOL * len(resultados) * max(sum(a["entra"].values()) for a in v["agua"])


def test_sem_agua_ficticia_nos_casos_sem_fase_aquosa(resultados):
    ids = [c["id"] for c in topologia()["correntes"]]
    for r in resultados:
        if r.num in SEM_AGUA:
            assert all(r.streams[s]["W"] == 0 and r.streams[s]["D"] == 0 for s in ids), r.num


def test_bsw_de_cada_separador_e_min_da_entrada_e_da_especificacao(v, resultados, prem):
    assert v["bsw_ok"] and v["fwko_sem_agua_no_oleo"] == []
    por = {(x["bloco"], x["num"]): x for x in v["separadores"]}
    for r in resultados:
        fwko, to1, to2 = por["SG-001", r.num], por["TO-001", r.num], por["TO-002", r.num]
        if r.num in SEM_AGUA:
            assert fwko["saida"] == to1["saida"] == to2["saida"] == 0.0
            continue
        # o FWKO sempre deixa água no óleo; só o TO-002 (último separador) chega à especificação
        assert fwko["saida"] == pytest.approx(min(prem["BSW_F"], r.BSW01), rel=TOL) and fwko["saida"] > prem["BSW_pre"]
        assert to1["saida"] == pytest.approx(prem["BSW_pre"], rel=TOL) and to1["saida"] > prem["BSW_t"]
        assert to2["saida"] == pytest.approx(prem["BSW_t"], rel=TOL)


def test_vazoes_nao_negativas_temperaturas_e_aproximacao(resultados, prem):
    """Vazões ≥ 0 a menos do arredondamento: o gás de C-18 em diante sai de ṁ_G,C16 − ṁ_G,C17,
    que é zero exato na física e −2,2e-16 kg/s no ponto flutuante (≈ 1 ulp) em alguns casos."""
    for r in resultados:
        piso = -TOL * sum(r.streams["C-01"].values())
        assert all(r.streams[s][c] >= piso for s in r.streams for c in COMP), r.num
        assert r.T["C-08"] >= prem["T_trat"]  # BOT 2.7.1.4: tratadores a ≥ 90 °C
        if r.duties["Q_pre"] > 0:  # pré-aquecedor em contracorrente: aproximação ≥ dT_app (P-32)
            quente = r.T["C-22"] - r.T["C-07"]
            fria = r.T["C-23"] - r.T["C-06"]
            assert min(quente, fria) >= prem["dT_app"] - TOL * prem["dT_app"]


def test_sal_do_oleo_tratado_na_base_da_emulsao(v):
    """Decisão do usuário (2026-09-25): o limite de 285 mg/L (BOT 2.3.1.1) vale no volume da
    emulsão. Com o sal real de W e D, todos os casos atendem; na base só do óleo, 15–16
    passariam de 285 (informativo)."""
    assert v["sal_max_emulsao"] <= v["limite_sal"]
    assert v["sal_max_emulsao"] == pytest.approx(284.0006, rel=1e-6)
    acima_na_base_oleo = [x["num"] for x in v["sal_oleo"] if x["oleo"] > v["limite_sal"]]
    assert acima_na_base_oleo == [15, 16]


def test_achados_de_premissa_fixados(v):
    """A3: diluição calculada com S_W para toda a água residual (parte é diluição reciclada,
    sem sal) — superdimensionada, conservadora. A4: FWKO abaixo de 40 °C nos casos 5–6
    (reciclo de óleo da Nota 11 não modelado, P-41). A6: γ do gás além da água de Standing."""
    exc = {x["num"]: x["excesso_rel"] for x in v["diluicao"]}
    assert exc[2] == pytest.approx(0.3668, abs=1e-4) and exc[3] == pytest.approx(exc[2], rel=1e-5)
    assert all(e >= 0 for e in exc.values()) and max(exc, key=exc.get) in (2, 3)
    assert v["abaixo_T_fwko"] == [5, 6] and v["t_fwko_min"] == 40.0
    assert min(v["gamma_gas"].values()) == pytest.approx(0.811, abs=1e-3)
    assert max(v["gamma_gas"].values()) == pytest.approx(1.222, abs=1e-3)


def test_caso_1_igual_ao_oraculo(resultados, oraculo):
    """Nenhum número do balanço muda nesta fase (a paridade completa está em test_paridade)."""
    r1, o1 = resultados[0], oraculo["casos"][0]
    assert r1.num == o1["num"] == 1
    assert {s: dict(c) for s, c in r1.streams.items()} == o1["streams"]
    assert all(math.isclose(r1.T[s], o1["T"][s], rel_tol=0, abs_tol=0) for s in o1["T"])


def test_resumo_mostra_agua_e_alertas(v):
    """O resumo de terminal (relatorio.verificacao_balanco) só apresenta o que o núcleo devolve;
    as falhas aparecem como ATENÇÃO, com os casos."""
    from fpso_siz.output.terminal.estilo import Estilo
    from fpso_siz.output.terminal.relatorio import verificacao_balanco

    texto = "\n".join(verificacao_balanco(v, Estilo(False)))
    assert "sai por C-05, C-25" in texto and "Casos sem fase aquosa: 1, 4, 5, 6, 7" in texto
    assert "em todos os separadores" in texto and "máx. 284,0 mg/L; limite 285 mg/L" in texto
    assert "abaixo de 40 °C nos casos 5, 6" in texto and "ATENÇÃO" not in texto
    falha = dict(v, sem_fase_aquosa=[], bsw_ok=False, separadores=[dict(v["separadores"][0], ok=False)],
                 fwko_sem_agua_no_oleo=[3], sal_oleo=[], abaixo_T_fwko=[])
    texto = "\n".join(verificacao_balanco(falha, Estilo(False)))
    assert "em 1 ponto(s)" in texto and "chegada nos casos 3" in texto
    assert "sem fase aquosa" not in texto and "Sal no óleo" not in texto and "ALERTA" not in texto
