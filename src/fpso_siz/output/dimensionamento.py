"""Saída estruturada de um dimensionamento: JSON (entrada, cartão, casos) e CSV da
varredura. Genérica: itera os descritores do método (result_fields, sweep_columns) e nunca
nomeia grandeza. NaN/Inf viram null (JSON estrito)."""
import math
from pathlib import Path

from fpso_siz.core.casos import Interval
from fpso_siz.core.contrato import column_value
from fpso_siz.core.motor import governing_summary
from fpso_siz.output.arquivos import escrever_csv, escrever_json

ARQ_JSON = "dimensionamento.json"
ARQ_CSV = "varredura.csv"
COLUNAS_FIXAS = ("governante", "caso_governante", "admissivel")


def _num(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def _entrada(v):
    return [v.lo, v.hi] if isinstance(v, Interval) else v


def estrutura(eq, m, casos, r, origem):
    folgas = list(r.slack) + [None] * (len(r.case_names) - len(r.slack))
    return {
        "equipamento": {"id": eq.method_id, "rotulo": eq.label},
        "metodo": {"id": m.method_id, "rotulo": m.label,
                   "referencia": getattr(m, "method_reference", lambda: "")()},
        "entrada": {"origem": origem,
                    "casos": [{"nome": c.name, "ativo": c.enabled,
                               "valores": {k: _entrada(v) for k, v in c.values.items()}} for c in casos.cases]},
        "resultado": {
            "viavel": r.feasible, "mensagem": r.message, "resumo": governing_summary(m, r),
            "x": _num(r.x), "y": _num(r.y), "governante": r.governing, "caso_governante": r.driver_case,
            "teto": _num(r.ceiling), "caso_teto": r.ceiling_case, "mecanismo_teto": r.ceiling_mechanism,
            "derivados": {k: _num(v) for k, v in r.derivados.items()},
            "cartao": [{"rotulo": f.label, "valor": _num(f.value), "unidade": f.unit, "status": f.status}
                       for f in m.result_fields(r)],
        },
        "casos": [{"nome": n, "viavel": pc.feasible, "mensagem": pc.message, "x": _num(pc.x), "y": _num(pc.y),
                   "governante": pc.governing, "folga": _num(f)}
                  for n, pc, f in zip(r.case_names, r.per_case, folgas)],
    }


def linhas_varredura(m, r):
    cols = m.sweep_columns()
    return [{**{c.label: _num(column_value(row, c)) for c in cols},
             **dict(zip(COLUNAS_FIXAS, (row.governing, row.driver_case, row.ok)))} for row in r.rows]


def gravar(eq, m, casos, r, pasta, origem):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    escrever_json(estrutura(eq, m, casos, r, origem), pasta / ARQ_JSON)
    colunas = [{"id": c.label} for c in m.sweep_columns()] + [{"id": k} for k in COLUNAS_FIXAS]
    escrever_csv(colunas, linhas_varredura(m, r), pasta / ARQ_CSV)
    return [pasta / ARQ_JSON, pasta / ARQ_CSV]
