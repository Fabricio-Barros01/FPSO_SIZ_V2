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

# Um método declara que um critério não se aplica a um caso pelo rótulo do mecanismo
# (`rotulo_mecanismo`): é a única declaração de não aplicabilidade que o contrato hoje
# oferece, e é positiva — vem do método, não do vazio. Pendência anotada no relatório:
# promovê-la a hook do contrato, em vez de prefixo de texto.
PREFIXO_NAO_APLICAVEL = "não aplicável"
SEM_TETO = ("none", "sem teto de decantação")

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

    def _sem_teto(self, mecanismo):
        return mecanismo in SEM_TETO or str(mecanismo).startswith(PREFIXO_NAO_APLICAVEL)

    def _nao_aplicavel_ao_caso(self, mecanismo):
        return str(mecanismo).startswith(PREFIXO_NAO_APLICAVEL)

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
        if self._sem_teto(self.r.ceiling_mechanism):
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
        if linha is not None and self._sem_teto(linha["mecanismo"]):
            return "NAO_APLICAVEL", f"o caso não impõe teto (mecanismo declarado: {linha['mecanismo']})"
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
        if linha is not None and self._nao_aplicavel_ao_caso(linha["mecanismo"]):
            return "NAO_APLICAVEL", f"o método declara o caso como «{linha['mecanismo']}»"
        return None

    def _r_series_casos_teto(self, caminho, valor):
        linha = self._caso_serie(caminho, "casos")
        i = indices(caminho)
        linhas = self.calc.get("tabela", {}).get("linhas", [])
        mec = linhas[i[0]]["mecanismo"] if linha is not None and i[0] < len(linhas) else None
        if mec is not None and self._sem_teto(mec):
            return "NAO_APLICAVEL", f"o caso não impõe teto (mecanismo declarado: {mec})"
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
    cartao = _cartao(m, r)
    if status == servico.DIMENSIONADO:
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

    principais = {f.label: f.value for f in cartao.values() if f.highlight}
    linha = dict(tag=tag, equipamento=rt.tag.equipamento, metodo=m.method_id, status=status,
                 viavel=bool(r.feasible) if r is not None else None,
                 caso_governante=(r.driver_case if r is not None else "") or "",
                 principais=principais, x=None if r is None else r.x, y=None if r is None else r.y,
                 ausentes=sorted({a["caminho"] for a in achados
                                  if a["caminho"].startswith(("calculo.", "cartao["))}),
                 lacunas=lacunas, avisos=[t for t, _ in rt.entradas.avisos()],
                 mc_consistente=not any(a["erro"] for a in achados),
                 niveis=niveis_do_metodo(m, r))
    return linha, [dict(a, tag=tag) for a in achados]


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
IDENTIDADE_OBRIGATORIA = ("commit", "casos", "oleo", "propostas", "topologia", "regra_fwko",
                          "premissas_alteradas", "modos_dos_tags")


def identidade(ctx, planta, casos=""):
    """Identidade da execução: o que foi dimensionado, com qual código e sob quais opções.

    Tudo o que muda dimensionamento entra aqui — o arquivo de casos e seu SHA, a regra do
    FWKO (que muda o balanço), a viscosidade do óleo, a alocação de correntes, as propostas
    que preencheram lacunas, as premissas alteradas e o modo de cada TAG. A proveniência do
    código vem da mesma função que os memoriais usam (`proveniencia_git`), não de outra."""
    commit, sujo = saida_mc.proveniencia_git()
    prop = ctx.propostas
    balanco = ctx.resultados_balanco if ctx.balanco_resolvido else []
    ident = {
        "commit": commit,
        "arvore_suja": sujo,
        "fpso_siz": __version__,
        "casos": {"arquivo": str(casos) or ctx.dados.origem, "origem": ctx.dados.origem,
                  "sha256": ctx.dados.sha256, "n_casos": len(ctx.dados.casos)},
        "oleo": "vivo" if ctx.oleo_vivo else "morto",
        "propostas": ({"arquivo": prop.arquivo, "sha256": prop.sha256} if prop else "não usadas"),
        "topologia": "pfd_f1_julia" if ctx.topologia_julia else "projeto_p46",
        "regra_fwko": balanco[0].fwko["regra"] if balanco else None,
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
    return dict(identidade=ident, casos=ident["casos"]["arquivo"], sha256=ctx.dados.sha256, tags=linhas,
                achados=achados, contagem=contagem, erros=erros,
                aprovada=not erros and ident["completa"])


def auditar(casos, pasta, propostas=True, oleo_vivo=True):
    ctx = servico.Contexto(carregar_casos(casos), oleo_vivo=oleo_vivo,
                           propostas=mod_propostas.padrao() if propostas else None)
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
              ("regra do FWKO", ident["regra_fwko"]),
              ("viscosidade do óleo", ident["oleo"]),
              ("alocação de correntes", ident["topologia"]),
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
    out = [f"# Auditoria de saída do PFD — {aprovada}", "",
           "Gerado por `tools/auditar_saida_pfd.py`; todos os números vêm do fluxo real.", "",
           *_identidade_md(rel["identidade"]),
           "| TAG | estado | viável | caso governante | principais | ausências | lacunas | avisos | MC |",
           "|---|---|---|:--:|---|--:|--:|--:|:--:|"]
    for t in rel["tags"]:
        princ = "; ".join(f"{k} = {_num(v)}" for k, v in t["principais"].items()) or "—"
        out.append(f"| {t['tag']} | {t['status']} | {'sim' if t['viavel'] else 'não'} | "
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
    ap.add_argument("--oleo-morto", action="store_true")
    a = ap.parse_args()
    try:
        rel = auditar(a.casos, a.saida, propostas=not a.sem_propostas, oleo_vivo=not a.oleo_morto)
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
