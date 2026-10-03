"""Pacote de dados para montar ou atualizar o modelo no HYSYS (config/pfd/hysys.toml, nota 47).

Só consolida o que já foi calculado — o estado operacional do balanço (depois do rating do
P-001), o serviço por TAG e, se houver, a comparação de configurações — em `hysys.json` e três
CSVs (correntes, cargas e equipamentos). Nenhuma grandeza nova, nenhuma conversão para os
componentes do HYSYS, nenhuma importação automática. A apresentação não nomeia TAG, corrente nem
parâmetro: itera a topologia, os TAGs da planta e os `ResultField` de cada método.
"""
from dataclasses import asdict
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.balanco.balancos import topologia
from fpso_siz.balanco.dados import descritores_premissas
from fpso_siz.balanco.exportacao import cargas, colunas_correntes, tabela_correntes, termodinamica
from fpso_siz.core.configuracao import carregar
from fpso_siz.output.arquivos import escrever_csv, escrever_json
from fpso_siz.output.pfd import _limpar
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd.entradas import PROPOSTA
from fpso_siz.pfd.equipamento import areas_troca

COLUNAS_EQUIPAMENTOS = ("tag", "equipamento", "bloco", "metodo", "status", "etapa_balanco",
                        "unidades_em_operacao", "unidades_reserva", "area_por_unidade_m2", "area_em_operacao_m2",
                        "area_instalada_m2", "origem_geometria", "restricoes", "decisoes_pendentes",
                        "verificacoes_incompletas", "limitacoes_aceitas", "valores_propostos")


def cfg():
    return carregar("pfd/hysys.toml")


def _geometria(rt):
    """A geometria que o TAG publica: a instalada (rating) ou os campos do envelope DESIGN."""
    op = rt.operacao
    if op is not None and op.geometria is not None:
        return {"origem": "geometria_instalada", **asdict(op.geometria), **op.geometria_derivada}
    r = rt.resultado
    if r is None or not r.feasible:
        return None
    return {"origem": "envelope_design",
            "campos": [{"rotulo": f.label, "valor": f.value, "unidade": f.unit}
                       for f in rt.entradas.metodo.result_fields(r)]}


def _propostos(rt):
    """Chaves cujo valor veio das propostas para lacunas (não confirmado pelo usuário)."""
    return sorted({k for c in rt.entradas.casos for k, v in c.valores.items() if v.origem == PROPOSTA})


def _classificacao(rt):
    return {"restricoes": list(rt.restricoes), "decisoes_pendentes": list(rt.decisoes_pendentes),
            "verificacoes_incompletas": list(rt.verificacoes_incompletas),
            "limitacoes_aceitas": list(rt.limitacoes_aceitas)}


def _equipamento(rt):
    t = rt.tag
    return {"tag": t.tag, "nome": t.nome, "equipamento": t.equipamento, "bloco": t.bloco, "metodo": t.metodo,
            "status": rt.status, "etapa_balanco": rt.etapa_balanco or None,
            "geometria": _geometria(rt), "areas": areas_troca(rt), "classificacao": _classificacao(rt),
            "valores_propostos": _propostos(rt),
            # rating da geometria instalada por caso: UA, U, F, ΔT_lm, h, velocidades e perdas de
            # carga, com a classificação (atende / alerta / não avaliado, e o motivo de cada lacuna)
            "operacao": rt.operacao.estrutura() if rt.operacao is not None else None}


def _linha_equipamento(rt):
    a = areas_troca(rt) or {}
    g = _geometria(rt) or {}
    c = _classificacao(rt)
    return dict(zip(COLUNAS_EQUIPAMENTOS, (
        rt.tag.tag, rt.tag.equipamento, rt.tag.bloco, rt.tag.metodo, rt.status, rt.etapa_balanco or None,
        a.get("unidades_em_operacao"), a.get("unidades_reserva"), a.get("por_unidade_m2"), a.get("em_operacao_m2"),
        a.get("instalada_m2"), g.get("origem"), "; ".join(c["restricoes"]), "; ".join(c["decisoes_pendentes"]),
        "; ".join(c["verificacoes_incompletas"]), "; ".join(c["limitacoes_aceitas"]), "; ".join(_propostos(rt)))))


def _cargas(planta):
    """Uma linha por caso e etapa: as cargas e potências do balanço preliminar e do estado
    operacional (o que P-002 e P-003 recebem depois do rating)."""
    return [{"caso": r.num, "etapa": r.etapa, **cargas(r)}
            for estados in (planta.balanco, planta.balanco_operacional) for r in estados]


def _comparacao(c):
    """Os candidatos avaliados, com a classificação e os motivos; o domínio inteiro e o que o
    limite deixou de fora. Comparação por dominância, sem pesos."""
    if c is None:
        return None
    ids_var = [v["id"] for v in ot.variaveis(c.sub)]
    frente = {a.x for a in c.frente()}
    return {"subproblema": c.sub, "rotulo": ot.subproblema(c.sub)["rotulo"],
            "variaveis": [{k: v.get(k) for k in ("id", "rotulo", "tipo", "min", "max", "fonte")}
                          for v in ot.variaveis(c.sub)],
            "objetivos": [{k: o.get(k) for k in ("id", "rotulo", "unidade", "sentido", "fonte")}
                          for o in ot.objetivos(c.sub)],
            "criterio": "dominância de Pareto entre candidatos admissíveis (sem violação); sem pesos e sem "
                        "soma de grandezas de unidades diferentes",
            "limite_avaliacoes": c.limite, "limite_atingido": c.limite_atingido,
            "dominio": [dict(zip(ids_var, x)) for x in c.dominio],
            "nao_avaliados": [dict(zip(ids_var, x)) for x in c.nao_avaliados],
            "candidatos": [{"x": dict(zip(ids_var, a.x)), "referencia": i == 0, "situacao": a.situacao,
                            "admissivel": a.admissivel, "nao_dominado": a.x in frente,
                            "objetivos": a.objetivos, "violacoes": {k: g for k, g in a.restricoes.items() if g > 0},
                            "motivos": a.motivos(), "limitacoes_aceitas": a.limitacoes, "estados": a.estados}
                           for i, a in enumerate(c.avaliacoes)]}


def estrutura(planta, comparacao=None):
    """O pacote como dados puros (JSON estrito: NaN/Inf viram null)."""
    ctx, c = planta.contexto, cfg()
    base = {d["nome"]: d for d in descritores_premissas(ctx.dados)}
    estados = planta.balanco_operacional
    topo = topologia()
    tag_do_bloco = {rt.tag.bloco: rt.tag.tag for rt in planta.tags}
    return _limpar({
        "esquema": c["esquema"], "avisos": list(c["avisos"]),
        "proveniencia": {"fpso_siz": __version__, "arquivo_casos": ctx.dados.origem, "sha256": ctx.dados.sha256,
                         "propostas": ({"arquivo": ctx.propostas.arquivo, "sha256": ctx.propostas.sha256}
                                       if ctx.propostas else None),
                         "propriedades": ctx.versoes, "etapa_dos_estados": sorted({r.etapa for r in estados})},
        "condicoes_padrao": ctx.dados.bruto.get("standard_conditions"),
        "premissas": [dict(d, valor=ctx.prem[nome], alterada=ctx.prem[nome] != d["valor"]) for nome, d in base.items()],
        "casos": [{"num": r.num, "nome": r.caso.get("name", ""), "fluido": r.fluid, "poco": r.well, "api": r.api,
                   "etapa": r.etapa, "convergiu": r.convergiu, "termodinamica": termodinamica(r)} for r in estados],
        "caracterizacao_fracoes_plus": ctx.dados.bruto.get("c20_pseudo"),
        "topologia": {"entradas_globais": topo["global_in"], "saidas_globais": topo["global_out"],
                      "correntes": topo["correntes"],
                      "blocos": [dict(b, tag=tag_do_bloco.get(b["id"])) for b in topo["blocos"]]},
        "equipamentos": [_equipamento(rt) for rt in planta.tags],
        "comparacao": _comparacao(comparacao),
        "dados_faltantes": [dict(f) for f in c["faltante"]],
    })


def gravar(planta, pasta, comparacao=None):
    """hysys.json, hysys_correntes.csv (caso × corrente, estado operacional), hysys_cargas.csv
    (caso × etapa) e hysys_equipamentos.csv (um TAG por linha)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arq = {n: pasta / n for n in ("hysys.json", "hysys_correntes.csv", "hysys_cargas.csv", "hysys_equipamentos.csv")}
    escrever_json(estrutura(planta, comparacao), arq["hysys.json"])
    escrever_csv(colunas_correntes(), _limpar(tabela_correntes(planta.balanco_operacional)), arq["hysys_correntes.csv"])
    linhas_cargas = _limpar(_cargas(planta))
    escrever_csv([{"id": k} for k in linhas_cargas[0]], linhas_cargas, arq["hysys_cargas.csv"])
    escrever_csv([{"id": k} for k in COLUNAS_EQUIPAMENTOS], _limpar([_linha_equipamento(rt) for rt in planta.tags]),
                 arq["hysys_equipamentos.csv"])
    return list(arq.values())
