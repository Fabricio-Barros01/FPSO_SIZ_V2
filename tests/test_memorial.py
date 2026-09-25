"""F4 — memorial LaTeX do balanço: paridade, robustez a dados/premissas, bijeção e compilação."""
import contextlib
import difflib
import importlib.util
import io
import json
import re
import shutil
import sys
import tomllib
import warnings
from importlib.resources import files
from pathlib import Path

import pytest

from fpso_siz.balanco import indicadores
from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.cli import main
from fpso_siz.core.configuracao import carregar
from fpso_siz.output.latex import compilacao, formatacao
from fpso_siz.output.latex.balanco import memorial

RAIZ = Path(__file__).resolve().parents[1]
FIX = RAIZ / "tests" / "fixtures" / "python_ref"
CASOS = FIX / "design_cases_bot.json"
SCRIPT = RAIZ / "references" / "Balanço_Preliminar.py"
precisa_script = pytest.mark.skipif(not SCRIPT.exists(), reason="acervo local references/ ausente")

# Linhas em que o script original escrevia um literal fixo (2.500, 0,01/0,99, 285, 240.000,
# ΔT_app = 10, 40 °C...) que aqui acompanha o dado/premissa. Só elas podem diferir do
# original quando dados ou premissas mudam; qualquer outra diferença é número esquecido.
LITERAIS_DO_ORIGINAL = [re.compile(p) for p in (
    r"F-02 & Pressão do FWKO", r"\\item O fluido de poço \(C-01\) recebe", r"\\paragraph\{Premissas:\} P-06, P-14",
    r"\\paragraph\{Saídas:\} C-03 multifásica", r"\\paragraph\{Entradas:\} C-03 \(Caso", r"Caso \d+ \(\$\\gamma_g",
    r"\\emph\{\(iii\) Óleo na água\}", r"\\paragraph\{Saídas:\} C-04 gás", r"\\paragraph\{Validação recomendada em etapa posterior:\} flash",
    r"\\paragraph\{Entradas:\} lado frio", r"\\paragraph\{Premissas:\} P-14, P-17, P-32", r"Caso \d+: \$\\dot C_\{C06\}",
    r"T_\{C08\}=\\max\(", r"Caso \d+: \$Q_\{A\+D,C11\}", r"\\paragraph\{Saídas:\} C-11 óleo úmido",
    r"\\paragraph\{Modelo de cálculo:\} balanço de sal", r"S_\{\\mathrm\{res\}\}\\le", r"Q_D=", r"\\dot Q_\{\\mbox\{DWH-001\}\}=",
    r"Q_\{A\+D,C21\}=\\min", r"Salinidade resultante", r"\\paragraph\{Premissas:\} P-21, P-34, P-36",
    r"\\paragraph\{Saídas:\} C-02:", r"\\dot Q_\{\\mbox\{P-003\}\}=\\sum", r"\\paragraph\{Modelo de cálculo:\} \$\\dot m_\{C25\}",
    r"Maior pressão \(igual em todos os casos",
)]


@pytest.fixture(scope="module")
def base():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    return dados, prem, resolver_todos(dados, prem)


def test_layout_original_identico_ao_script(base):
    assert memorial.gerar(*base) == (FIX / "main_ref.tex").read_text(encoding="utf-8")


def test_corpo_identico_entre_layouts_salvo_premissas_do_layout(base):
    """O corpo é comum; só as linhas de premissa restritas a um layout (P-42, `senai`) diferem.
    O `original` segue o script de referência (paridade byte a byte: test_layout_original_identico_ao_script)."""
    env, ctx = memorial.preparar(*base)

    def corpo(layout):
        c = dict(ctx, premissas_memorial=[p for p in ctx["premissas_memorial"]
                                          if layout in p.get("layouts", memorial.LAYOUTS)])
        return "".join(env.get_template(f"{n}.tex.j2").render(c) for n in memorial.CORPO)

    senai, original = memorial.gerar(*base, layout="senai"), memorial.gerar(*base)
    assert senai.endswith(corpo("senai")) and original.endswith(corpo("original"))
    linhas_original = set(corpo("original").splitlines())
    so_senai = [x for x in corpo("senai").splitlines() if x not in linhas_original]
    assert len(so_senai) == 2 and all("P-42" in x for x in so_senai)  # tabela de premissas + rastro
    assert "P-42" not in original and "Nota~11" in senai
    assert "\\pagestyle{memorial}" in senai and base[0].sha256 in senai


def test_layout_desconhecido(base):
    with pytest.raises(ValueError, match="layout"):
        memorial.gerar(*base, layout="outro")


# ---------------------------------------------------------------- robustez
def rodar_original(tmp, casos_json, alteracoes=None):
    """Roda uma CÓPIA do script de referência (premissas opcionalmente alteradas no PREM)."""
    src = SCRIPT.read_text(encoding="utf-8")
    ini = src.index("PREM = dict(")
    fim = src.index(")", src.index("T_FWKO_min=40.0"))
    bloco = src[ini:fim]
    for k, v in (alteracoes or {}).items():
        bloco, n = re.subn(rf"\b{k}=[0-9.]+", f"{k}={v!r}", bloco)
        assert n == 1, k
    (tmp / "orig.py").write_text(src[:ini] + bloco + src[fim:], encoding="utf-8")
    (tmp / "design_cases_bot.json").write_text(json.dumps(casos_json), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("orig_mem", tmp / "orig.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["orig_mem"] = mod
    with pytest.MonkeyPatch.context() as mp, warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        mp.chdir(tmp)
        warnings.simplefilter("ignore")
        spec.loader.exec_module(mod)
    return (tmp / "main.tex").read_text(encoding="utf-8"), mod.PREM


def diferencas_nao_previstas(original, novo):
    a, b = original.splitlines(), novo.splitlines()
    ruins, previstas = [], 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op != "replace" or i2 - i1 != j2 - j1:
            ruins.append((op, a[i1:i2], b[j1:j2]))
            continue
        for la, lb in zip(a[i1:i2], b[j1:j2]):
            if any(p.match(lb) for p in LITERAIS_DO_ORIGINAL):
                previstas += 1
            else:
                ruins.append((la, lb))
    return ruins, previstas


@precisa_script
def test_robusto_a_outros_dados(tmp_path):
    d = json.loads(CASOS.read_text(encoding="utf-8"))
    d["fwko_pressure_kPa"] = 2350.0
    for c in d["cases"]:
        c["oil_sm3d"] = round(c["oil_sm3d"] * 1.07)
        c["liquid_sm3d"] = max(c["oil_sm3d"], round(c["liquid_sm3d"] * 1.04))
        c["T_C"] -= 3
        for k in ("produced_gas_sm3d", "lift_gas_sm3d", "transferred_gas_sm3d"):
            c[k] = round(c[k] * 0.93)
        c["total_gas_sm3d"] = c["produced_gas_sm3d"] + c["lift_gas_sm3d"] + c["transferred_gas_sm3d"]
    original, _ = rodar_original(tmp_path, d)
    dados = carregar_casos(tmp_path / "design_cases_bot.json")
    prem = premissas(dados)
    ruins, previstas = diferencas_nao_previstas(original, memorial.gerar(dados, prem, resolver_todos(dados, prem)))
    assert ruins == [] and previstas > 0


@precisa_script
def test_robusto_a_outras_premissas(tmp_path):
    alt = dict(P_D1=650.0, P_D2=180.0, BSW_pre=0.015, BSW_t=0.004, dT_app=12.0, T_trat=92.0, C_OiW=2.4, S_W=230000.0,
               S_spec=280.0, T_store=38.0, cp_D=4.2, T_dil_out=88.0, T_dil_in=24.0, P_rec=2700.0, P_pump_oil=850.0)
    original, prem_orig = rodar_original(tmp_path, json.loads(CASOS.read_text(encoding="utf-8")), alt)
    dados = carregar_casos(tmp_path / "design_cases_bot.json")
    prem = premissas(dados, **alt)
    assert prem == prem_orig
    novo = memorial.gerar(dados, prem, resolver_todos(dados, prem))
    ruins, previstas = diferencas_nao_previstas(original, novo)
    assert ruins == [] and previstas > 0
    assert "\\frac{0{,}015}{0{,}985}" in novo  # premissa não arredondada no texto


# ---------------------------------------------------------------- invariante 3
def test_bijecao_equacoes_memorial(base):
    tex = memorial.gerar(*base)
    rotulos = set(re.findall(r"\\label\{([^}]+)\}", tex))
    catalogo = carregar("equacoes_balanco.toml")
    ancoras = {a for e in catalogo.values() for a in e["memorial"]}
    definicoes = set(tomllib.loads(files("fpso_siz.output.latex.balanco").joinpath("rastro_memorial.toml")
                                   .read_text(encoding="utf-8"))["definicoes"])
    assert ancoras <= rotulos, ancoras - rotulos                      # toda equação do motor aparece
    eqs = {r for r in rotulos if r.startswith("eq:")}
    assert eqs <= ancoras | definicoes, eqs - ancoras - definicoes    # toda equação escrita tem origem
    assert not (definicoes & ancoras) and definicoes <= eqs


def test_criticos_iguais_ao_oraculo(base):
    oraculo = json.loads((FIX / "oraculo_balanco.json").read_text(encoding="utf-8"))["criticos"]
    crit = indicadores.criticos(base[2], base[0], base[1])
    assert [(v, c) for _, v, c in crit] == [(o["valor"], o["casos"]) for o in oraculo]
    textos = tomllib.loads(files("fpso_siz.output.latex.balanco").joinpath("criticos_memorial.toml")
                           .read_text(encoding="utf-8"))["linhas"]
    assert [(t["equipamento"], t["criterio"]) for t in textos] == [(o["equipamento"], o["criterio"]) for o in oraculo]
    assert [t["id"] for t in textos] == [k for k, _, _ in crit]


# ---------------------------------------------------------------- formatação e CLI
def test_formatacao():
    assert formatacao.br(None) == "--" and formatacao.br(-0.0001, 2) == "0,00" and formatacao.br(1234567.891, 1) == "1.234.567,9"
    assert formatacao.sci(0) == "$0$" and formatacao.sci(-2.5e-11) == "$-2{,}5\\times10^{-11}$"
    assert [formatacao.mbn(x, d) for x, d in [(0.01, 2), (0.015, 2), (2.0, 1), (1.0, 0), (1234.5, 0)]] == \
        ["0{,}01", "0{,}015", "2{,}0", "1", "1.234{,}5"]
    assert formatacao.esc("a_b&c%#") == "a\\_b\\&c\\%\\#" and formatacao.ids([1, 2]) == "1, 2"


def test_cli_memorial(tmp_path, capsys):
    assert main(["memorial", "--casos", str(CASOS), "--saida", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "main.tex").read_bytes() == (FIX / "main_ref.tex").read_bytes()
    assert main(["memorial", "--casos", str(CASOS), "--saida", str(tmp_path / "s"), "--layout", "senai"]) == 0
    assert (tmp_path / "s" / "logo-senai.png").stat().st_size > 0
    with pytest.raises(SystemExit):
        main(["memorial", "--casos", str(CASOS), "--saida", str(tmp_path), "--layout", "outro"])


def test_cli_memorial_pdf_sem_latexmk(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert main(["memorial", "--casos", str(CASOS), "--saida", str(tmp_path), "--pdf"]) == 3
    assert "latexmk não encontrado" in capsys.readouterr().err


def test_compilacao_falha_reporta_log(tmp_path, monkeypatch):
    class R:
        returncode, stdout = 1, "linha\n! erro fatal"
    monkeypatch.setattr(shutil, "which", lambda _: "/bin/latexmk")
    monkeypatch.setattr(compilacao.subprocess, "run", lambda *a, **k: R())
    (tmp_path / "main.tex").write_text("x", encoding="utf-8")
    with pytest.raises(compilacao.ErroCompilacao, match="erro fatal"):
        compilacao.compilar(tmp_path / "main.tex")
    (tmp_path / "main.log").write_text("log\n! Undefined control sequence", encoding="utf-8")
    with pytest.raises(compilacao.ErroCompilacao, match="Undefined"):
        compilacao.compilar(tmp_path / "main.tex")


# ---------------------------------------------------------------- compilação real (lenta)
@pytest.mark.latex
@pytest.mark.skipif(not compilacao.disponivel(), reason="latexmk ausente")
@pytest.mark.parametrize("layout", sorted(memorial.LAYOUTS))
def test_compila_em_pdf(base, tmp_path, layout):
    pdf = compilacao.compilar(memorial.gravar(*base, tmp_path, layout))
    log = pdf.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    assert pdf.stat().st_size > 100_000
    assert not re.search(r"^! ", log, re.M) and "undefined" not in log.lower()
