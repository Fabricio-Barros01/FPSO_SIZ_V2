"""Invariantes de arquitetura (CLAUDE.md). Quebrar qualquer uma é defeito, não escolha.

1. Núcleo sem UI e sem rede; nada formata/imprime fora de output/ e cli.py; caminhos
   resolvidos em runtime.
2. Constantes e premissas em TOML; nenhum literal numérico nas equações além de
   {0, 1, 2, 10} (fatores exatos só em core/unidades.py; a camada de saída, que só
   apresenta, está fora desta regra).
(3, a bijeção equação↔rastro, está em tests/balanco/test_trace.py; 4 entra com a CLI.)
"""
import ast
import re
from pathlib import Path

import pytest

from fpso_siz.core.configuracao import carregar

PACOTE = Path(__file__).resolve().parents[2] / "src" / "fpso_siz"
MODULOS = sorted(PACOTE.rglob("*.py"))
ROTULO = lambda p: p.relative_to(PACOTE).as_posix()
SAIDA = lambda p: ROTULO(p).startswith("output/") or ROTULO(p) in ("cli.py", "__main__.py")

REDE = {"socket", "urllib", "http", "requests", "httpx", "aiohttp", "ftplib", "smtplib", "websocket"}
UI = {"tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "flask", "fastapi", "streamlit", "dash"}
SO_EM = {"numpy": {"_num.py"}, "scipy": {"_num.py"}, "jinja2": "output/"}
# 0,5 (vaso meio cheio, média), 4 (área πd²/4; casas decimais) e 10 (base) são estruturais,
# não coeficientes empíricos; estes vão para TOML.
LITERAIS_OK = {0, 0.5, 1, 2, 4, 10}
EXATOS = {"core/unidades.py",        # fatores de conversão exatos
          "core/formato_julia.py",   # regra de impressão de números do Julia (não é física)
          "core/grade.py"}           # algoritmo de faixa float do Julia (limites de maxintfloat)


def arvore(p):
    return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def importados(p):
    for n in ast.walk(arvore(p)):
        if isinstance(n, ast.Import):
            yield from (a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            yield n.module.split(".")[0]


def test_ha_modulos_a_verificar():
    assert len(MODULOS) >= 8


@pytest.mark.parametrize("p", MODULOS, ids=ROTULO)
def test_sem_rede_e_sem_ui(p):
    assert not (set(importados(p)) & (REDE | UI))


@pytest.mark.parametrize("p", MODULOS, ids=ROTULO)
def test_dependencias_pesadas_so_na_sua_porta(p):
    for mod in set(importados(p)) & set(SO_EM):
        permitido = SO_EM[mod]
        ok = ROTULO(p) in permitido if isinstance(permitido, set) else ROTULO(p).startswith(permitido)
        assert ok, f"{ROTULO(p)} importa {mod}"


@pytest.mark.parametrize("p", [p for p in MODULOS if not SAIDA(p)], ids=ROTULO)
def test_nucleo_nao_imprime_nem_importa_saida(p):
    for n in ast.walk(arvore(p)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            assert n.func.id != "print", f"{ROTULO(p)}:{n.lineno}"
        if isinstance(n, ast.ImportFrom) and n.module:
            assert not n.module.startswith(("fpso_siz.output", "fpso_siz.cli")), ROTULO(p)


@pytest.mark.parametrize("p", MODULOS, ids=ROTULO)
def test_sem_url_nem_caminho_absoluto(p):
    for n in ast.walk(arvore(p)):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            s = n.value
            assert not re.search(r"https?://", s), f"{ROTULO(p)}:{n.lineno} URL"
            assert not re.match(r"^(/[A-Za-z]|[A-Za-z]:[\\/]|~/)", s), f"{ROTULO(p)}:{n.lineno} caminho {s!r}"
        if isinstance(n, ast.Name):
            assert n.id != "__file__", f"{ROTULO(p)}:{n.lineno} use importlib.resources"


def test_toml_sem_url():
    for p in (PACOTE / "config").rglob("*.toml"):
        assert not re.search(r"https?://", p.read_text(encoding="utf-8")), p.name


@pytest.mark.parametrize("p", [p for p in MODULOS if ROTULO(p) not in EXATOS and not SAIDA(p)], ids=ROTULO)
def test_sem_literal_numerico_nas_equacoes(p):
    for n in ast.walk(arvore(p)):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            assert n.value in LITERAIS_OK, f"{ROTULO(p)}:{n.lineno} literal {n.value!r} → TOML"


def test_constantes_citam_fonte():
    for secao, conteudo in carregar("constantes.toml").items():
        assert "fonte" in conteudo, secao


def test_premissas_tem_id_unidade_e_descricao():
    for nome, e in carregar("premissas.toml").items():
        assert re.fullmatch(r"[FP]-\d\d", e["id"]), nome
        assert e["unidade"] and e["descricao"], nome
        assert "valor" in e or "chave_casos" in e or nome == "carry", nome


def test_cli_nao_nomeia_parametros_nem_grandezas():
    """Invariante 4: a CLI só itera descritores; nenhum nome de premissa, equação,
    coluna, verificação ou campo de resultado aparece como texto em cli.py."""
    from fpso_siz.balanco.modelo import ResultadoCaso

    proibidos = (set(carregar("premissas.toml")) | set(carregar("equacoes_balanco.toml"))
                 | set(carregar("auditoria.toml")) | {c["id"] for c in carregar("saida_correntes.toml")["colunas"]}
                 | set(ResultadoCaso.__dataclass_fields__)) - {"caso", "nome"}
    textos = {n.value for n in ast.walk(arvore(PACOTE / "cli.py"))
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (textos & proibidos), textos & proibidos


@pytest.mark.parametrize("nome", ["core/motor.py", "core/contrato.py"])
def test_motor_nao_nomeia_grandezas(nome):
    """O motor é genérico sobre equipamento E grandeza: nenhuma chave de corrente ou de
    parâmetro de método aparece como texto nele (invariante 4, lado do núcleo)."""
    from fpso_siz.core.corrente import STREAM_KEYS

    textos = {n.value for n in ast.walk(arvore(PACOTE / nome)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (textos & set(STREAM_KEYS))
    assert not (textos & {"d_min", "d_max", "sr", "lss", "leff", "sr_min", "sr_max", "dn", "npsh"})
