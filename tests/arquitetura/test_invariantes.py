"""Invariantes de arquitetura (CLAUDE.md). Quebrar qualquer uma é defeito, não escolha.

1. Núcleo sem UI e sem rede; nada formata/imprime fora de output/ e cli.py; caminhos
   resolvidos em runtime.
2. Constantes e premissas em TOML; nenhum literal numérico nas equações além de
   {0, 1, 2, 10} (fatores exatos só em core/unidades.py; a camada de saída, que só
   apresenta, está fora desta regra).
(3, a bijeção equação↔rastro, está em tests/balanco/test_trace.py.)
4. A CLI não nomeia parâmetro: por comando, interativa e as saídas de dimensionamento.
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
# thermo/chemicals (ChEDL): dependência direta por decisão do usuário (2026-09-23), atrás de
# uma porta única, como numpy/scipy — o port a C/Java troca só essa camada.
SO_EM = {"numpy": {"_num.py"}, "scipy": {"_num.py"}, "jinja2": "output/", "thermo": {"pfd/_chedl.py"},
         "chemicals": {"pfd/_chedl.py"}, "fluids": {"pfd/_chedl.py"}, "pandas": set()}
# 0,5 (vaso meio cheio, média), 4 (área πd²/4; casas decimais), 8 (área do segmento circular
# d²/8) e 10 (base) são estruturais, não coeficientes empíricos; estes vão para TOML.
LITERAIS_OK = {0, 0.5, 1, 2, 4, 8, 10}
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
    arv = arvore(p)
    # casas decimais de apresentação (`digits=3` no cartão de resultados) não são física
    apresentacao = {id(k.value) for n in ast.walk(arv) if isinstance(n, ast.Call) for k in n.keywords if k.arg == "digits"}
    for n in ast.walk(arv):
        if id(n) in apresentacao:
            continue
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


INTERFACE = ["cli.py", "output/dimensionamento.py", "output/pfd.py", "output/ajustes.py", "output/latex/tag/memorial.py",
             *sorted(p.relative_to(PACOTE).as_posix() for p in (PACOTE / "output" / "terminal").glob("*.py"))]


@pytest.mark.parametrize("nome", INTERFACE)
def test_cli_nao_nomeia_parametros_nem_grandezas(nome):
    """Invariante 4: a CLI (por comando e interativa) só itera descritores; nenhum nome de
    premissa, equação, coluna, verificação, campo de resultado, parâmetro de método ou
    chave de corrente aparece como texto nela."""
    import fpso_siz.sizing  # noqa: F401
    from fpso_siz.balanco.modelo import ResultadoCaso
    from fpso_siz.core import registro
    from fpso_siz.core.corrente import STREAM_KEYS

    parametros = {s.key for eq in registro.equipments() for m in registro.methods_for(eq)
                  for s in [*m.parameters(), *m.stream_parameters()]}
    proibidos = (set(carregar("premissas.toml")) | set(carregar("equacoes_balanco.toml"))
                 | set(carregar("auditoria.toml")) | {c["id"] for c in carregar("saida_correntes.toml")["colunas"]}
                 | set(ResultadoCaso.__dataclass_fields__) | parametros | set(STREAM_KEYS)) - {"caso", "nome"}
    textos = {n.value for n in ast.walk(arvore(PACOTE / nome))
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


def _textos(nome):
    return {n.value for n in ast.walk(arvore(PACOTE / nome)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


@pytest.mark.parametrize("nome", INTERFACE)
def test_interface_nao_fixa_tags_blocos_nem_correntes(nome):
    """F10c: TAGs, blocos e correntes vêm dos descritores e da topologia; um desenho ou uma
    tela com 'V-001' ou 'C-10' escrito no código não acompanharia a configuração."""
    from fpso_siz.balanco.balancos import topologia
    from fpso_siz.pfd.tags import tags

    topo = topologia()
    ids = {t.tag for t in tags()} | {b["id"] for b in topo["blocos"]} | {c["id"] for c in topo["correntes"]}
    assert not (_textos(nome) & ids)
    assert not [s for s in _textos(nome) if re.search(r"(?<![\w-])C-\d\d(?![\w-])", s)]


@pytest.mark.parametrize("nome", INTERFACE)
def test_interface_nao_monta_entradas_nem_chama_o_motor(nome):
    """F10c: comandos e menus só selecionam, leem/gravam e apresentam; a montagem de
    entradas e a chamada do motor são do serviço por TAG (pfd/equipamento.py)."""
    proibidos = {"size_envelope", "size_single", "montar", "montar_manual", "REGRAS"}
    for n in ast.walk(arvore(PACOTE / nome)):
        if isinstance(n, ast.ImportFrom):
            assert not ({a.name for a in n.names} & proibidos), (nome, n.module)
            assert n.module not in ("fpso_siz.pfd.entradas", "fpso_siz.pfd.fluidos", "fpso_siz.pfd._chedl"), nome
        if isinstance(n, ast.Attribute):
            assert n.attr not in proibidos, (nome, n.attr)


def test_sessao_tira_textos_e_menus_do_toml():
    """Os rótulos dos menus e os textos da sessão estão em interativo.toml, não no código."""
    cfg = carregar("interativo.toml")
    declarados = {a["rotulo"] for m in cfg["menus"].values() for a in m["acoes"]}
    declarados |= {m["titulo"] for m in cfg["menus"].values()}
    declarados |= {v for v in cfg["textos"].values() if isinstance(v, str)}
    frases = {t for t in declarados if " " in t.strip()}  # palavras soltas coincidem com ids
    for nome in ("output/terminal/sessao.py", "output/terminal/pfd.py", "cli.py"):
        assert not (_textos(nome) & frases), nome


def test_servico_por_tag_e_nucleo():
    """O serviço por TAG não pergunta, não imprime nem grava: é núcleo."""
    for nome in ("pfd/equipamento.py", "pfd/ajustes.py", "pfd/manual.py", "pfd/planta.py"):
        mods = set()
        for n in ast.walk(arvore(PACOTE / nome)):
            if isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in ("print", "input"), nome
        assert not {m for m in mods if m.startswith("fpso_siz.output")}, nome
