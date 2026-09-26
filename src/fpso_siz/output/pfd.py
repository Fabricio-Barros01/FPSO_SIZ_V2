"""JSON e CSV de varredura por TAG (ou avulso) e planta.csv.

O serializador é o MESMO para o menu do TAG, `dimensionar --tag` e `pfd`: o artefato de um
TAG depende só do contexto e do estado daquele TAG, nunca dos outros. O PFD só acrescenta
planta.csv. JSON estrito: NaN/Inf viram null. A origem, a revisão e o estado distinguem
lacuna, recomendação não revisada, caso inativo e inviabilidade. A apresentação não conhece
os nomes dos parâmetros dos métodos.
"""
import math
from dataclasses import asdict
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.balanco.balancos import topologia
from fpso_siz.output import dimensionamento
from fpso_siz.output.arquivos import escrever_csv, escrever_json
from fpso_siz.pfd.ajustes import canonico_estado
from fpso_siz.pfd.equipamento import blocos_sem_dimensionamento, fontes_propriedades, limitacoes, rotulo_origem

ESQUEMA = 2
COLUNAS = ("tag", "equipamento", "x", "eixo_x", "y", "unidade_y", "caso_governante", "status")
SUFIXO_VARREDURA = "_varredura.csv"


def _limpar(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _limpar(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_limpar(v) for v in obj]
    return obj


def origem_entrada(ctx, rt):
    """Identificação da entrada do envelope: o arquivo de casos (TAG) ou o do avulso."""
    e = rt.entradas
    if e.avulso:
        return rt.estado.arquivo or rotulo_origem("usuario")
    return ctx.dados.origem


def estrutura_tag(ctx, rt):
    e, r = rt.entradas, rt.resultado
    envelope = None
    if r is not None:
        envelope = dimensionamento.estrutura(e.equipamento, e.metodo, e.case_set(), r, origem_entrada(ctx, rt))
        envelope["varredura"] = dimensionamento.linhas_varredura(e.metodo, r)
        envelope["rastros"] = {n: [asdict(x) for x in c.trace] for n, c in zip(r.case_names, r.per_case)}
    bot = not e.avulso
    return _limpar({
        "schema_version": ESQUEMA,
        "proveniencia": {"arquivo": ctx.dados.origem if bot else None, "sha256": ctx.dados.sha256 if bot else None,
                         "fpso_siz": __version__, "propriedades": ctx.versoes,
                         "propostas": ({"arquivo": ctx.propostas.arquivo, "sha256": ctx.propostas.sha256}
                                       if ctx.propostas else None)},
        "tag": asdict(e.tag), "avulso": e.avulso, "modo": e.modo, "status": rt.status, "preliminar": e.preliminar,
        "premissas": ctx.prem if bot else None,
        "ajustes": canonico_estado(rt.estado, list(e.specs)) if rt.estado is not None else {},
        "limitacoes": limitacoes(ctx.oleo_vivo),
        "blocos_sem_dimensionamento": blocos_sem_dimensionamento(topologia()) if bot else [],
        "fontes_propriedades": fontes_propriedades(),
        "descritores": [asdict(s) for s in e.specs.values()],
        "lacunas": [asdict(l) for l in e.lacunas],
        "revisoes": [asdict(x) for x in e.revisoes()],
        "casos": [{"num": c.num, "nome": c.nome, "ativo": c.ativo, "motivo": c.motivo,
                   "valores": {k: asdict(v) for k, v in c.valores.items()},
                   "insumos": {k: asdict(v) for k, v in c.insumos.items()},
                   "rastro": [asdict(x) for x in c.rastro], "avisos": c.avisos} for c in e.casos],
        "envelope": envelope,
    })


def gravar_tag(ctx, rt, pasta):
    """<id>.json e <id>_varredura.csv (só o cabeçalho, se não há envelope)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    ident, m = rt.tag.tag, rt.entradas.metodo
    arq_json, arq_csv = pasta / f"{ident}.json", pasta / f"{ident}{SUFIXO_VARREDURA}"
    escrever_json(estrutura_tag(ctx, rt), arq_json)
    colunas = [{"id": c.label} for c in m.sweep_columns()] + [{"id": k} for k in dimensionamento.COLUNAS_FIXAS]
    linhas = dimensionamento.linhas_varredura(m, rt.resultado) if rt.resultado is not None else []
    escrever_csv(colunas, linhas, arq_csv)
    return [arq_json, arq_csv]


def linhas(resultados):
    out = []
    for t in resultados:
        r, m = t.resultado, t.entradas.metodo
        out.append(dict(zip(COLUNAS, (t.tag.tag, t.tag.equipamento,
            r.x if r else None, m.sweep_columns()[0].label,
            r.y if r else None, m.requirement_spec()[1], r.driver_case if r else "", t.status))))
    return _limpar(out)


def gravar(planta, pasta):
    """Os artefatos de cada TAG (mesmo serializador do TAG isolado) e planta.csv."""
    pasta = Path(pasta)
    arquivos = []
    for t in planta.tags:
        arquivos += gravar_tag(planta.contexto, t, pasta)
    caminho = pasta / "planta.csv"
    escrever_csv([{"id": k} for k in COLUNAS], linhas(planta.tags), caminho)
    return [*arquivos, caminho]
