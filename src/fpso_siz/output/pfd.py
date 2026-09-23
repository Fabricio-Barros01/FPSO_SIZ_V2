"""JSON por TAG e planta.csv, a partir das entradas rastreadas e dos envelopes.

JSON estrito: NaN/Inf viram null. A origem e o estado distinguem lacuna, caso inativo e
inviabilidade. A apresentação não conhece os nomes dos parâmetros dos métodos.
"""
import math
from dataclasses import asdict
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.output import dimensionamento
from fpso_siz.output.arquivos import escrever_csv, escrever_json
from fpso_siz.pfd import fluidos
from fpso_siz.pfd.entradas import cfg

COLUNAS = ("tag", "equipamento", "x", "eixo_x", "y", "unidade_y", "caso_governante", "status")


def _limpar(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _limpar(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_limpar(v) for v in obj]
    return obj


def estrutura(planta, tag):
    e, r = tag.entradas, tag.resultado
    envelope = None
    if r is not None:
        envelope = dimensionamento.estrutura(e.equipamento, e.metodo, e.case_set(), r, planta.dados.origem)
        envelope["varredura"] = dimensionamento.linhas_varredura(e.metodo, r)
        envelope["rastros"] = {n: [asdict(x) for x in c.trace] for n, c in zip(r.case_names, r.per_case)}
    return _limpar({
        "schema_version": 1,
        "proveniencia": {"arquivo": planta.dados.origem, "sha256": planta.dados.sha256,
                         "fpso_siz": __version__, "propriedades": planta.versoes},
        "tag": asdict(tag.tag), "status": tag.status,
        "premissas": planta.prem, "ajustes": planta.ajustes.get(tag.tag.tag, {}),
        "limitacoes": cfg()["limitacoes"], "blocos_sem_dimensionamento": planta.sem_dimensionamento,
        "fontes_propriedades": fluidos.cfg(),
        "descritores": [asdict(s) for s in e.specs.values()],
        "lacunas": [asdict(l) for l in e.lacunas],
        "casos": [{"num": c.num, "nome": c.nome, "ativo": c.ativo, "motivo": c.motivo,
                   "valores": {k: asdict(v) for k, v in c.valores.items()},
                   "insumos": {k: asdict(v) for k, v in c.insumos.items()},
                   "rastro": [asdict(x) for x in c.rastro], "avisos": c.avisos} for c in e.casos],
        "envelope": envelope,
    })


def linhas(planta):
    out = []
    for t in planta.tags:
        r, m = t.resultado, t.entradas.metodo
        out.append(dict(zip(COLUNAS, (t.tag.tag, t.tag.equipamento,
            r.x if r else None, m.sweep_columns()[0].label,
            r.y if r else None, m.requirement_spec()[1], r.driver_case if r else "", t.status))))
    return _limpar(out)


def gravar(planta, pasta):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for t in planta.tags:
        caminho = pasta / f"{t.tag.tag}.json"
        escrever_json(estrutura(planta, t), caminho)
        arquivos.append(caminho)
    caminho = pasta / "planta.csv"
    escrever_csv([{"id": k} for k in COLUNAS], linhas(planta), caminho)
    return [*arquivos, caminho]
