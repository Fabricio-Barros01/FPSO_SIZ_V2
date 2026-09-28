"""F10w — eficiência de água livre do SG-001 (P-43): η_A = máx(η_padrão; η_req), com
η_req = 1 − [BSW_lim/(1 − BSW_lim)]·Q_O,C06/Q_A+D,C03 e BSW_lim = F-06 (BOT 2.7.1.2).

É a regra única do balanço; a fixture de regressão foi congelada pela tabela que o usuário
conferiu em 2026-09-25 (docs/validacao/12-eficiencia-fwko.md)."""
import json
from pathlib import Path

import pytest

from fpso_siz.balanco import indicadores as I
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.propriedades import split_eficiencia

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref"
REGRESSAO = json.loads((FIXTURES / "regressao_eficiencia.json").read_text(encoding="utf-8"))
SEM_AGUA = (1, 4, 5, 6, 7)

# tabela confirmada pelo usuário: caso → (η adotado, exigido acima do padrão, BSW C-06, BSW C-21), em %
TABELA = {2: (85.0, False, 2.39, 0.50), 3: (85.0, False, 2.39, 0.50), 8: (85.0, False, 10.92, 0.50),
          9: (85.0, False, 16.87, 0.50), 10: (85.0, False, 21.15, 0.50), 11: (85.0, False, 34.95, 0.50),
          12: (85.0, False, 34.56, 0.50), 13: (85.0, False, 29.15, 0.50), 14: (85.0, False, 29.15, 0.50),
          15: (92.4, True, 40.00, 0.50), 16: (91.5, True, 40.00, 0.50)}


@pytest.fixture(scope="module")
def prem(dados):
    return premissas(dados)


def test_regressao_bit_a_bit(resultados, dados):
    assert REGRESSAO["proveniencia"]["entrada_sha256"] == dados.sha256
    assert REGRESSAO["premissas"] == premissas(dados)
    for r, e in zip(resultados, REGRESSAO["casos"], strict=True):
        # a fixture foi gerada quando havia duas regras e guarda o rótulo `regra`; ele saiu do
        # estado (há uma regra só), e todo o resto — números e estado do FWKO — é comparado
        assert e["fwko"].get("regra", "eficiencia") == "eficiencia"
        assert r.num == e["num"] and r.fwko == {k: v for k, v in e["fwko"].items() if k != "regra"}
        assert (r.BSW01, r.BSW_F) == (e["BSW01"], e["BSW_F"])
        assert (r.iters, r.residuo_reciclo) == (e["iters"], e["residuo_reciclo"])
        assert r.streams == e["streams"] and r.T == e["T"] and r.duties == e["duties"] and r.gas == e["gas"]


def test_tabela_confirmada_pelo_usuario(resultados):
    for r in resultados:
        fw = r.fwko
        if r.num in SEM_AGUA:  # η nulo, com o estado explícito
            assert fw["eta"] is None and fw["eta_req"] is None and not fw["exigido_acima"]
            assert fw["estado"] == "não aplicável — sem fase aquosa"
            assert I.bsw(r, "C-06") == I.bsw(r, "C-21") == 0.0
            continue
        eta, exigido, b06, b21 = TABELA[r.num]
        assert round(100 * fw["eta"], 1) == eta and fw["exigido_acima"] is exigido
        assert fw["estado"] == ("exigido acima do padrão (BOT 2.7.1.2)" if exigido
                                else "padrão (o limite do BOT não restringe)")
        assert round(100 * I.bsw(r, "C-06"), 2) == b06 and round(100 * I.bsw(r, "C-21"), 2) == b21
        assert fw["eta"] == max(fw["eta_padrao"], fw["eta_req"])
    r15 = resultados[14]
    assert round(r15.fwko["eta_req"], 3) == 0.924  # a substituição numérica do memorial
    assert resultados[1].fwko["eta_req"] < 0  # diagnóstico: o limite não restringe


def test_eta_req_pelas_correntes_do_caso_15(resultados, prem):
    r = resultados[14]
    lim = prem["BSW_F"]
    eta_req = 1 - lim / (1 - lim) * I.q(r, "C-06", "O") / I.q_agua(r, "C-03")
    assert eta_req == pytest.approx(r.fwko["eta_req"], rel=1e-12)
    assert I.bsw(r, "C-06") == pytest.approx(lim, rel=1e-12)


def test_split_eficiencia():
    # sem água: nada a separar; η e η_req não se aplicam
    assert split_eficiencia(100.0, 0.0, 0.85, 0.4, 2.0, 880.0, 8) == (0.0, 0.0, 0.0, None, None)
    # pouca água: η_req < η_padrão (diagnóstico) e vale o padrão
    w_keep, w_rem, oil_w, eta, eta_req = split_eficiencia(100.0, 10.0, 0.85, 0.4, 2.0, 880.0, 8)
    assert eta == 0.85 and eta_req < 0.85 and w_keep + w_rem == pytest.approx(10.0) and w_rem == 8.5
    # muita água: o limite governa e o óleo sai com BSW_lim
    w_keep, w_rem, oil_w, eta, eta_req = split_eficiencia(10.0, 100.0, 0.85, 0.4, 2.0, 880.0, 8)
    o_out = 10.0 - oil_w
    assert eta == eta_req > 0.85 and w_keep / (w_keep + o_out) == pytest.approx(0.4, rel=1e-12)


def test_rastro_e_auditoria_da_eficiencia(resultados, dados, prem):
    for r in resultados:
        p = r.trace.passo("eficiencia_fwko", "SG-001")
        assert p.valor == r.fwko["eta"] and p.entradas["eta_padrao"] == prem["eta_F"]
    ef = {a["id"]: a["max_desvio_abs"] for a in auditar(resultados, dados, prem)}
    assert ef["eficiencia_fwko"] < 1e-12 and ef["massa_global"] < 1e-9


def test_agua_livre_e_conservacao(resultados, prem):
    """Em regime toda a água produzida sai pelo FWKO e pelo BSW do óleo; nenhuma água é
    inventada nos casos sem fase aquosa."""
    v = I.verificacao_fisica(resultados, prem)
    assert v["bsw_ok"] and v["fwko_sem_agua_no_oleo"] == [] and v["sem_fase_aquosa"] == list(SEM_AGUA)
    assert v["maior_residuo_agua"] < 1e-9 and v["sal_max_emulsao"] <= v["limite_sal"]


def test_sensibilidade_da_eficiencia(resultados, dados, prem):
    _, corridas = I.sensibilidade(resultados, dados, prem)
    assert len({rot for _, rot, _ in corridas if "eta_{A" in rot}) == 2
    base = {n: r for n, rot, r in corridas if rot == "Base"}
    for n, rot, r in corridas:
        if "80" in rot and "eta_{A" in rot and not r.fwko["exigido_acima"] and I.q_agua(r, "C-03") > 0:
            assert r.duties["Q_H"] >= base[n].duties["Q_H"]  # menos eficiência → mais água aquecida
