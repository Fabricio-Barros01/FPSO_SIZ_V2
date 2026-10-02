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


def _tags_da_integracao():
    """(TAG recuperador, TAGs que consomem carga residual) — declarados em TOML."""
    from fpso_siz.pfd import integracao_termica as integracao
    c = integracao.cfg()
    return c["tag_recuperador"], tuple(l["tag_residual"] for l in c["lado"])


def estrutura_integracao(ctx):
    """Integração térmica REALIZADA (ADR 0005), caso a caso: alvo do Pinch, carga realizada,
    temperaturas de saída e utilidades residuais. Leitura, não cálculo: vem de
    `pfd/integracao.py`, que é quem dimensiona o recuperador no ponto fixo."""
    from fpso_siz.pfd import integracao_termica as integracao
    i = ctx.integracao
    recuperador, residuais = _tags_da_integracao()
    return _limpar({
        "tag_recuperador": recuperador, "tags_residuais": list(residuais),
        "aplicavel": i.aplicavel, "motivo": i.motivo, "cenario": i.cenario, "valida": i.valida,
        "ponto_fixo": {"iteracoes": i.iteracoes, "convergiu": i.convergiu, "desvio_K": i.desvio_K,
                       "tolerancia_K": float(integracao.cfg()["iteracao"]["tolerancia_K"])},
        "fonte": integracao.cfg()["fonte"],
        "total": {"alvo": i.q_alvo_total, "realizado": i.q_realizado_total,
                  "nao_recuperado": i.q_alvo_total - i.q_realizado_total},
        "casos": [{
            "num": c.num, "nome": c.nome, "ativo": c.ativo, "motivo": c.motivo,
            "estado_rating": c.estado_rating, "dimensiona": c.dimensionante,
            "carga_alvo_kW": c.q_alvo, "carga_realizada_kW": c.q_realizado,
            "carga_nao_recuperada_kW": c.q_nao_recuperado, "fracao_realizada": c.fracao_realizada,
            "lados": [{
                "id": l.id, "rotulo": l.rotulo, "capacidade_kW_K": l.capacidade,
                "t_entrada_C": l.t_in, "t_saida_alvo_C": l.t_out_alvo, "t_saida_realizada_C": l.t_out_real,
                "t_destino_premissa_C": l.t_destino, "carga_residual": l.carga_residual,
                "tag_residual": l.tag_residual,
                "carga_preliminar_kW": l.q_residual_preliminar, "carga_residual_kW": l.q_residual,
                "destino_alterado": l.destino_cruzado} for l in c.lados],
            "operacao": {k: v for k, v in (c.operacao or {}).items()
                         if isinstance(v, (int, float, bool, str))},
            "avisos": list(c.avisos)} for c in i.casos],
    })


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
        "limitacoes": limitacoes(),
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
        # O TAG que recupera calor e os que consomem a carga residual carregam a integração
        # térmica realizada: é ela que explica por que a carga deste TAG não é a do balanço
        # preliminar. Nos outros TAGs o campo não existe — eles não participam dela.
        "integracao_termica": (estrutura_integracao(ctx) if bot and rt.tag.tag in
                               (_tags_da_integracao()[0], *_tags_da_integracao()[1]) else None),
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


ARQ_INTEGRACAO = "integracao_termica.json"
COLUNAS_INTEGRACAO = ("caso", "nome", "ativo", "estado_rating", "carga_alvo_kW", "carga_realizada_kW",
                      "carga_nao_recuperada_kW", "fracao_realizada", "t_frio_saida_alvo_C",
                      "t_frio_saida_realizada_C", "t_quente_saida_alvo_C", "t_quente_saida_realizada_C",
                      "utilidade_quente_preliminar_kW", "utilidade_quente_residual_kW",
                      "utilidade_fria_preliminar_kW", "utilidade_fria_residual_kW", "dp_kPa", "v_m_s",
                      "reynolds", "u_W_m2K")


def linhas_integracao(estrutura):
    """Uma linha por caso do BOT: alvo do Pinch, realizado, temperaturas e utilidades."""
    out = []
    for c in estrutura["casos"]:
        frio = next((l for l in c["lados"] if l["id"] == "tubo"), {})
        quente = next((l for l in c["lados"] if l["id"] == "casco"), {})
        op = c.get("operacao") or {}
        out.append(dict(zip(COLUNAS_INTEGRACAO, (
            c["num"], c["nome"], c["ativo"], c["estado_rating"], c["carga_alvo_kW"],
            c["carga_realizada_kW"], c["carga_nao_recuperada_kW"], c["fracao_realizada"],
            frio.get("t_saida_alvo_C"), frio.get("t_saida_realizada_C"),
            quente.get("t_saida_alvo_C"), quente.get("t_saida_realizada_C"),
            frio.get("carga_preliminar_kW"), frio.get("carga_residual_kW"),
            quente.get("carga_preliminar_kW"), quente.get("carga_residual_kW"),
            op.get("dp"), op.get("v"), op.get("re"), op.get("u")))))
    return _limpar(out)


def gravar(planta, pasta):
    """Os artefatos de cada TAG (mesmo serializador do TAG isolado), planta.csv e a integração
    térmica realizada (JSON + CSV dos 16 casos)."""
    pasta = Path(pasta)
    arquivos = []
    for t in planta.tags:
        arquivos += gravar_tag(planta.contexto, t, pasta)
    caminho = pasta / "planta.csv"
    escrever_csv([{"id": k} for k in COLUNAS], linhas(planta.tags), caminho)
    arquivos.append(caminho)
    integ = estrutura_integracao(planta.contexto)
    arq_json = pasta / ARQ_INTEGRACAO
    escrever_json(integ, arq_json)
    arq_csv = pasta / "integracao_termica.csv"
    escrever_csv([{"id": k} for k in COLUNAS_INTEGRACAO], linhas_integracao(integ), arq_csv)
    return [*arquivos, arq_json, arq_csv]
