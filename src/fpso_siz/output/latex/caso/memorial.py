"""Memorial do balanço de massa e energia de UM caso (F11b): MC_Caso01 … MC_Caso16.

Anexo do memorial do balanço (MC-SEN-SEP-COO-001), no layout SENAI. Toda grandeza vem do
núcleo: resultado do caso, `balanco/balancos.py` e `balanco/indicadores.py`; aqui só se
escolhe texto e formato. A folha de rosto traz o commit, as premissas diferentes do padrão e
a data. Casos sem fase aquosa (P-42) mostram "—" nas grandezas da fase aquosa.
O arquivo de um caso é o mesmo gerado isolado ou em lote (a data é parâmetro).
"""
from importlib.resources import files
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.balanco import indicadores
from fpso_siz.balanco.balancos import balanco_bloco, balanco_global, topologia
from fpso_siz.balanco.dados import descritores_premissas
from fpso_siz.core.configuracao import carregar
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.ambiente import ambiente
from fpso_siz.output.latex.tag.memorial import data_hoje, proveniencia_git

PACOTE = "fpso_siz.output.latex.caso"
BALANCO = "fpso_siz.output.latex.balanco"
TODOS = "todos"


def cfg():
    return carregar("memorial_balanco.toml")


def nome_arquivo(num):
    return cfg()["caso"]["arquivo"].format(num=num)


def premissas_alteradas(dados, prem):
    """Premissas com valor diferente do padrão (arquivo de casos + premissas.toml)."""
    return [dict(d, atual=prem[d["nome"]]) for d in descritores_premissas(dados) if prem[d["nome"]] != d["valor"]]


def selecionar(texto, nums):
    """'todos', 'N' ou '1,4-7' → números de caso válidos; ValueError se algum não existe."""
    if texto == TODOS:
        return list(nums)
    out = []
    for parte in str(texto).replace(" ", "").split(","):
        a, sep, b = parte.partition("-")
        if not a.isdigit() or (sep and not b.isdigit()):
            raise ValueError(f"caso inválido: {parte!r} (use N, N-M, lista ou '{TODOS}')")
        out += [n for n in (range(int(a), int(b) + 1) if sep else [int(a)]) if n not in out]
    fora = [n for n in out if n not in nums]
    if fora:
        raise ValueError(f"casos inexistentes no arquivo: {fora}; disponíveis: {nums[0]}–{nums[-1]}")
    return out


def contexto(dados, prem, resultados, num, data=None, git=None):
    meta = cfg()
    c = meta["caso"]
    r = next(x for x in resultados if x.num == num)
    commit, sujo = git if git is not None else proveniencia_git()
    titulo = c["titulo"].format(num=num, nome=r.caso.get("name", r.fluid))
    doc = dict(meta, numero=c["numero"].format(num=num), numero_balanco=meta["numero"], data=data or data_hoje(),
               descricao_revisao=c["descricao_revisao"], senai=dict(meta["senai"], tipo=c["tipo"], titulo=titulo.upper()))
    agua = indicadores.balanco_agua(r)
    return dict(meta=doc, titulo=titulo, r=r, dados=dados, P=prem, ind=indicadores,
                topo=topologia(), bb=balanco_bloco, gb=balanco_global, commit=commit, sujo=sujo,
                versao=__version__, alteradas=premissas_alteradas(dados, prem),
                sem_agua=not sum(agua["entra"].values()) > 0, agua=agua, sem_fase=c["sem_fase"],
                fech=indicadores.criterios()["fechamento_max"], preambulo_extra="")


def gerar(dados, prem, resultados, num, data=None, git=None):
    ctx = contexto(dados, prem, resultados, num, data, git)
    return ambiente(PACOTE, BALANCO).get_template("mc_caso.tex.j2").render(ctx)


def gravar(dados, prem, resultados, num, pasta, data=None, git=None):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    tex = pasta / f"{nome_arquivo(num)}.tex"
    tex.write_text(gerar(dados, prem, resultados, num, data, git), encoding="utf-8")
    logo = files(BALANCO).joinpath("recursos", "logo-senai.png")
    (pasta / "logo-senai.png").write_bytes(logo.read_bytes())
    return tex


def exportar_lote(dados, prem, resultados, nums, pasta, data=None, git=None, pdf=False):
    """Um MC por caso, pela mesma função do caso isolado, em <pasta>/MC_CasoNN. (arquivos, [erros])."""
    git = git if git is not None else proveniencia_git()
    arquivos, erros = [], []
    for num in nums:
        tex = gravar(dados, prem, resultados, num, Path(pasta) / nome_arquivo(num), data, git)
        arquivos.append(tex)
        if pdf:
            try:
                arquivos.append(compilacao.compilar(tex))
            except compilacao.ErroCompilacao as e:
                erros.append(f"{tex.stem}: {e}")
    return arquivos, erros
