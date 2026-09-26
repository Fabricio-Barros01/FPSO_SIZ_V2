"""Conteúdo do memorial de cálculo (MC) de um TAG (F11): só dados, sem formatação.

Consome o ResultadoTAG do serviço por TAG (pfd/equipamento.py) — o mesmo do terminal, do
JSON e do CSV — e devolve um dicionário com as dez seções do MC. Nenhuma equação de
engenharia é reavaliada aqui: resultados e operandos vêm do rastro de cada caso
(`Rastro.operandos`, capturados na avaliação) e do envelope; o que o MC mostra a mais
(parcelas de Lss, bordas da banda de esbeltez, constante de campo convertida) sai de hooks
do método ou de core/unidades.py. A escolha do que aparece e em que ordem está em
config/memorial_tag.toml, por método: não há código por TAG.

TAG aguardando entrada, inativo ou inviável também tem MC: as seções de cálculo ficam
"aguardando entrada" (lacunas com a origem esperada), e o inviável traz o diagnóstico.
"""
import math
import re

from fpso_siz.balanco.dados import descritores_premissas
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.parametros import with_defaults
from fpso_siz.core.unidades import CONVERSOES_CAMPO
from fpso_siz.pfd.entradas import rotulo_origem
from fpso_siz.pfd.equipamento import AGUARDANDO, DIMENSIONADO, INATIVO, INVIAVEL, limitacoes

CODIGO_PREMISSA = re.compile(r"\b[PF]-\d{2}\b")
SELECAO = "selecao"


def cfg():
    return carregar("memorial_tag.toml")


def numero(tag, revisao=None):
    """(sequência, número do documento) pela tabela fixa; (None, None) fora da planta."""
    c = cfg()
    seq = c["numeracao"].get(tag)
    if seq is None:
        return None, None
    return seq, c["formato_numero"].format(seq=seq, rev=c["revisao"] if revisao is None else revisao)


def conteudo_metodo(metodo):
    return cfg()["metodos"].get(metodo.method_id, {})


# ------------------------------------------------------------------ auxiliares do rastro
def _entrada(tr, bloco, var):
    """Última entrada do rastro com (bloco, var), ou None."""
    achadas = [e for e in tr.entries if e.block == bloco and e.var == var]
    return achadas[-1] if achadas else None


def _linha_em(sweep, x):
    return next((r for r in sweep if r.x == x), None)


def _parametros_envelope(m, entradas):
    """Grade e banda do envelope (as mesmas que o motor usou)."""
    params = [with_defaults(m.parameters(), vals) for _, vals in entradas.case_set().expand()]
    ok, p_env = m.envelope_params(params) if params else (False, None)
    return p_env if ok else None


def indice_governante(r):
    """Caso do passo a passo: o que governa o ponto escolhido; se inviável, o do teto;
    se não há nem um nem outro, o primeiro caso ativo."""
    for nome in (r.driver_case, r.ceiling_case):
        if nome and nome in r.case_names:
            return r.case_names.index(nome)
    return 0


# ------------------------------------------------------------------ seções
def identificacao(ctx, rt):
    t, e = rt.tag, rt.entradas
    seq, num = numero(t.tag) if not e.avulso else (None, None)
    regra, exigidos = None, []
    if not e.avulso and e.modo != "manual" and ctx.balanco_resolvido:
        b = ctx.resultados_balanco
        regra = b[0].fwko["regra"]
        exigidos = [x.num for x in b if x.fwko.get("exigido_acima")]
    m = e.metodo
    return dict(tag=t.tag, nome=t.nome, bloco=t.bloco, condicao=t.condicao, equipamento=e.equipamento.label,
                metodo=m.label, metodo_id=m.method_id, referencia=getattr(m, "method_reference", lambda: "")(),
                sequencia=seq, numero=num, revisao=cfg()["revisao"], status=rt.status, modo=e.modo,
                preliminar=e.preliminar, regra_fwko=regra, fwko_exigidos=exigidos, avulso=e.avulso)


def casos(rt):
    return [dict(num=c.num, nome=c.nome, ativo=c.ativo, motivo=c.motivo) for c in rt.entradas.casos]


def entradas(rt):
    """Dados de entrada por chave (ordem do método, depois insumos do TAG), agrupando os
    casos ativos com o mesmo valor, origem e fonte."""
    e = rt.entradas
    ativos = [c for c in e.casos if c.ativo]
    chaves = list(e.specs) + [k for c in ativos for k in c.insumos if k not in e.specs]
    out = []
    for k in dict.fromkeys(chaves):
        s = e.specs.get(k)
        ins = e.tag.insumos.get(k, {})
        grupos = {}
        for c in ativos:
            v = c.valores.get(k) or c.insumos.get(k)
            if v is None:
                continue
            chave = (repr(v.numero), v.origem, v.fonte, v.revisao)
            grupos.setdefault(chave, (v, []))[1].append(c.num)
        for v, nums in grupos.values():
            out.append(dict(chave=k, rotulo=s.label if s else ins.get("rotulo", k), unidade=s.unit if s else
                            ins.get("unidade", ""), valor=v.numero, origem=v.origem, rotulo_origem=rotulo_origem(v.origem),
                            fonte=v.fonte, revisao=v.revisao, anterior=v.anterior, casos=nums))
    return out


def lacunas(rt):
    return [dict(chave=l.chave, rotulo=l.rotulo, unidade=l.unidade, faixa=list(l.faixa), origem_esperada=l.dica,
                 casos=list(l.casos), dependentes=list(l.dependentes)) for l in rt.entradas.lacunas]


def premissas(ctx, rt, ident):
    """Códigos P-xx/F-xx citados no rastro e nas fontes das entradas do TAG (e a P-43,
    quando o balanço usado é o da regra de eficiência), com o descritor numérico do
    balanço quando existe."""
    textos = []
    for c in rt.entradas.casos:
        textos += [f"{x.eq} {x.var} {x.formula}" for x in c.rastro]
        textos += [v.fonte for v in (*c.valores.values(), *c.insumos.values())]
    if rt.resultado is not None:
        for pc in rt.resultado.per_case:
            textos += [f"{x.eq} {x.formula}" for x in pc.trace]
    codigos = set(CODIGO_PREMISSA.findall(" ".join(textos)))
    if ident["regra_fwko"] == "eficiencia":
        codigos.add("P-43")
    dados = ctx.dados if not rt.entradas.avulso else None
    desc = {}
    for d in descritores_premissas(dados):
        desc.setdefault(d["id"], []).append(dict(nome=d["nome"], valor=ctx.prem.get(d["nome"], d["valor"])
                                                 if ctx.prem else d["valor"], unidade=d["unidade"],
                                                 descricao=d["descricao"], origem=d["origem"]))
    chave = lambda c: (c[0], int(c[2:]))  # noqa: E731
    return [dict(id=c, descritores=desc.get(c, [])) for c in sorted(codigos, key=chave)]


def _operandos(tr, eq, selecao):
    if eq.get("fonte_dados") == SELECAO:
        if selecao is None:
            return None
        return dict(selecao), selecao[eq["resultado"]], None
    ent = _entrada(tr, eq["bloco"], eq["var"])
    if ent is None:
        return None
    ops = dict(tr.operandos.get((eq["bloco"], eq["var"]), {}))
    if eq.get("iteracao") == "ultima" and tr.iteracoes.get(eq["bloco"]):
        ops.update(tr.iteracoes[eq["bloco"]][-1])
    return ops, ent.value, ent


def equacoes(rt, i, selecao):
    """Passo a passo do caso `i`: forma de campo, forma métrica, operandos e resultado."""
    m = rt.entradas.metodo
    tr = rt.resultado.per_case[i].trace
    unid_sel = dict(d="mm", leff="m", lss="m", sr="–", volume="m³")
    out = []
    for eq in conteudo_metodo(m).get("equacoes", []):
        achado = _operandos(tr, eq, selecao)
        if achado is None:
            continue
        ops, resultado, ent = achado
        conv = None
        if "conversao" in eq and "coef" in ops:
            c = eq["conversao"]
            convertido = CONVERSOES_CAMPO[c["funcao"]](c["campo"])
            conv = dict(campo=c["campo"], convertido=convertido, publicado=ops["coef"],
                        desvio=convertido / ops["coef"] - 1, fonte=c["fonte"], nota=c.get("nota", ""))
            ops["campo"] = c["campo"]
        out.append(dict(id=eq["id"], titulo=eq["titulo"], fonte=eq["fonte"], campo=eq.get("campo", ""),
                        metrico=eq["metrico"], substituicao=eq["substituicao"], unidades=eq.get("unidades", {}),
                        operandos=ops, resultado=resultado,
                        unidade=ent.unit if ent is not None else unid_sel.get(eq["resultado"], ""),
                        rastro=dict(eq=ent.eq, var=ent.var, formula=ent.formula) if ent is not None else None,
                        conversao=conv))
    return out


def iteracoes(rt, i, bloco):
    return list(rt.resultado.per_case[i].trace.iteracoes.get(bloco, []))


def selecao(rt, i):
    """Operandos do ponto escolhido do envelope (só com resultado viável)."""
    r, m = rt.resultado, rt.entradas.metodo
    if not r.feasible or not hasattr(m, "selecao_memorial"):
        return None
    return m.selecao_memorial(r.x, r.y, r.derivados, r.per_case[i].trace, m.constants())


def x_referencia(rt, p_env):
    """Abscissa das comparações por caso: o ponto escolhido, ou, se inviável, o menor x
    da grade com a esbeltez na banda (o que o teto impede)."""
    r, m = rt.resultado, rt.entradas.metodo
    if r.feasible:
        return r.x
    if p_env is None:
        return None
    na_banda = [row.x for row in r.rows if m.admissible(row.x, row.derivados, p_env)]
    return min(na_banda) if na_banda else None


def tabela_casos(rt, x):
    """Resultados intermediários de cada caso ativo, com a exigência e o critério
    governante em x (da varredura individual do caso)."""
    r, m = rt.resultado, rt.entradas.metodo
    colunas = conteudo_metodo(m).get("colunas_casos", [])
    linha_env = _linha_em(r.rows, x) if x is not None else None
    out = []
    for i, (nome, pc) in enumerate(zip(r.case_names, r.per_case)):
        vals = []
        for col in colunas:
            ent = _entrada(pc.trace, col["bloco"], col["var"])
            vals.append(ent.value if ent is not None else None)
        lin = _linha_em(pc.sweep, x) if x is not None else None
        y = linha_env.per_case_y[i] if linha_env is not None else None
        rotulo_mec = getattr(m, "rotulo_mecanismo", str)
        out.append(dict(caso=nome, valores=vals, y=y, governante=m.governing_label(lin.governing) if lin else None,
                        folga=(r.slack[i] if r.feasible and r.slack else None),
                        teto=pc.ceiling if math.isfinite(pc.ceiling) else None,
                        mecanismo=rotulo_mec(pc.ceiling_mechanism), viavel_isolado=pc.feasible,
                        x_isolado=pc.x if pc.feasible else None))
    return dict(colunas=[c["rotulo"] for c in colunas], linhas=out)


def criterios(rt, x):
    """Verificação atende / não atende, a partir dos estados do cartão e do envelope."""
    r, m = rt.resultado, rt.entradas.metodo
    out = []
    for f in m.result_fields(r):
        if f.status in ("ok", "erro"):
            out.append(dict(criterio=f.label, valor=f.value, unidade=f.unit, atende=f.status == "ok"))
    if r.feasible:
        out.append(dict(criterio="menor folga entre os casos no ponto escolhido", valor=min(r.slack),
                        unidade=m.requirement_spec()[1], atende=min(r.slack) >= 0))
    else:
        out.append(dict(criterio="existe ponto admissível para todos os casos", valor=None, unidade="", atende=False))
        if x is not None and math.isfinite(r.ceiling):
            out.append(dict(criterio="menor diâmetro com esbeltez na banda ≤ teto de decantação", valor=x,
                            unidade=m.sweep_axis(_parametros_envelope(m, rt.entradas)).unit, atende=x <= r.ceiling))
    return out


def diagnostico(rt, x):
    r = rt.resultado
    if r is None or r.feasible:
        return None
    m = rt.entradas.metodo
    return dict(mensagem=r.message, teto=r.ceiling if math.isfinite(r.ceiling) else None, caso_teto=r.ceiling_case,
                mecanismo=getattr(m, "rotulo_mecanismo", str)(r.ceiling_mechanism), x_min_banda=x)


def resultados(rt):
    r, m = rt.resultado, rt.entradas.metodo
    return [dict(rotulo=f.label, valor=f.value, unidade=f.unit, destaque=f.highlight) for f in m.result_fields(r)]


def series(rt, p_env):
    """Séries dos gráficos (CSV lidos pelo pgfplots): diagrama x × exigência com as
    capacidades envelopadas, a banda de esbeltez e o ponto; exigência por caso."""
    r, m = rt.resultado, rt.entradas.metodo
    graf = conteudo_metodo(m).get("graficos", [])
    out = {}
    if "diagrama" in graf and r.rows and hasattr(m, "bordas_banda") and p_env is not None:
        k = m.constants()
        linhas = []
        for row in r.rows:
            caps = {}
            for pc in r.per_case:
                lin = _linha_em(pc.sweep, row.x)
                for chave, v in (lin.per_constraint.items() if lin else ()):
                    caps[chave] = max(caps.get(chave, -math.inf), v)
            lo, hi = m.bordas_banda(row.x, row.governing, p_env, k)
            linhas.append(dict(x=row.x, y=row.y, **{f"cap_{c}": v for c, v in caps.items()}, banda_min=lo,
                               banda_max=hi, admissivel=int(row.ok)))
        out["diagrama"] = linhas
        rotulos = {c[4:]: m.governing_label(c[4:]) for c in linhas[0] if c.startswith("cap_")} if linhas else {}
        out["rotulos_capacidades"] = rotulos
        if r.feasible:
            out["ponto"] = [dict(x=r.x, y=r.y)]
        else:
            x_min = x_referencia(rt, p_env)
            lin = _linha_em(r.rows, x_min) if x_min is not None else None
            out["minimo"] = [dict(x=lin.x, y=lin.y)] if lin else []
        if math.isfinite(r.ceiling):
            ys = [v for li in linhas for v in (li["y"],) if math.isfinite(v) and v > 0]
            out["teto"] = [dict(x=r.ceiling, y=min(ys)), dict(x=r.ceiling, y=max(ys))] if ys else []
        out["banda"] = m.banda_memorial(p_env)
    if "casos" in graf:
        x = x_referencia(rt, p_env)
        lin_env = _linha_em(r.rows, x) if x is not None else None
        linhas = []
        if lin_env is not None:
            for i, (nome, pc) in enumerate(zip(r.case_names, r.per_case)):
                lin = _linha_em(pc.sweep, x)
                gov = lin.governing if lin else ""
                linhas.append(dict(caso=i + 1, nome=nome, y=lin_env.per_case_y[i], governante=gov,
                                   teto=pc.ceiling if math.isfinite(pc.ceiling) else math.nan))
        out["casos"] = linhas
        out["x_casos"] = x
    return out


def pendencias(rt):
    e = rt.entradas
    sem_fonte = [dict(chave=k, casos=v) for k, v in _sem_fonte(e).items()]
    return dict(revisoes=[dict(chave=v.chave, valor=v.numero if hasattr(v, "numero") else v.valor, fonte=v.fonte,
                               origem=rotulo_origem(v.origem), estado=v.estado, casos=list(v.casos))
                          for v in e.revisoes()],
                lacunas=[lac.chave for lac in e.lacunas], avisos=[dict(texto=a, casos=n) for a, n in e.avisos()],
                sem_fonte=sem_fonte, limitacoes=limitacoes())


def _sem_fonte(e):
    out = {}
    for c in e.casos:
        if not c.ativo:
            continue
        for k, v in (*c.valores.items(), *c.insumos.items()):
            if not v.lacuna and not v.nao_aplicavel and not v.fonte.strip():
                out.setdefault(k, []).append(c.num)
    return out


def documento(ctx, rt):
    """As dez seções do MC do TAG, como dados (números em precisão total)."""
    ident = identificacao(ctx, rt)
    m = rt.entradas.metodo
    doc = dict(identificacao=ident, conteudo=conteudo_metodo(m), casos=casos(rt), entradas=entradas(rt),
               lacunas=lacunas(rt), premissas=premissas(ctx, rt, ident), pendencias=pendencias(rt),
               calculo=None)
    r = rt.resultado
    if r is None:
        return doc
    p_env = _parametros_envelope(m, rt.entradas)
    i = indice_governante(r)
    x = x_referencia(rt, p_env)
    sel = selecao(rt, i)
    doc["calculo"] = dict(caso_governante=r.case_names[i], indice_governante=i, viavel=r.feasible,
                          equacoes=equacoes(rt, i, sel), iteracoes=iteracoes(rt, i, "gas"), selecao=sel,
                          banda=m.banda_memorial(p_env) if p_env and hasattr(m, "banda_memorial") else None,
                          tabela=tabela_casos(rt, x), criterios=criterios(rt, x), diagnostico=diagnostico(rt, x),
                          resultados=resultados(rt), series=series(rt, p_env), x_referencia=x,
                          eixo=m.sweep_axis(p_env).label if p_env else "", unidade_eixo=m.sweep_axis(p_env).unit
                          if p_env else "", exigencia=m.requirement_spec())
    return doc


ESTADOS_MC = {DIMENSIONADO: "dimensionado", INVIAVEL: "diagnostico", AGUARDANDO: "aguardando", INATIVO: "aguardando"}
