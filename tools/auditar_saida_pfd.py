"""Gate de sanidade do dimensionamento e dos memoriais (fim de fase).

Roda o dimensionamento REAL dos TAGs pelo mesmo fluxo do usuário (`pfd/planta.py` →
`pfd/equipamento.py` → `core/motor.py`), grava os mesmos artefatos que `fpso-siz pfd
--mc` grava (`output/pfd.py` e `output/latex/tag/memorial.py`) numa pasta temporária, e
confere se o que saiu tem significado numérico. Não existe um segundo caminho de
dimensionamento aqui: a auditoria só lê o que o fluxo de produção produziu.

Três níveis são comparados, antes de qualquer formatação:

    SizingResult (EnvelopeResult, em memória) → <TAG>.json (núcleo) → <número>.json (MC)

Ausência não é erro por si. Cada `-` do MC é classificado, e a classificação precisa de
uma justificativa POSITIVA vinda do próprio resultado (o mecanismo que o método declara, o
regime que a correlação registrou, a inviabilidade do caso isolado, a equação que não
declara conversão). Travessão sem justificativa reprova:

    NAO_APLICAVEL  o método declara que o critério não se aplica àquele caso
    LACUNA         falta entrada; vira erro se o TAG mesmo assim se diz dimensionado
    INVIAVEL       não há solução, e o MC traz diagnóstico numérico no lugar das dimensões
    ERRO_NUMERICO  resultado necessário não finito, ou fisicamente impossível
    ERRO_OUTPUT    o núcleo tem número e a apresentação perdeu, trocou ou não justificou

Código de saída: 0 sem erro de aceite, 1 com erro de aceite (para rodar automaticamente
ao fim de cada fase), 2 se a própria auditoria não conseguiu rodar.

    uv run python tools/auditar_saida_pfd.py [--casos ARQ] [--saida saida/_auditoria_fase]
"""
import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.output import pfd as saida_pfd
from fpso_siz.output.latex.tag import memorial as saida_mc
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as nucleo
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parent.parent
CASOS_PADRAO = RAIZ / "design_cases_bot.json"
CASOS_FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
SAIDA_PADRAO = RAIZ / "saida" / "_auditoria_fase"

CATEGORIAS = ("NAO_APLICAVEL", "LACUNA", "INVIAVEL", "ERRO_NUMERICO", "ERRO_OUTPUT")
ERROS = ("ERRO_NUMERICO", "ERRO_OUTPUT")

# Grandezas que não admitem valor negativo por construção geométrica ou de transporte. A
# regra é pela UNIDADE do campo do cartão, não pelo nome: a auditoria não cita grandeza.
# Ficam de fora "m", "W" e "kW" porque ali há campos que são diferenças com sinal (folga de
# NPSH) ou fluxos que podem inverter de sentido.
UNIDADES_POSITIVAS = ("mm", "m²", "m³", "m/s", "W/m²K", "K")


# ------------------------------------------------------------------ utilidades
def ausente(v):
    return v is None or (isinstance(v, float) and not math.isfinite(v))


def igual(a, b):
    """Igualdade numérica exata (antes da formatação); ausente == ausente."""
    if ausente(a) or ausente(b):
        return ausente(a) and ausente(b)
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return float(a) == float(b)


def percorrer(obj, pre=""):
    """(caminho, valor) de cada folha, com o índice de cada lista no caminho."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from percorrer(v, f"{pre}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from percorrer(v, f"{pre}[{i}]")
    else:
        yield pre.lstrip("."), obj


def molde(caminho):
    return re.sub(r"\[\d+\]", "[]", caminho)


def indices(caminho):
    return [int(i) for i in re.findall(r"\[(\d+)\]", caminho)]


def achado(categoria, caminho, detalhe, justificativa=""):
    return dict(categoria=categoria, caminho=caminho, detalhe=detalhe, justificativa=justificativa,
                erro=categoria in ERROS)


# ------------------------------------------------------------------ níveis de resultado por método
def niveis_do_metodo(m, r):
    """Classificação dos resultados do método, derivada dos contratos que já existem —
    nada é redeclarado: `ResultField.highlight` marca o principal, `memorial_tag.toml`
    declara o que o MC é obrigado a apresentar, e o resto é diagnóstico.

    principal    dimensiona o equipamento; em TAG dimensionado tem de ser finito
    memorial     o MC apresenta; tem de bater com o núcleo, número a número
    diagnostico  explica o resultado; pode faltar, desde que a falta seja justificada
    """
    conteudo = nucleo.conteudo_metodo(m)
    campos = m.result_fields(r) if r is not None else []
    principal = [f.label for f in campos if f.highlight]
    memorial = [f.label for f in campos if not f.highlight]
    equacoes = [e["titulo"] for e in conteudo.get("equacoes", [])]
    colunas = [c["rotulo"] for c in conteudo.get("colunas_casos", [])]
    diagnostico = sorted(r.derivados) if r is not None else []
    return dict(metodo=m.method_id, rotulo=m.label, principal=principal,
                memorial=dict(cartao=memorial, equacoes=equacoes, colunas_por_caso=colunas),
                diagnostico=dict(derivados=diagnostico, graficos=list(conteudo.get("graficos", []))))


# ------------------------------------------------------------------ justificativa das ausências
class Justificador:
    """Classifica cada ausência do documento do MC. Sem justificativa positiva: ERRO_OUTPUT."""

    def __init__(self, rt, doc):
        self.rt, self.doc = rt, doc
        self.r = rt.resultado
        self.m = rt.entradas.metodo
        self.calc = doc.get("calculo") or {}
        self.equacoes = nucleo.conteudo_metodo(self.m).get("equacoes", [])

    # --- auxiliares
    def _linha(self, caminho):
        i = indices(caminho)
        linhas = self.calc.get("tabela", {}).get("linhas", [])
        return linhas[i[0]] if i and i[0] < len(linhas) else None

    def _caso_serie(self, caminho, chave):
        i = indices(caminho)
        linhas = self.calc.get("series", {}).get(chave, [])
        return linhas[i[0]] if i and i[0] < len(linhas) else None

    # --- classificação
    def classificar(self, caminho, valor):
        regra = getattr(self, "_r_" + molde(caminho).replace("calculo.", "", 1)
                        .replace(".", "_").replace("[]", ""), None)
        if regra is not None:
            resposta = regra(caminho, valor)
            if resposta is not None:
                return achado(resposta[0], caminho, valor, resposta[1])
        return achado("ERRO_OUTPUT", caminho, valor,
                      "ausência sem justificativa declarada pelo método ou pelo resultado")

    def _r_banda(self, caminho, valor):
        if not hasattr(self.m, "banda_memorial"):
            return "NAO_APLICAVEL", f"o método {self.m.method_id} não declara banda (sem hook banda_memorial)"
        return None

    def _r_selecao(self, caminho, valor):
        if not hasattr(self.m, "selecao_memorial"):
            return "NAO_APLICAVEL", f"o método {self.m.method_id} não declara seleção (sem hook selecao_memorial)"
        if not self.r.feasible:
            return "INVIAVEL", "não há ponto escolhido: o envelope é inviável"
        return None

    def _r_diagnostico(self, caminho, valor):
        if self.r.feasible:
            return "NAO_APLICAVEL", "o envelope é viável: não há inviabilidade a diagnosticar"
        return None

    def _r_diagnostico_teto(self, caminho, valor):
        if not self.m.teto_aplicavel(self.r.ceiling_mechanism):
            return "NAO_APLICAVEL", f"nenhum caso impõe teto (mecanismo declarado: {self.r.ceiling_mechanism})"
        return None

    def _r_diagnostico_x_min_banda(self, caminho, valor):
        if not self.r.rows:
            return "INVIAVEL", "o motor parou na preparação de um caso: não houve varredura em que buscar a banda"
        return None

    def _r_indice_governante(self, caminho, valor):
        if not self.r.per_case:
            return "INVIAVEL", "o motor parou na preparação de um caso: não há caso governante"
        return None

    def _r_x_referencia(self, caminho, valor):
        if not self.r.rows:
            return "INVIAVEL", "o motor parou antes da varredura: não há abscissa de referência"
        return None

    def _r_criterios_valor(self, caminho, valor):
        i = indices(caminho)
        crit = self.calc["criterios"][i[0]]
        if crit.get("atende") is not None and not crit.get("unidade"):
            return "NAO_APLICAVEL", f"critério de existência (atende = {crit['atende']}), sem valor numérico"
        return None

    def _r_resultados_valor(self, caminho, valor):
        if not self.r.feasible:
            return "INVIAVEL", "sem ponto escolhido: o MC traz diagnóstico no lugar das dimensões"
        return None

    def _r_tabela_linhas_teto(self, caminho, valor):
        linha = self._linha(caminho)
        if linha is not None and not linha["teto_aplicavel"]:
            return "NAO_APLICAVEL", f"o caso não impõe teto (mecanismo declarado: {linha['mecanismo_id']})"
        return None

    def _r_tabela_linhas_x_isolado(self, caminho, valor):
        linha = self._linha(caminho)
        if linha is not None and not linha["viavel_isolado"]:
            return "INVIAVEL", "o caso não tem solução nem isolado"
        return None

    def _r_tabela_linhas_folga(self, caminho, valor):
        if not self.r.feasible:
            return "INVIAVEL", "sem ponto escolhido: não há folga a medir"
        return None

    def _r_tabela_linhas_valores(self, caminho, valor):
        linha = self._linha(caminho)
        if linha is not None and not linha["criterio_aplicavel"]:
            return "NAO_APLICAVEL", f"o método declara o critério não aplicável ao caso ({linha['mecanismo_id']})"
        return None

    def _r_series_casos_teto(self, caminho, valor):
        linha = self._caso_serie(caminho, "casos")
        i = indices(caminho)
        linhas = self.calc.get("tabela", {}).get("linhas", [])
        tab = linhas[i[0]] if linha is not None and i[0] < len(linhas) else None
        if tab is not None and not tab["teto_aplicavel"]:
            return "NAO_APLICAVEL", f"o caso não impõe teto (mecanismo declarado: {tab['mecanismo_id']})"
        return None

    def _r_series_operacao_peso_transicao(self, caminho, valor):
        op = self._caso_serie(caminho, "operacao")
        if op is not None and op.get("regime") and op["regime"] != "transicao":
            return "NAO_APLICAVEL", f"regime {op['regime']}: não há interpolação de transição a ponderar"
        return None

    def _r_equacoes_conversao(self, caminho, valor):
        i = indices(caminho)
        eq = self.calc["equacoes"][i[0]]
        declarada = next((e for e in self.equacoes if e["id"] == eq["id"]), {})
        if "conversao" not in declarada:
            return "NAO_APLICAVEL", f"a equação «{eq['id']}» não declara conversão de constante de campo"
        return None

    def _r_equacoes_rastro(self, caminho, valor):
        i = indices(caminho)
        eq = self.calc["equacoes"][i[0]]
        declarada = next((e for e in self.equacoes if e["id"] == eq["id"]), {})
        if declarada.get("fonte_dados") == nucleo.SELECAO:
            return "NAO_APLICAVEL", (f"a equação «{eq['id']}» lê o ponto escolhido do envelope, "
                                     "não uma entrada do rastro de um caso")
        return None


# ------------------------------------------------------------------ auditoria de um TAG
def _cartao(m, r):
    return {f.label: f for f in m.result_fields(r)} if r is not None else {}


def _mc_arquivo(pasta, doc):
    return Path(pasta) / saida_mc.PASTA_MC / saida_mc.nome_base(doc) / f"{saida_mc.nome_base(doc)}.json"


def auditar_tag(ctx, rt, pasta):
    """(linha do resumo, achados) de um TAG, sobre os artefatos que o fluxo real gravou."""
    tag, status = rt.tag.tag, rt.status
    r, m = rt.resultado, rt.entradas.metodo
    achados = []

    saida_pfd.gravar_tag(ctx, rt, pasta)
    saida_mc.exportar(ctx, rt, pasta, data="01/01/2000", git=(None, None))
    nucleo_json = json.loads((Path(pasta) / f"{tag}.json").read_text(encoding="utf-8"))
    doc = nucleo.documento(ctx, rt)
    mc_json = json.loads(_mc_arquivo(pasta, doc).read_text(encoding="utf-8"))

    # --- o estado tem de ser o que as entradas sustentam
    lacunas = [x.chave for x in rt.entradas.lacunas]
    if status == servico.DIMENSIONADO and lacunas:
        achados.append(dict(achado("LACUNA", "status", lacunas,
                                   "o TAG se diz dimensionado, mas há entrada necessária faltando"), erro=True))
    if status == servico.AGUARDANDO and not lacunas:
        achados.append(achado("ERRO_OUTPUT", "status", status,
                              "o TAG está aguardando entrada e não diz qual entrada falta"))

    envelope = nucleo_json.get("envelope")
    if rt.operacao is not None:
        achados += _conferir_operacao(ctx, rt, nucleo_json, mc_json, pasta)
    elif rt.etapa_balanco and rt.etapa_balanco != ctx.etapa_do_tag(rt.tag):
        achados.append(achado("ERRO_OUTPUT", "etapa_balanco", rt.etapa_balanco,
                              "o TAG foi preparado de uma etapa do balanço diferente da do estado operacional"))
    achados += _conferir_continuidade(ctx, rt, mc_json)
    achados += _conferir_metodologia(rt, doc, pasta)
    cartao = _cartao(m, r)
    if status == servico.DIMENSIONADO and rt.operacao is None:
        achados += _conferir_dimensionado(rt, cartao)
    elif status == servico.INVIAVEL:
        achados += _conferir_inviavel(rt, doc)

    # --- todo travessão do MC precisa de classificação
    if doc.get("calculo"):
        just = Justificador(rt, doc)
        for caminho, valor in percorrer(doc["calculo"], "calculo"):
            if ausente(valor):
                achados.append(just.classificar(caminho, valor))

    # --- os três níveis têm de trazer o mesmo número
    if envelope is not None:
        achados += _conferir_niveis(rt, cartao, envelope, mc_json)

    planta = next((li for li in saida_pfd.linhas([rt])), {})
    principais = {f.label: f.value for f in cartao.values() if f.highlight}
    if rt.operacao is not None and rt.operacao.geometria is not None:
        # a geometria instalada (a do rating) é o resultado principal do P-001 integrado
        principais = {"tubos por passe (instalado)": planta.get("x"), "comprimento do tubo (instalado)": planta.get("y")}
    linha = dict(tag=tag, equipamento=rt.tag.equipamento, metodo=m.method_id, status=status,
                 viavel=bool(r.feasible) if r is not None else (status == servico.DIMENSIONADO),
                 caso_governante=planta.get("caso_governante") or "",
                 principais=principais, x=planta.get("x"), y=planta.get("y"), restricoes=list(rt.restricoes),
                 decisoes_pendentes=list(rt.decisoes_pendentes),
                 ausentes=sorted({a["caminho"] for a in achados
                                  if a["caminho"].startswith(("calculo.", "cartao["))}),
                 lacunas=lacunas, avisos=[t for t, _ in rt.entradas.avisos()],
                 mc_consistente=not any(a["erro"] for a in achados),
                 niveis=niveis_do_metodo(m, r))
    return linha, [dict(a, tag=tag) for a in achados]


def _conferir_operacao(ctx, rt, nucleo_json, mc_json, pasta):
    """P-001 integrado: uma geometria só (sem envelope DESIGN paralelo), a mesma estrutura no
    resultado, no JSON e no MC, o CSV de operação igual ao resultado, o estado operacional igual
    ao que P-002/P-003 leem, e toda ausência com motivo e status de não avaliada."""
    achados = []
    op = rt.operacao
    esperado = op.estrutura()
    if nucleo_json.get("operacao_integrada") != esperado or mc_json.get("operacao_integrada") != esperado:
        achados.append(achado("ERRO_OUTPUT", "operacao_integrada", None,
                              "rating integrado do P-001 diverge entre resultado, JSON e memorial"))
    if nucleo_json.get("envelope") is not None or rt.resultado is not None:
        achados.append(achado("ERRO_OUTPUT", "envelope", None,
                              "o P-001 integrado não pode apresentar um envelope DESIGN paralelo à geometria do rating"))
    csv_op = Path(pasta) / f"{rt.tag.tag}_operacao.csv"
    with csv_op.open(encoding="utf-8", newline="") as f:
        lidas = list(csv.DictReader(f))
    for li, ref in zip(lidas, saida_pfd.linhas_operacao(op)):
        for k, v in ref.items():
            if isinstance(v, float) and not igual(float(li[k]), v):
                achados.append(achado("ERRO_OUTPUT", f"operacao_csv[{ref['num']}].{k}", (li[k], v),
                                      "o CSV de operação não reproduz o resultado"))
    if op.geometria is None:
        return achados
    g = op.geometria
    for nome, v in (("tubos_por_passe", g.tubos_por_passe), ("comprimento_tubo", g.comprimento_tubo),
                    ("area_unitaria", g.area_unitaria)):
        if not math.isfinite(v) or v <= 0:
            achados.append(achado("ERRO_NUMERICO", f"geometria.{nome}", v, "dimensão instalada não positiva"))
    operacional = {r.num: r for r in ctx.balanco_operacional()}
    for caso in op.casos:
        balan = operacional[caso.num]
        if not all(igual(a, b) for a, b in ((caso.Q_real, balan.duties["Q_pre"]),
                                            (caso.q_p002, balan.duties["Q_H"]),
                                            (caso.q_p003, balan.duties["Q_C"]),
                                            (caso.t_fria_out, balan.T["C-07"]),
                                            (caso.t_quente_out, balan.T["C-23"]))):
            achados.append(achado("ERRO_OUTPUT", f"operacao_integrada.caso[{caso.num}]", None,
                                  "cargas ou temperaturas não foram propagadas ao balanço produtivo"))
        for crit in caso.hidraulico.get("criterios", []):
            if crit["valor"] is None or (isinstance(crit["valor"], float) and not math.isfinite(crit["valor"])):
                if crit["status"] not in (servico.NAO_AVALIADO, servico.NAO_APLICAVEL) or not crit["motivo"]:
                    achados.append(achado("ERRO_OUTPUT", f"operacao.caso[{caso.num}].{crit['criterio']}", None,
                                          "valor ausente sem status de não avaliado e sem motivo"))
                else:
                    achados.append(achado("NAO_APLICAVEL", f"operacao.caso[{caso.num}].{crit['criterio']}", None,
                                          crit["motivo"]))
        achados += _conferir_hidraulica(rt, caso)
    achados += _conferir_premissa_comprimento(op)
    return achados


def _conferir_metodologia(rt, doc, pasta):
    """Só TAG aguardando entrada pode dizer que nenhuma equação foi avaliada (template comum)."""
    if rt.status == servico.AGUARDANDO:
        return []
    tex = _mc_arquivo(pasta, doc).with_suffix(".tex").read_text(encoding="utf-8")
    secao = tex.split("\\section{Metodologia}")[1].split("\\section")[0]
    if saida_mc.cfg()["textos"]["aguardando"] in secao:
        return [achado("ERRO_OUTPUT", "memorial.metodologia", rt.status,
                       "o MC apresenta a metodologia como de TAG aguardando entrada, e o TAG não está")]
    return []


def _conferir_hidraulica(rt, caso):
    """Atividade térmica ≠ passagem de vazão; atendimento ≠ completude; ausência ≠ aprovação."""
    achados, h, d = [], caso.hidraulico, caso.diagnosticos
    onde = f"operacao.caso[{caso.num}].hidraulico"
    com_vazao = (d.get("vazao_tubo_kg_s") or 0) > 0 or (d.get("vazao_casco_kg_s") or 0) > 0
    if com_vazao and h.get("atendimento") == servico.NAO_APLICAVEL:
        achados.append(achado("ERRO_OUTPUT", onde, caso.termico.get("status"),
                              "caso com vazão classificado como hidraulicamente não aplicável"))
    criterios = h.get("criterios", [])
    lacunas = [c for c in criterios if c["obrigatorio"] and (c["status"] in (servico.NAO_AVALIADO, servico.SEM_CRITERIO)
                                                           or c["natureza"] == servico.ESTIMATIVA_INDICATIVA)]
    if h.get("atendimento") != servico.NAO_APLICAVEL:
        if lacunas and h.get("completude") != servico.INCOMPLETA:
            achados.append(achado("ERRO_OUTPUT", onde, h.get("completude"),
                                  "há grandeza ausente, sem critério ou estimada, e a verificação se diz completa"))
        if h.get("atendimento") == servico.ATENDE and any(c["status"] == servico.NAO_ATENDE and c["com_limite"]
                                                          for c in criterios):
            achados.append(achado("ERRO_OUTPUT", onde, h.get("atendimento"),
                                  "resumo 'atende' com critério vigente não atendido"))
        if any(c["status"] == servico.ATENDE and not c["com_limite"] for c in criterios):
            achados.append(achado("ERRO_OUTPUT", onde, None, "grandeza sem limite vigente classificada como atendida"))
    rho = rt.entradas.caso(caso.num).auxiliares["rho_casco"].valor
    if not igual(d.get("rho_casco_kg_m3"), rho if math.isfinite(rho) else None):
        achados.append(achado("ERRO_OUTPUT", f"operacao.caso[{caso.num}].rho_casco", d.get("rho_casco_kg_m3"),
                              "ρ do casco do rating difere da ρ da corrente do casco"))
    return achados


def _conferir_premissa_comprimento(op):
    """A premissa de comprimento é UMA: a busca, a classificação e o memorial a leem igual."""
    achados, pc = [], op.premissa_comprimento
    if op.geometria is None:
        return achados
    crit = next(r for r in op.restricoes_geometricas if r["criterio"] == "comprimento_tubo")
    if not igual(crit["limite"], pc["limite_m"]):
        achados.append(achado("ERRO_OUTPUT", "premissa_comprimento", (crit["limite"], pc["limite_m"]),
                              "a classificação usou um limite de comprimento diferente da premissa efetiva"))
    if pc["aplicado_na_busca"] and op.geometria.comprimento_tubo > pc["limite_m"]:
        achados.append(achado("ERRO_OUTPUT", "premissa_comprimento", op.geometria.comprimento_tubo,
                              "limite do projeto aplicado na busca, e a geometria selecionada o excede"))
    if pc["estado"] == "divergente" and crit["status"] in (servico.ATENDE, servico.NAO_ATENDE):
        achados.append(achado("ERRO_OUTPUT", "premissa_comprimento", crit["status"],
                              "premissa indefinida (default do método × domínio da busca) tratada como aprovada/reprovada"))
    return achados


def _conferir_continuidade(ctx, rt, mc_json):
    """Os MC do P-001 e dos TAGs dependentes rastreiam preliminar → pós-rating com os estados de
    fato usados: a seção existe, e cada antes/depois é o do estado preliminar/operacional."""
    achados = []
    dependente = servico.depende_do_rating(rt.tag) and rt.etapa_balanco == servico.ETAPA_RATING
    if rt.operacao is None and not dependente:
        return achados
    if rt.operacao is not None and rt.operacao.geometria is None:
        return achados
    ct = mc_json.get("continuidade")
    if not ct:
        return [achado("ERRO_OUTPUT", "continuidade", None,
                       "MC sem a rastreabilidade balanço preliminar → rating do P-001")]
    preliminar = {r.num: r for r in ctx.balanco}
    operacional = {r.num: r for r in ctx.balanco_operacional()}
    for li in ct["linhas"]:
        pre, pos = preliminar[li["num"]], operacional[li["num"]]
        for g, v in zip(ct["grandezas"], li["valores"]):
            fonte = (lambda e: e.T[g["id"]]) if g["tipo"] == "temperatura" else (lambda e: e.duties[g["id"]])
            if not (igual(v["pre"], fonte(pre)) and igual(v["pos"], fonte(pos))):
                achados.append(achado("ERRO_OUTPUT", f"continuidade[{li['num']}].{g['id']}", (v["pre"], v["pos"]),
                                      "o MC não reproduz o preliminar e o pós-rating dos estados usados"))
    if not ct["fechamento"]["atende"]:
        achados.append(achado("ERRO_NUMERICO", "continuidade.fechamento", ct["fechamento"],
                              "o estado operacional não fecha massa/energia na tolerância do balanço"))
    return achados


def _conferir_dimensionado(rt, cartao):
    """Num TAG dimensionado: principal finito, cartão finito e nada fisicamente impossível.

    A única ausência tolerada no cartão é a que o método DECLARA em `campos_nao_aplicaveis`
    — e nem essa vale para um resultado principal, que é o que dimensiona o equipamento."""
    r, m = rt.resultado, rt.entradas.metodo
    declarados = m.campos_nao_aplicaveis(r)
    achados = []
    for rotulo, f in cartao.items():
        if isinstance(f.value, str):
            continue
        if not math.isfinite(f.value):
            if rotulo in declarados and not f.highlight:
                achados.append(achado("NAO_APLICAVEL", f"cartao[{rotulo}]", f.value,
                                      f"o método declara o campo como «{declarados[rotulo]}»"))
                continue
            cat = "ERRO_NUMERICO" if f.highlight else "ERRO_OUTPUT"
            achados.append(achado(cat, f"cartao[{rotulo}]", f.value,
                                  "resultado do cartão sem valor finito num TAG dimensionado"))
        elif f.unit in UNIDADES_POSITIVAS and f.value < 0:
            achados.append(achado("ERRO_NUMERICO", f"cartao[{rotulo}]", f.value,
                                  f"grandeza em {f.unit} não admite valor negativo"))
    for nome, v in (("x", r.x), ("y", r.y)):
        if not math.isfinite(v) or v <= 0:
            achados.append(achado("ERRO_NUMERICO", nome, v,
                                  "a dimensão escolhida e a exigência atendida têm de ser positivas"))
    return achados


def _conferir_inviavel(rt, doc):
    """Num TAG inviável não se exige dimensão: exige-se mensagem e diagnóstico numérico."""
    r, calc = rt.resultado, doc.get("calculo") or {}
    achados = []
    if not (r.message or "").strip():
        achados.append(achado("ERRO_OUTPUT", "mensagem", "", "TAG inviável sem mensagem que explique a inviabilidade"))
    diag = calc.get("diagnostico") or {}
    series = calc.get("series") or {}
    numericos = []
    if not ausente(diag.get("teto")):
        numericos.append("teto de decantação")
    if not ausente(diag.get("x_min_banda")):
        numericos.append("menor abscissa na banda")
    if series.get("feixe_proximo"):
        numericos.append("feixe mais próximo de atender")
    for chave, valores in series.items():
        if isinstance(valores, list) and valores and any(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for li in valores if isinstance(li, dict) for v in li.values()):
            numericos.append(f"série {chave}")
    for h in (doc.get("alarme") or {}).get("hipoteses", []):
        for v in h.get("variantes", []):
            if not ausente(v.get("x")) or not ausente(v.get("teto")):
                numericos.append(f"variante {v['nome']}")
    if not numericos:
        achados.append(achado("ERRO_OUTPUT", "diagnostico", None,
                              "TAG inviável sem nenhum diagnóstico numérico: só texto"))
    else:
        achados.append(achado("INVIAVEL", "dimensoes", None,
                              "sem dimensões finais, com diagnóstico numérico: " + "; ".join(sorted(set(numericos)))))
    return achados


def _conferir_niveis(rt, cartao, envelope, mc_json):
    """SizingResult → dimensionamento.json → JSON do memorial, número a número."""
    r = rt.resultado
    achados = []
    res = envelope["resultado"]
    declarados = rt.entradas.metodo.campos_nao_aplicaveis(r)
    for nome, a in (("x", r.x), ("y", r.y)):
        if not igual(a, res[nome]):
            achados.append(achado("ERRO_OUTPUT", f"nivel2.{nome}", (a, res[nome]),
                                  "o JSON do núcleo não reproduz o resultado do motor"))
    for k, v in r.derivados.items():
        if not igual(v, res["derivados"].get(k)):
            achados.append(achado("ERRO_OUTPUT", f"nivel2.derivados.{k}", (v, res["derivados"].get(k)),
                                  "o JSON do núcleo não reproduz o derivado do motor"))
    nucleo_cartao = {c["rotulo"]: c["valor"] for c in res["cartao"]}
    calc = (mc_json.get("calculo") or {})
    mc_cartao = {c["rotulo"]: c["valor"] for c in calc.get("resultados", [])}
    for rotulo, f in cartao.items():
        if not igual(f.value, nucleo_cartao.get(rotulo)):
            achados.append(achado("ERRO_OUTPUT", f"nivel2.cartao[{rotulo}]", (f.value, nucleo_cartao.get(rotulo)),
                                  "o cartão do JSON do núcleo não reproduz o motor"))
        if rotulo not in mc_cartao:
            if not ausente(nucleo_cartao.get(rotulo)):
                achados.append(achado("ERRO_OUTPUT", f"nivel3.cartao[{rotulo}]", nucleo_cartao.get(rotulo),
                                      "o núcleo tem número finito e o MC não apresenta o campo"))
            elif rotulo not in declarados:
                achados.append(achado("ERRO_OUTPUT", f"nivel3.cartao[{rotulo}]", None,
                                      "o MC omite o campo sem que o método declare a não aplicabilidade"))
        elif not igual(f.value, mc_cartao[rotulo]):
            achados.append(achado("ERRO_OUTPUT", f"nivel3.cartao[{rotulo}]", (f.value, mc_cartao[rotulo]),
                                  "o MC apresenta número diferente do resultado estruturado"))
    linhas = calc.get("tabela", {}).get("linhas", [])
    for i, (caso, pc) in enumerate(zip(envelope["casos"], r.per_case)):
        if not igual(pc.x, caso["x"]):
            achados.append(achado("ERRO_OUTPUT", f"nivel2.casos[{i}].x", (pc.x, caso["x"]),
                                  "o JSON do núcleo não reproduz a varredura individual do caso"))
        if i < len(linhas) and not igual(caso["folga"], linhas[i]["folga"]):
            achados.append(achado("ERRO_OUTPUT", f"nivel3.casos[{i}].folga", (caso["folga"], linhas[i]["folga"]),
                                  "a folga do MC não reproduz a do JSON do núcleo"))
        if i < len(linhas) and pc.feasible and not igual(pc.x, linhas[i]["x_isolado"]):
            achados.append(achado("ERRO_OUTPUT", f"nivel3.casos[{i}].x_isolado", (pc.x, linhas[i]["x_isolado"]),
                                  "o x isolado do MC não reproduz o do motor"))
    # a exigência de cada caso na abscissa de referência: a do motor, não outra
    x = calc.get("x_referencia")
    linha_motor = next((li for li in r.rows if li.x == x), None) if x is not None else None
    if linha_motor is not None:
        for i, y in enumerate(linha_motor.per_case_y):
            if i < len(linhas) and not igual(y, linhas[i]["y"]):
                achados.append(achado("ERRO_OUTPUT", f"nivel3.casos[{i}].y", (y, linhas[i]["y"]),
                                      "a exigência do caso no MC não reproduz a linha do envelope"))
    return achados


# ------------------------------------------------------------------ execução e relatório
# Chaves da identidade que NÃO podem faltar: sem elas o relatório não é atribuível a uma
# execução, e um gate que não se sabe de onde veio não serve de gate.
IDENTIDADE_OBRIGATORIA = ("commit", "casos", "modelo", "propostas", "premissas_alteradas", "modos_dos_tags")
# O modelo de processo é um só desde a consolidação (docs/arquitetura/arquitetura-alvo.md): a
# identidade o declara em vez de listar modos que não existem mais.
MODELO = ("regra de eficiência do FWKO (P-43); gás de SG-001/V-001/V-002 pelo trem (Nota 4 + flash) nos casos "
          "sem gás de lift e por Standing nos demais (docs/validacao/39); óleo vivo (Beggs & Robinson sobre o óleo "
          "morto do BOT); alocação de correntes do projeto (P-46)")


def identidade(ctx, planta, casos=""):
    """Identidade da execução: o que foi dimensionado, com qual código e sob quais opções.

    Tudo o que muda dimensionamento entra aqui — o arquivo de casos e seu SHA, as propostas
    que preencheram lacunas, as premissas alteradas e o modo de cada TAG. A proveniência do
    código vem da mesma função que os memoriais usam (`proveniencia_git`), não de outra."""
    commit, sujo = saida_mc.proveniencia_git()
    prop = ctx.propostas
    ident = {
        "commit": commit,
        "arvore_suja": sujo,
        "fpso_siz": __version__,
        "casos": {"arquivo": str(casos) or ctx.dados.origem, "origem": ctx.dados.origem,
                  "sha256": ctx.dados.sha256, "n_casos": len(ctx.dados.casos)},
        "modelo": MODELO,
        "propostas": ({"arquivo": prop.arquivo, "sha256": prop.sha256} if prop else "não usadas"),
        "premissas_alteradas": dict(ctx.alteracoes),
        "modos_dos_tags": {rt.tag.tag: rt.entradas.modo for rt in planta.tags},
        "versoes_propriedades": ctx.versoes,
    }
    faltando = [k for k in IDENTIDADE_OBRIGATORIA if ident.get(k) is None]
    ident["completa"] = not faltando
    ident["faltando"] = faltando
    return ident


def auditar_planta(ctx, planta, pasta, casos=""):
    """Audita uma planta já dimensionada (o gate e a suíte usam a mesma função)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    linhas, achados = [], []
    for rt in planta.tags:
        li, ac = auditar_tag(ctx, rt, pasta)
        linhas.append(li)
        achados += ac
    contagem = {c: sum(1 for a in achados if a["categoria"] == c) for c in CATEGORIAS}
    ident = identidade(ctx, planta, casos)
    erros = [a for a in achados if a["erro"]]
    aprovada = not erros and ident["completa"]
    # `aprovada` é a CONSISTÊNCIA das saídas (decide o código de saída). O atendimento de engenharia
    # é outra pergunta — restrições, decisões pendentes, verificação incompleta — e só se informa.
    return dict(identidade=ident, casos=ident["casos"]["arquivo"], sha256=ctx.dados.sha256, tags=linhas,
                achados=achados, contagem=contagem, erros=erros, aprovada=aprovada,
                consistencia_saidas={"aprovada": aprovada, "erros": len(erros)},
                atendimento_engenharia=engenharia(planta))


def engenharia(planta):
    """Atendimento de engenharia por TAG, separado da consistência das saídas: um TAG pode ter
    saídas consistentes e, ao mesmo tempo, restrição não atendida ou verificação incompleta."""
    out = []
    for rt in planta.tags:
        li = {"tag": rt.tag.tag, "status": rt.status, "restricoes": list(rt.restricoes),
              "decisoes_pendentes": list(rt.decisoes_pendentes)}
        if rt.operacao is not None and rt.operacao.geometria is not None:
            av = rt.operacao.avaliacao()
            hid = av["atendimento_hidraulico"]
            li.update(situacao=av["situacao"], termico=av["atendimento_termico"]["status"],
                      hidraulica_atendimento=hid["atendimento"], hidraulica_completude=hid["completude"],
                      hidraulica_conclusao=hid["conclusao"],
                      premissa_comprimento=av["premissa_comprimento"].get("explicacao", ""))
        else:
            # o status do envelope do método (viabilidade nos critérios dele), não uma aprovação adicional
            li.update(situacao=rt.status)
        out.append(li)
    return out


def auditar(casos, pasta, propostas=True):
    ctx = servico.Contexto(carregar_casos(casos), propostas=mod_propostas.padrao() if propostas else None)
    return auditar_planta(ctx, dimensionar(contexto=ctx), pasta, casos)


def _num(v):
    if ausente(v):
        return "—"
    if isinstance(v, str):
        return v
    return f"{v:.6g}"


def limpar(obj):
    """NaN/Inf viram null (o resumo.json é JSON estrito, como o resto da saída)."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): limpar(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [limpar(v) for v in obj]
    return obj


def _identidade_md(ident):
    alteradas = ", ".join(f"{k} = {v}" for k, v in ident["premissas_alteradas"].items()) or "nenhuma"
    prop = ident["propostas"]
    modos = ", ".join(sorted({m for m in ident["modos_dos_tags"].values()}))
    linhas = [("commit", f"`{ident['commit']}`" + (" (árvore suja)" if ident["arvore_suja"] else "")),
              ("versão", ident["fpso_siz"]),
              ("casos", f"`{ident['casos']['arquivo']}` — sha256 `{ident['casos']['sha256'][:12]}`, "
                        f"{ident['casos']['n_casos']} casos"),
              ("modelo de processo", ident["modelo"]),
              ("propostas", prop if isinstance(prop, str) else
               f"`{prop['arquivo']}` — sha256 `{prop['sha256'][:12]}`"),
              ("premissas alteradas", alteradas),
              ("modo dos TAGs", modos),
              ("propriedades", "; ".join(f"{k} {v}" for k, v in ident["versoes_propriedades"].items()))]
    fora = "" if ident["completa"] else f"\n\n**Identidade incompleta:** falta {', '.join(ident['faltando'])}."
    return ["## Identidade da execução", "", "| item | valor |", "|---|---|",
            *(f"| {k} | {v} |" for k, v in linhas), fora, ""]


def resumo_md(rel):
    aprovada = "APROVADA" if rel["aprovada"] else "REPROVADA"
    out = [f"# Auditoria de saída do PFD — consistência das saídas {aprovada}", "",
           "Gerado por `tools/auditar_saida_pfd.py`; todos os números vêm do fluxo real. O resultado acima "
           "(e o código de saída) diz se resultado, JSON, CSV e memoriais são consistentes e justificam toda "
           "ausência. Ele **não** é aprovação de engenharia: o atendimento a critérios está na seção própria.", "",
           *_identidade_md(rel["identidade"]),
           "| TAG | estado | viável | caso governante | principais | ausências | lacunas | avisos | MC |",
           "|---|---|---|:--:|---|--:|--:|--:|:--:|"]
    for t in rel["tags"]:
        princ = "; ".join(f"{k} = {_num(v)}" for k, v in t["principais"].items()) or "—"
        estado = t["status"] + (f" — restrições: {', '.join(t['restricoes'])}" if t.get("restricoes") else "")
        estado += f" — decisão pendente: {', '.join(t['decisoes_pendentes'])}" if t.get("decisoes_pendentes") else ""
        out.append(f"| {t['tag']} | {estado} | {'sim' if t['viavel'] else 'não'} | "
                   f"{t['caso_governante'] or '—'} | {princ} | {len(t['ausentes'])} | {len(t['lacunas'])} | "
                   f"{len(t['avisos'])} | {'ok' if t['mc_consistente'] else 'ERRO'} |")
    out += ["", "## Classificação das ausências", "",
            "| categoria | ocorrências |", "|---|--:|"]
    out += [f"| {c} | {n} |" for c, n in rel["contagem"].items()]
    out += ["", "## Erros de aceite", ""]
    if not rel["erros"]:
        out.append("Nenhum. Todo travessão do MC tem justificativa declarada, e os três níveis "
                   "(motor → JSON do núcleo → JSON do MC) trazem o mesmo número.")
    else:
        out += ["| TAG | categoria | caminho | valor | por quê |", "|---|---|---|---|---|"]
        out += [f"| {a['tag']} | {a['categoria']} | `{a['caminho']}` | {a['detalhe']} | {a['justificativa']} |"
                for a in rel["erros"]]
    out += ["", "## Atendimento de engenharia (informativo; não decide o código de saída)", "",
            "| TAG | situação | restrições não atendidas | decisões pendentes | hidráulica |", "|---|---|---|---|---|"]
    for e in rel.get("atendimento_engenharia", []):
        out.append(f"| {e['tag']} | {e['situacao']} | {', '.join(e['restricoes']) or '—'} | "
                   f"{', '.join(e['decisoes_pendentes']) or '—'} | {e.get('hidraulica_conclusao') or '—'} |")
    for e in rel.get("atendimento_engenharia", []):
        if e.get("premissa_comprimento"):
            out += ["", f"**{e['tag']} — premissa de comprimento:** {e['premissa_comprimento']}"]
    out += ["", "## Resultados de cada método", "",
            "| método | principal | obrigatório de memorial | diagnóstico/opcional |", "|---|---|--:|--:|"]
    for t in rel["tags"]:
        n = t["niveis"]
        mem = n["memorial"]
        out.append(f"| {n['metodo']} | {'; '.join(n['principal']) or '—'} | "
                   f"{len(mem['cartao'])} do cartão + {len(mem['equacoes'])} equações + "
                   f"{len(mem['colunas_por_caso'])} colunas por caso | "
                   f"{len(n['diagnostico']['derivados'])} derivados + "
                   f"{len(n['diagnostico']['graficos'])} gráficos |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS_PADRAO if CASOS_PADRAO.exists() else CASOS_FIXTURE)
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    ap.add_argument("--sem-propostas", action="store_true")
    a = ap.parse_args()
    try:
        rel = auditar(a.casos, a.saida, propostas=not a.sem_propostas)
    except Exception as e:                                  # noqa: BLE001  (o gate não pode mascarar falha própria)
        print(f"auditoria não pôde rodar: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    (a.saida / "resumo.json").write_text(
        json.dumps(limpar(rel), ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    (a.saida / "resumo.md").write_text(resumo_md(rel), encoding="utf-8")
    print(resumo_md(rel))
    print(f"artefatos em {a.saida}")
    return 0 if rel["aprovada"] else 1


if __name__ == "__main__":
    sys.exit(main())
