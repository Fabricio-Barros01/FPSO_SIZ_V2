"""Memorial de cálculo (MC) por TAG em LaTeX A4/SENAI (F11).

O conteúdo vem de `pfd.memorial.documento` (núcleo): aqui só se formata. Cada MC grava,
na mesma pasta e pelo mesmo comando: o `.tex`, os CSV lidos pelo pgfplots (nenhum número
de dado é digitado no `.tex`) e o JSON do documento (os números em precisão total, para o
teste PDF × JSON). O número do documento vem da tabela de config/memorial_tag.toml, nunca
da ordem de exportação; exportar um TAG isolado ou em lote dá os mesmos bytes (a data é
parâmetro).
"""
import math
import re
import subprocess
from datetime import date
from importlib.resources import files
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.core.configuracao import carregar
from fpso_siz.output.arquivos import escrever_csv, escrever_json
from fpso_siz.output.latex import compilacao, formatacao
from fpso_siz.output.latex.ambiente import ambiente
from fpso_siz.pfd import memorial as nucleo

PACOTE = "fpso_siz.output.latex.tag"
BALANCO = "fpso_siz.output.latex.balanco"
MARCA = re.compile(r"@(k:)?([A-Za-z_][A-Za-z0-9_]*)@")
TIPO_FONTE = {"F-": "dado de fonte (BOT)", "P-": "premissa"}


def cfg():
    return carregar("memorial_tag.toml")


def proveniencia_git():
    """(commit curto, há alterações locais?) do repositório de onde o pacote roda; None se
    não houver git (pacote instalado)."""
    raiz = Path(str(files("fpso_siz"))).parent
    try:
        commit = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=raiz, capture_output=True,
                                text=True, timeout=10, check=True).stdout.strip()
        sujo = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=raiz,
                              capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None, None
    return commit, bool(sujo)


def data_hoje():
    return date.today().strftime("%d/%m/%Y")


# ------------------------------------------------------------------ formatação
def _valor_op(nome, v, exatos):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return formatacao.tx(str(v))
    return formatacao.mbn(v) if nome in exatos else formatacao.sig(v)


def substituir(expr, operandos, unidades=None, constantes=None, exatos=()):
    """Troca @nome@ pelo operando formatado (com unidade, se declarada) e @k:nome@ pela
    constante do método. Operando ausente é erro: o MC não inventa número."""
    unidades = unidades or {}

    def troca(mo):
        const, nome = mo.groups()
        if const:
            return formatacao.mbn(constantes[nome])
        v = _valor_op(nome, operandos[nome], exatos)
        u = unidades.get(nome)
        return f"{v}\\,\\text{{{formatacao.unid(u)}}}" if u else v
    return MARCA.sub(troca, expr)


def _valor_entrada(v):
    if isinstance(v, (list, tuple)):
        return " -- ".join(formatacao.sigt(x) for x in v)
    return formatacao.sigt(v)


def _premissas(doc, prem):
    """Linhas das premissas citadas, com o texto e o tipo do catálogo do memorial do
    balanço (premissas_memorial.toml) e o valor do descritor."""
    env = ambiente(BALANCO)
    catalogo = {}
    for linha in carregar_catalogo():
        catalogo.setdefault(linha["id"], linha)
    out = []
    for p in doc["premissas"]:
        cat = catalogo.get(p["id"])
        texto = cat["parametro"] if cat else "; ".join(formatacao.tx(d["descricao"]) for d in p["descritores"])
        valor = env.from_string(cat["valor"]).render(P=prem) if cat and prem else "--"
        if (not cat or valor == "--") and p["descritores"]:
            valor = "; ".join(f"{formatacao.sigt(d['valor'])} {formatacao.unid(d['unidade'])}"
                              for d in p["descritores"] if isinstance(d["valor"], (int, float)))
        if re.match(r"(eq\.|Tab\.|Seç)", valor):   # remissão ao memorial do balanço, não a este
            valor = f"{cfg()['textos']['remissao_balanco']} {valor}"
        tipo = cat["tipo"].lower() if cat else TIPO_FONTE[p["id"][:2]]
        out.append(dict(id=p["id"], texto=texto, valor=valor or "--", tipo=tipo,
                        justificativa=cat.get("justificativa", "") if cat else ""))
    return out


def carregar_catalogo():
    import tomllib
    texto = files(BALANCO).joinpath("premissas_memorial.toml").read_text(encoding="utf-8")
    return tomllib.loads(texto)["linhas"]


COLUNAS_MATRIZ = 7   # colunas de entradas por tabela de casos (A4 retrato)


def tabelas_entrada(doc):
    """Entradas comuns a todos os casos ativos (uma linha) e as que variam por caso (matriz
    caso × entrada, em blocos, com a legenda de origem e fonte de cada coluna)."""
    ativos = [c["num"] for c in doc["casos"] if c["ativo"]]
    por = {}
    for e in doc["entradas"]:
        por.setdefault(e["chave"], []).append(e)
    comuns, variaveis = [], []
    for linhas in por.values():
        if len(linhas) == 1 and linhas[0]["casos"] == ativos:
            comuns.append(linhas[0])
        else:
            variaveis.append(linhas)
    legenda = [dict(chave=ls[0]["chave"], rotulo=ls[0]["rotulo"], unidade=ls[0]["unidade"],
                    fontes=list(dict.fromkeys((x["rotulo_origem"], x["fonte"]) for x in ls))) for ls in variaveis]
    blocos = []
    for i in range(0, len(variaveis), COLUNAS_MATRIZ):
        grupo = variaveis[i:i + COLUNAS_MATRIZ]
        linhas = []
        for n in ativos:
            nome = next(c["nome"] for c in doc["casos"] if c["num"] == n)
            linhas.append(dict(caso=nome, valores=[next((x for x in ls if n in x["casos"]), None) for ls in grupo]))
        blocos.append(dict(chaves=[ls[0]["chave"] for ls in grupo], unidades=[ls[0]["unidade"] for ls in grupo],
                           linhas=linhas))
    return dict(comuns=comuns, legenda=legenda, blocos=blocos)


def _metodologia(doc, constantes):
    return [dict(m, latex=substituir(m["latex"], {}, constantes=constantes))
            for m in doc["conteudo"].get("metodologia", [])]


def _equacoes(calc, exatos):
    out = []
    for e in calc["equacoes"]:
        ops = e["operandos"]
        conv = e["conversao"]
        out.append(dict(e, campo_tex=substituir(e["campo"], ops, exatos=exatos) if e["campo"] else "",
                        metrico_tex=substituir(e["metrico"], ops, exatos=exatos),
                        subst_tex=substituir(e["substituicao"], ops, e["unidades"], exatos=exatos),
                        conv_tex=dict(convertido=formatacao.sig(conv["convertido"]),
                                      desvio=formatacao.sig(conv["desvio"] * 100)) if conv else None))
    return out


# ------------------------------------------------------------------ arquivos
def nome_base(doc):
    ident = doc["identificacao"]
    return ident["numero"] or f"MC-{ident['tag']}"


def _csvs(doc, pasta, base):
    """Grava os CSV dos gráficos e devolve {série: nome do arquivo} (o .tex só referencia)."""
    calc = doc["calculo"]
    if calc is None:
        return {}
    s = calc["series"]
    feitos = {}

    def gravar(chave, linhas):
        if not linhas:
            return
        nome = f"{base}_{chave}.csv"
        cols = list(dict.fromkeys(k for li in linhas for k in li))
        limpo = [{k: ("nan" if isinstance(v, float) and not math.isfinite(v) else v) for k, v in li.items()}
                 for li in linhas]
        escrever_csv([{"id": c} for c in cols], limpo, pasta / nome)
        feitos[chave] = nome

    gravar("diagrama", s.get("diagrama"))
    gravar("ponto", s.get("ponto"))
    gravar("teto", s.get("teto"))
    gravar("minimo", s.get("minimo"))
    for chave in ("perfil_tq", "curva_sistema", "ponto_bomba", "npsh"):
        gravar(chave, s.get(chave))
    if s.get("resistencias"):
        gravar("resistencias", [dict(i=i, r=x["r"], pct=x["fracao"] * formatacao.POR_CENTO)
                                for i, x in enumerate(s["resistencias"], 1)])
    casos = s.get("casos") or []
    govs = sorted({c["governante"] for c in casos if c["governante"]})
    gravar("casos", [dict(caso=c["caso"], y=c["y"], teto=c["teto"], x_ref=s["x_casos"],
                          **{f"y_{g}": (c["y"] if c["governante"] == g else math.nan) for g in govs})
                     for c in casos])
    feitos["governantes"] = govs
    return feitos


def contexto(ctx, rt, data=None, git=None):
    """(documento do núcleo, contexto do template)."""
    doc = nucleo.documento(ctx, rt)
    c = cfg()
    ident = doc["identificacao"]
    status = nucleo.ESTADOS_MC.get(ident["status"], "aguardando")
    tipo = c["senai"][f"tipo_{status}"]
    commit, sujo = git if git is not None else proveniencia_git()
    meta = dict(numero=ident["numero"] or f"MC-{ident['tag']}", revisao=c["revisao"],
                descricao_revisao=c["descricao_revisao"], data=data or data_hoje(), execucao=c["execucao"],
                verificacao=c["verificacao"], aprovacao=c["aprovacao"], numero_nota=c["numero_nota"],
                senai=dict(c["senai"], tipo=tipo, titulo=f"{ident['tag']} --- {ident['nome']}".upper()))
    exatos = set(c.get("operandos_exatos", ()))
    constantes = {k: v for k, v in rt.entradas.metodo.constants().items() if isinstance(v, (int, float))}
    calc = doc["calculo"]
    tpl = dict(doc=doc, meta=meta, ident=ident, status=status, textos=c["textos"], regra=c["regra_algarismos"],
               prem=_premissas(doc, ctx.prem), metodologia=_metodologia(doc, constantes),
               eqs=_equacoes(calc, exatos) if calc else [], commit=commit, sujo=sujo, versao=__version__,
               entradas=tabelas_entrada(doc), dados=ctx.dados if not ident["avulso"] else None, versoes=ctx.versoes, valor_entrada=_valor_entrada,
               preambulo_extra=files(PACOTE).joinpath("templates", "preambulo_extra.tex").read_text(encoding="utf-8"))
    return doc, tpl


def gerar(ctx, rt, data=None, git=None, csvs=None):
    doc, tpl = contexto(ctx, rt, data, git)
    tpl["csv"] = csvs or {}
    return doc, ambiente(PACOTE, BALANCO).get_template("mc_tag.tex.j2").render(tpl)


def gravar(ctx, rt, pasta, data=None, git=None):
    """<número>.tex, <número>.json e os CSV dos gráficos em `pasta`, com o logotipo SENAI.
    Devolve o caminho do .tex."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    doc = nucleo.documento(ctx, rt)
    base = nome_base(doc)
    csvs = _csvs(doc, pasta, base)
    doc, tex = gerar(ctx, rt, data, git, csvs)
    arq = pasta / f"{base}.tex"
    arq.write_text(tex, encoding="utf-8")
    escrever_json(_json(doc), pasta / f"{base}.json")
    logo = files(BALANCO).joinpath("recursos", "logo-senai.png")
    (pasta / "logo-senai.png").write_bytes(logo.read_bytes())
    return arq


PASTA_MC = "mc"


def exportar(ctx, rt, pasta, data=None, git=None, pdf=False):
    """MC de um TAG em `<pasta>/mc/<número>/` — o mesmo caminho e os mesmos bytes no TAG
    isolado e no lote. Devolve (arquivos gravados, erro de compilação ou None)."""
    destino = Path(pasta) / PASTA_MC / nome_base(nucleo.documento(ctx, rt))
    tex = gravar(ctx, rt, destino, data, git)
    arquivos = [tex, tex.with_suffix(".json"), *sorted(destino.glob(f"{tex.stem}_*.csv"))]
    if not pdf:
        return arquivos, None
    try:
        return arquivos + [compilacao.compilar(tex)], None
    except compilacao.ErroCompilacao as e:
        return arquivos, e


def exportar_lote(ctx, resultados, pasta, data=None, git=None, pdf=False):
    """MC de cada TAG (mesma função do TAG isolado). (arquivos, [erros])."""
    git = git if git is not None else proveniencia_git()
    arquivos, erros = [], []
    for rt in resultados:
        arqs, erro = exportar(ctx, rt, pasta, data, git, pdf)
        arquivos += arqs
        if erro is not None:
            erros.append(f"{rt.tag.tag}: {erro}")
    return arquivos, erros


def _json(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): _json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json(v) for v in obj]
    return obj
