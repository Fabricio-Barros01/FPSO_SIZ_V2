"""Memorial de cálculo do balanço preliminar em LaTeX.

O corpo (seções 1–18 e apêndices) é comum aos layouts; o layout define preâmbulo e
capa: `original` reproduz byte a byte o main.tex do script de referência, `senai` usa o
template SENAI CETIQT. Toda grandeza vem do núcleo (resultado, rastro, indicadores,
catálogos); aqui só se escolhe o texto e o formato.
"""
import tomllib
from pathlib import Path
from importlib.resources import files

from fpso_siz.balanco import indicadores
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.balancos import balanco_bloco, balanco_global, origem_destino, topologia
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_k
from fpso_siz.output.latex.ambiente import ambiente

CORPO = ["02_introducao", "03_escopo", "04_fonte", "05_condicoes", "06_conversao", "07_premissas", "08_diagrama",
         "09_correntes", "10_global", "11_blocos", "11a_M01", "11b_SG001", "11c_P001", "11d_P002", "11e_V001",
         "11f_TO001", "11g_B002", "11h_DWH001", "11i_M02", "11j_V002", "11k_TO002", "11l_B003", "11m_M03",
         "11n_B001", "11o_P003", "11p_MED001", "12_massa_caso", "13_energia", "14_consolidada", "15_eficiencias",
         "16_fechamento", "17_envelopes", "18_informacoes", "19_conclusoes", "20_referencias", "21_ap_correntes",
         "22_ap_componentes", "23_ap_rastro", "24_reprodutibilidade"]
LAYOUTS = {"original": ["00_preambulo_original", "01_capa_original"],
           "senai": ["00_preambulo_senai", "01_capa_senai"]}


def contexto(dados, prem, resultados):
    meta = carregar("memorial_balanco.toml")
    nums = [r.num for r in resultados]
    RD = resultados[nums.index(meta["caso_demo"])]
    return dict(
        meta=meta, D=dados.bruto, dados=dados, P=prem, R=resultados, RD=RD, DEMO=meta["caso_demo"],
        topo=topologia(), ind=indicadores, VM=RD.VM, T_std_K=c_para_k(dados.T_std_C), aud=auditar(resultados, dados, prem),
        bb=balanco_bloco, gb=balanco_global, origem_destino=origem_destino,
        blocos={b["id"]: b for b in topologia()["blocos"]},
    )


def _conteudo(nome):
    texto = files("fpso_siz.output.latex.balanco").joinpath(nome).read_text(encoding="utf-8")
    return tomllib.loads(texto)["linhas"]


def tipo(t):
    """Marcador de classificação de origem do valor."""
    return r"\AV" if t == "A VALIDAR" else r"\tipo{" + t + "}"


def preparar(dados, prem, resultados):
    """(ambiente, contexto) prontos para renderizar qualquer template do memorial."""
    env = ambiente("fpso_siz.output.latex.balanco")
    ctx = contexto(dados, prem, resultados)
    ctx["avaliar"] = lambda expr: env.from_string(expr).render(ctx)
    # máximo entre casos de uma grandeza escrita como expressão de template em `r`
    ctx["maximo"] = lambda expr: indicadores.maximo(
        resultados, lambda r, f=env.compile_expression(expr): f(**ctx, r=r))
    ctx["tipo"] = tipo
    for nome in ("premissas", "envelopes", "criticos"):
        ctx[f"{nome}_memorial"] = _conteudo(f"{nome}_memorial.toml")
    ctx["envelopes"] = indicadores.envelopes(resultados, dados, prem)
    ctx["criticos"] = indicadores.criticos(resultados, dados, prem)
    ctx["sens_casos"], ctx["sens_corridas"] = indicadores.sensibilidade(resultados, dados, prem)
    return env, ctx


def gerar(dados, prem, resultados, layout="original"):
    if layout not in LAYOUTS:
        raise ValueError(f"layout desconhecido: {layout!r} (use {sorted(LAYOUTS)})")
    env, ctx = preparar(dados, prem, resultados)
    # linha com `layouts` só entra nos layouts citados (o `original` segue o script de referência)
    ctx["premissas_memorial"] = [p for p in ctx["premissas_memorial"] if layout in p.get("layouts", LAYOUTS)]
    return "".join(env.get_template(f"{nome}.tex.j2").render(ctx) for nome in LAYOUTS[layout] + CORPO)


def gravar(dados, prem, resultados, pasta, layout="original"):
    """Grava main.tex (UTF-8) em `pasta`; no layout SENAI, também o logotipo. Devolve o .tex."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    tex = pasta / "main.tex"
    tex.write_text(gerar(dados, prem, resultados, layout), encoding="utf-8")
    if layout == "senai":
        logo = files("fpso_siz.output.latex.balanco").joinpath("recursos", "logo-senai.png")
        (pasta / "logo-senai.png").write_bytes(logo.read_bytes())
    return tex
