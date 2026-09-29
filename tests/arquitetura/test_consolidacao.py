"""Consolidação arquitetural (docs/arquitetura/arquitetura-alvo.md): uma implementação produtiva
por responsabilidade, provada sobre o código — não sobre a documentação.

- existe uma única API pública de flash, e só ela fala com o backend;
- existe um único resolvedor produtivo de processo, e só ele cria o estado oficial;
- o dimensionamento não conhece processo nem termodinâmica: recebe entradas prontas;
- a saída e o memorial não avaliam física: leem o que o motor e o processo produziram;
- a otimização passa pelo mesmo serviço, não pelo motor nem pelo backend;
- tools/ não fala com o backend nem com o interior do motor;
- nenhum módulo de src/ fica sem consumidor, e nenhum nome de compatibilidade sobrevive.
"""
import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "fpso_siz"
MODULOS = sorted(p for p in PACOTE.rglob("*.py") if "__pycache__" not in p.parts)
TOOLS = sorted((RAIZ / "tools").glob("*.py"))


def rotulo(p):
    return p.relative_to(PACOTE).as_posix()


def nome_modulo(p):
    partes = list(p.relative_to(PACOTE.parent).with_suffix("").parts)
    return ".".join(partes[:-1] if partes[-1] == "__init__" else partes)


def arvore(p):
    return ast.parse(p.read_text(encoding="utf-8"))


def importados(p):
    """Módulos fpso_siz importados, com `from pacote import modulo` resolvido."""
    nomes = {nome_modulo(m) for m in MODULOS}
    out = set()
    for n in ast.walk(arvore(p)):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names if a.name.startswith("fpso_siz")}
        elif isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("fpso_siz"):
            out.add(n.module)
            out |= {f"{n.module}.{a.name}" for a in n.names if f"{n.module}.{a.name}" in nomes}
    return out


def chamadas_de_atributo(p, exceto=()):
    """Nomes chamados como atributo (`x.nome(...)`), menos os chamados sobre os módulos `exceto`."""
    return {n.func.attr for n in ast.walk(arvore(p))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and not (isinstance(n.func.value, ast.Name) and n.func.value.id in exceto)}


def definicoes(p):
    return {n.name for n in ast.walk(arvore(p)) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


# ------------------------------------------------------------------ termodinâmica
def test_uma_unica_api_de_flash():
    donos = [rotulo(p) for p in MODULOS if {"flash_tp", "flash_poco"} & definicoes(p)]
    assert donos == ["termo/servico.py"]


def test_so_o_servico_fala_com_o_backend():
    usam = sorted(rotulo(p) for p in MODULOS if "fpso_siz.termo.backend" in importados(p))
    assert usam == ["termo/servico.py"]


# o benchmark MEDE: envolve funções do backend para contar chamadas repetidas, sem calcular nada
MEDICAO = {"benchmark.py"}


@pytest.mark.parametrize("p", [p for p in TOOLS if p.name not in MEDICAO], ids=lambda p: p.name)
def test_tools_nao_falam_com_o_backend_nem_com_o_interior_do_motor(p):
    usados = importados(p)
    assert "fpso_siz.termo.backend" not in usados and "fpso_siz.termo.caracterizacao" not in usados
    assert not {"sizing_constraints", "_tubo", "flash_pseudo"} & chamadas_de_atributo(p), p.name


# ------------------------------------------------------------------ processo
def test_um_unico_resolvedor_de_processo():
    donos = [rotulo(p) for p in MODULOS if {"resolver_caso", "resolver_todos"} & definicoes(p)]
    assert donos == ["balanco/modelo.py"]


def test_so_o_resolvedor_cria_o_estado_oficial():
    for p in MODULOS:
        criam = any(isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "EstadoProcesso"
                    for n in ast.walk(arvore(p)))
        assert not criam or rotulo(p) == "balanco/modelo.py", rotulo(p)


def test_o_trem_e_parte_do_estado_e_nao_um_segundo_modelo():
    donos = [rotulo(p) for p in MODULOS if "TremSeparacao" in definicoes(p)]
    assert donos == ["balanco/trem.py"]
    assert not (PACOTE / "pfd" / "cascata.py").exists() and not (PACOTE / "pfd" / "integracao.py").exists()


# ------------------------------------------------------------------ dimensionamento
@pytest.mark.parametrize("p", [p for p in MODULOS if rotulo(p).startswith("sizing/")], ids=rotulo)
def test_o_dimensionamento_recebe_entradas_prontas(p):
    """Os métodos não reconstroem processo nem propriedade: não importam balanço, planta nem termo."""
    proibidos = {m for m in importados(p) if m.startswith(("fpso_siz.balanco", "fpso_siz.pfd", "fpso_siz.termo"))}
    assert not proibidos, proibidos


# ------------------------------------------------------------------ saída e memorial
HOOKS_DE_FISICA = {"sizing_constraints", "requirement", "derived", "governing_of", "per_constraint", "perfil_tq",
                   "parcelas_u", "curva_sistema", "npsh_exigido", "npsh_disponivel", "operacao_por_caso",
                   "bloqueios", "bordas_banda", "banda_memorial", "selecao_memorial", "admissible",
                   "envelope_params", "envelope_case_params", "envelope_derived", "size_envelope", "size_single",
                   "flash_tp", "resolver_todos", "resolver_caso"}
SAIDA = [p for p in MODULOS if rotulo(p).startswith("output/") or rotulo(p) == "pfd/memorial.py"]


@pytest.mark.parametrize("p", SAIDA, ids=rotulo)
def test_saida_e_memorial_nao_avaliam_fisica(p):
    """Saída e memorial leem resultados; o que exige o método sai de core/memoria.py. A exceção
    é a camada de comando, que pede ao processo um resultado (não reavalia um que já existe)."""
    chamadas = chamadas_de_atributo(p, exceto={"memoria"}) & HOOKS_DE_FISICA
    if rotulo(p) in ("output/terminal/sessao.py",):
        chamadas -= {"resolver_todos"}
    assert not chamadas, chamadas


# ------------------------------------------------------------------ otimização
@pytest.mark.parametrize("nome", ["pfd/otimizacao.py", "_otim.py"])
def test_a_otimizacao_passa_pelo_servico(nome):
    usados = importados(PACOTE / nome)
    assert not {m for m in usados if m.startswith(("fpso_siz.core.motor", "fpso_siz.sizing", "fpso_siz.termo"))}
    assert not {"size_envelope", "size_single", "sizing_constraints", "flash_tp"} & chamadas_de_atributo(PACOTE / nome)


def test_pressoes_do_trem_sao_premissas_otimizaveis_por_configuracao():
    """P_D1 e P_D2 viram variável de decisão por DECLARAÇÃO (`destino = "premissa"` no TOML, no
    subproblema de pressão): o decodificador as entrega ao processo, e o trem as lê do estado —
    sem código novo nem segundo resolvedor."""
    from fpso_siz.core.configuracao import carregar
    from fpso_siz.pfd import otimizacao as ot
    assert {"P_D1", "P_D2"} <= set(carregar("premissas.toml"))
    assert all(v["destino"] == "premissa" for v in ot.variaveis("pressao"))
    prem, _, _ = ot.decodificar((650.0, 180.0), "pressao")
    assert prem == {"P_D1": 650.0, "P_D2": 180.0}


# ------------------------------------------------------------------ nada órfão, nada de compatibilidade
PONTOS_DE_ENTRADA = {"fpso_siz", "fpso_siz.cli", "fpso_siz.__main__", "fpso_siz.config",
                     # porta do pymoo e avaliador da otimização: consumidos pela ferramenta de otimização
                     # (tools/otimizar.py) e pela suíte, ainda sem comando na CLI
                     "fpso_siz._otim", "fpso_siz.pfd.otimizacao",
                     # análise do pré-aquecedor sobre o EstadoProcesso (tools/pinch_planta.py)
                     "fpso_siz.pfd.pinch"}


def test_nenhum_modulo_sem_consumidor():
    consumidos = set().union(*(importados(p) for p in MODULOS))
    orfaos = sorted(nome_modulo(p) for p in MODULOS
                    if nome_modulo(p) not in consumidos | PONTOS_DE_ENTRADA and not p.name == "__init__.py")
    assert orfaos == [], orfaos


def test_nenhum_nome_de_compatibilidade():
    # nomes de camada de compatibilidade (como partes inteiras do identificador) e as flags removidas
    padrao = re.compile(r"(legacy|deprecated|bridge|temporary_adapter|(^|_)(compat|old)(_|$)|topologia_julia|oleo_morto)",
                        re.I)
    for p in MODULOS:
        for n in ast.walk(arvore(p)):
            nome = getattr(n, "name", None) or getattr(n, "id", None) or getattr(n, "attr", None) or getattr(n, "arg", None)
            if isinstance(nome, str):
                assert not padrao.search(nome), (rotulo(p), nome)
