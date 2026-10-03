"""Conteúdo da memória de cálculo (MC) de um TAG (F11): só dados, sem formatação.

Consome o ResultadoTAG do serviço por TAG (pfd/equipamento.py) — o mesmo do terminal, do
JSON e do CSV — e devolve um dicionário com as dez seções do MC. **Nada de engenharia é
avaliado aqui**: resultados e operandos vêm do rastro de cada caso (`Rastro.operandos`) e do
envelope, e o que o MC mostra a mais e exige o método (critério governante por caso, bordas da
banda, perfil T × Q, parcelas de 1/U, curva do sistema, feixe mais próximo) sai de
`core/memoria.py`, do lado do dimensionamento, sobre as restrições que o próprio motor preparou. A escolha do que aparece e em que ordem está em
config/memorial_tag.toml, por método: não há código por TAG.

TAG aguardando entrada, inativo ou inviável também tem MC: as seções de cálculo ficam
"aguardando entrada" (lacunas com a origem esperada), e o inviável traz o diagnóstico.
"""
import math
import re

from dataclasses import asdict

from fpso_siz.balanco.balancos import balanco_global, balancos_por_bloco, topologia
from fpso_siz.balanco.estado import ETAPA_RATING
from fpso_siz.balanco.indicadores import criterios as criterios_balanco
from fpso_siz.balanco.dados import descritores_premissas
from fpso_siz.core.configuracao import carregar
from fpso_siz.core import memoria
from fpso_siz.core.unidades import CONVERSOES_CAMPO, w_para_kw
from fpso_siz.pfd.entradas import rotulo_origem
from fpso_siz.pfd.ajustes import MANUAL
from fpso_siz.pfd.equipamento import (AGUARDANDO, DIMENSIONADO, INATIVO, INVIAVEL, TAG_RATING, limitacoes,
                                      referencias_rating)

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


indice_governante = memoria.indice_governante


# ------------------------------------------------------------------ seções
def identificacao(ctx, rt):
    t, e = rt.tag, rt.entradas
    seq, num = numero(t.tag) if not e.avulso else (None, None)
    usa_balanco, exigidos = False, []
    if not e.avulso and e.modo != "manual" and ctx.balanco_resolvido:
        usa_balanco = True
        exigidos = [x.num for x in ctx.resultados_balanco if x.fwko.get("exigido_acima")]
    m = e.metodo
    return dict(tag=t.tag, nome=t.nome, bloco=t.bloco, condicao=t.condicao, equipamento=e.equipamento.label,
                metodo=m.label, metodo_id=m.method_id, referencia=getattr(m, "method_reference", lambda: "")(),
                sequencia=seq, numero=num, revisao=cfg()["revisao"], status=rt.status, modo=e.modo,
                preliminar=e.preliminar, usa_balanco=usa_balanco, fwko_exigidos=exigidos, avulso=e.avulso,
                etapa_balanco=rt.etapa_balanco, restricoes=list(rt.restricoes),
                decisoes_pendentes=list(rt.decisoes_pendentes),
                propostas=dict(arquivo=ctx.propostas.arquivo, sha256=ctx.propostas.sha256) if ctx.propostas else None)


def correntes(ctx, rt):
    """Correntes de entrada e saída do bloco do TAG (topologia), com a faixa de T e P nos
    casos ativos quando o TAG usa o balanço (automático)."""
    t, e = rt.tag, rt.entradas
    if e.avulso or not t.bloco:
        return []
    topo = topologia()
    bloco = next((b for b in topo["blocos"] if b["id"] == t.bloco), None)
    if bloco is None:
        return []
    info = {c["id"]: c for c in topo["correntes"]}
    ativos = {c.num for c in e.casos if c.ativo}
    balanco = []
    if e.modo != "manual" and ctx.balanco_resolvido:
        # documento final: o estado operacional (pós-rating do P-001) — o P-001 mostra as saídas
        # realizadas; as entradas do rating (preliminares) estão na seção 4, identificadas
        balanco = ctx.balanco_operacional() if rt.operacao is not None else ctx.balanco_do_tag(t)
    out = []
    for papel, ids in (("entrada", bloco["entradas"]), ("saída", bloco["saidas"])):
        for cid in ids:
            ts = [r.T[cid] for r in balanco if r.num in ativos]
            ps = [r.P[cid] for r in balanco if r.num in ativos]
            out.append(dict(id=cid, papel=papel, nome=info[cid]["nome"], fase=info[cid]["fase"],
                            t=(min(ts), max(ts)) if ts else None, p=(min(ps), max(ps)) if ps else None))
    return out


def casos(rt):
    return [dict(num=c.num, nome=c.nome, ativo=c.ativo, motivo=c.motivo) for c in rt.entradas.casos]


def entradas(rt):
    """Dados de entrada por chave (ordem do método, depois insumos do TAG), agrupando os
    casos ativos com o mesmo valor, origem e fonte."""
    e = rt.entradas
    ativos = [c for c in e.casos if c.ativo]
    chaves = (list(e.specs) + [k for c in ativos for k in c.insumos if k not in e.specs]
              + [k for c in ativos for k in c.auxiliares])
    out = []
    for k in dict.fromkeys(chaves):
        s = e.specs.get(k)
        ins = e.tag.insumos.get(k) or e.tag.auxiliares.get(k, {})
        grupos = {}
        for c in ativos:
            v = c.valores.get(k) or c.insumos.get(k) or c.auxiliares.get(k)
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
    """Códigos P-xx/F-xx citados no rastro e nas fontes das entradas do TAG (e a P-43, quando
    o TAG usa o balanço), com o descritor numérico do balanço quando existe."""
    textos = []
    for c in rt.entradas.casos:
        textos += [f"{x.eq} {x.var} {x.formula}" for x in c.rastro]
        textos += [v.fonte for v in (*c.valores.values(), *c.insumos.values())]
    if rt.resultado is not None:
        for pc in rt.resultado.per_case:
            textos += [f"{x.eq} {x.formula}" for x in pc.trace]
    codigos = set(CODIGO_PREMISSA.findall(" ".join(textos)))
    if ident["usa_balanco"]:
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


def tabela_casos(rt, x):
    """Resultados intermediários de cada caso ativo, com a exigência e o critério
    governante em x."""
    r, m = rt.resultado, rt.entradas.metodo
    colunas = conteudo_metodo(m).get("colunas_casos", [])
    linha_env = _linha_em(r.rows, x) if x is not None else None
    govs = memoria.governantes(r, x)
    out = []
    for i, (nome, pc) in enumerate(zip(r.case_names, r.per_case)):
        vals = []
        for col in colunas:
            ent = _entrada(pc.trace, col["bloco"], col["var"])
            vals.append(ent.value if ent is not None else None)
        y = linha_env.per_case_y[i] if linha_env is not None else None
        rotulo_mec = getattr(m, "rotulo_mecanismo", str)
        out.append(dict(caso=nome, valores=vals, y=y,
                        governante=m.governing_label(govs[i]) if govs[i] is not None else None,
                        folga=(r.slack[i] if r.feasible and r.slack else None),
                        teto=pc.ceiling if math.isfinite(pc.ceiling) else None,
                        mecanismo=rotulo_mec(pc.ceiling_mechanism), mecanismo_id=pc.ceiling_mechanism,
                        teto_aplicavel=m.teto_aplicavel(pc.ceiling_mechanism),
                        criterio_aplicavel=pc.ceiling_mechanism not in m.mecanismos_nao_aplicaveis(),
                        viavel_isolado=pc.feasible,
                        x_isolado=pc.x if pc.feasible else None))
    return dict(colunas=[c["rotulo"] for c in colunas], linhas=out, tem_teto=any(l["teto"] is not None for l in out))


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
                            unidade=m.sweep_axis(r.p_env).unit, atende=x <= r.ceiling))
    return out


def diagnostico(rt, x):
    r = rt.resultado
    if r is None or r.feasible:
        return None
    m = rt.entradas.metodo
    return dict(mensagem=r.message, teto=r.ceiling if math.isfinite(r.ceiling) else None, caso_teto=r.ceiling_case,
                mecanismo=getattr(m, "rotulo_mecanismo", str)(r.ceiling_mechanism), mecanismo_id=r.ceiling_mechanism,
                teto_aplicavel=m.teto_aplicavel(r.ceiling_mechanism), x_min_banda=x)


def alarme(rt):
    """Alarme do TAG inviável, como está registrado (config/pfd/alarmes.toml): estado, resumo e
    hipóteses, com o rótulo e a origem das variantes de estudo. O MC não executa variante —
    seria recalcular engenharia na saída; quem as roda é `tools/investigar_alarmes.py`, pelo
    mesmo serviço. None se o TAG não está inviável."""
    from fpso_siz.pfd import investigacao

    if rt.status != INVIAVEL or rt.entradas.avulso:
        return None
    reg = investigacao.registro(rt.tag.tag)
    if reg is None:
        return dict(registrado=False, estado="sem investigação anotada", resumo="", hipoteses=[])
    classes = investigacao.cfg()["classes"]
    hipoteses = [dict(classe=classes[h["classe"]], texto=h["texto"],
                      variantes=[dict(nome=n, rotulo=investigacao.variante(n)["rotulo"],
                                      origem=investigacao.variante(n)["origem"]) for n in h.get("variantes", [])])
                 for h in reg["hipoteses"]]
    return dict(registrado=True, estado=reg["estado"], resumo=reg["resumo"], hipoteses=hipoteses)


def resultados(rt):
    r, m = rt.resultado, rt.entradas.metodo
    campos = m.result_fields(r)
    if r.feasible:   # só sai do MC o campo que o método DECLARA não se aplicar (contrato: campos_nao_aplicaveis)
        nao_aplicaveis = m.campos_nao_aplicaveis(r)
        campos = [f for f in campos if f.label not in nao_aplicaveis]
    return [dict(rotulo=f.label, valor=f.value, unidade=f.unit, destaque=f.highlight) for f in campos]


def nao_aplicaveis(rt):
    """[{campo, motivo}] declarados pelo método: por que um resultado do cartão não existe
    para este equipamento. É o que separa «não se aplica» de «faltou calcular»."""
    r, m = rt.resultado, rt.entradas.metodo
    return [dict(campo=k, motivo=v) for k, v in (m.campos_nao_aplicaveis(r) if r is not None else {}).items()]


def series(rt):
    """Séries dos gráficos (CSV lidos pelo pgfplots): diagrama x × exigência com as
    capacidades envelopadas, a banda de esbeltez e o ponto; exigência por caso. Os números vêm
    de `core/memoria.py`; aqui só se escolhe o que o método mostra e se dá forma."""
    r, m = rt.resultado, rt.entradas.metodo
    graf = conteudo_metodo(m).get("graficos", [])
    out = {}
    if "diagrama" in graf:
        diag = memoria.diagrama(r)
        if diag:
            linhas = [dict(x=d["x"], y=d["y"], **{f"cap_{c}": v for c, v in d["capacidades"].items()},
                           banda_min=d["banda_min"], banda_max=d["banda_max"], admissivel=d["admissivel"]) for d in diag]
            out["diagrama"] = linhas
            out["rotulos_capacidades"] = {c[4:]: m.governing_label(c[4:]) for c in linhas[0] if c.startswith("cap_")}
            if r.feasible:
                out["ponto"] = [dict(x=r.x, y=r.y)]
            else:
                x_min = memoria.x_referencia(r)
                lin = _linha_em(r.rows, x_min) if x_min is not None else None
                out["minimo"] = [dict(x=lin.x, y=lin.y)] if lin else []
            if math.isfinite(r.ceiling):
                ys = [li["y"] for li in linhas if math.isfinite(li["y"]) and li["y"] > 0]
                out["teto"] = [dict(x=r.ceiling, y=min(ys)), dict(x=r.ceiling, y=max(ys))] if ys else []
            out["banda"] = memoria.banda(r)
    if "casos" in graf:
        x = memoria.x_referencia(r)
        lin_env = _linha_em(r.rows, x) if x is not None else None
        linhas = []
        if lin_env is not None:
            govs = memoria.governantes(r, x)
            for i, (nome, pc) in enumerate(zip(r.case_names, r.per_case)):
                linhas.append(dict(caso=i + 1, nome=nome, y=lin_env.per_case_y[i], governante=govs[i] or "",
                                   teto=pc.ceiling if math.isfinite(pc.ceiling) else math.nan))
        out["casos"] = linhas
        out["x_casos"] = x
        out["rotulos_governantes"] = {g: m.governing_label(g) for g in dict.fromkeys(li["governante"] for li in linhas)
                                      if g}
    out.update(_series_do_metodo(rt, graf))
    return out


def _series_do_metodo(rt, graf):
    """Gráficos próprios de trocador (perfil T × Q, parcelas de 1/U) e de bomba (curva do
    sistema, NPSH por caso), no ponto escolhido e no caso governante."""
    r, m = rt.resultado, rt.entradas.metodo
    if not {"perfil_tq", "resistencias", "curva_sistema", "npsh"} & set(graf) or not r.preparo:
        return {}
    out = {"caso_metodo": r.preparo[memoria.caso_do_metodo(r)][0]}
    # o perfil T × Q só depende do balanço térmico do caso: sai também no inviável
    if "perfil_tq" in graf:
        perfil = memoria.perfil_tq(r)
        if perfil is not None:
            out["perfil_tq"] = [dict(q_kw=w_para_kw(q), t_tubo=tt, t_casco=tc) for q, tt, tc in perfil]
    if not r.feasible:
        out.update(_feixe_mais_proximo(rt))
        return out
    if "resistencias" in graf:
        pu = memoria.parcelas_u(r)
        if pu is not None:
            parcelas, u = pu
            rot = conteudo_metodo(m).get("rotulos_resistencias", {})
            total = sum(parcelas.values())
            out["resistencias"] = [dict(parcela=rot.get(k, k), r=v, fracao=v / total) for k, v in parcelas.items()]
            out["u"] = u
    if "curva_sistema" in graf:
        cs = memoria.curva_sistema(r, cfg()["graficos"]["fracoes_vazao"])
        if cs is not None:
            curva, h_est, (q, h) = cs
            out["curva_sistema"] = [dict(q=qq, h=hh, h_est=h_est) for qq, hh in curva]
            out["ponto_bomba"] = [dict(q=q, h=h)]
    if "npsh" in graf:
        n = memoria.npsh(r)
        if n is not None:
            out["npsh"] = [dict(caso=j, npsh_disponivel=d, npsh_exigido=e) for j, d, e in n]
    op = memoria.operacao(r)
    if op is not None:
        out["operacao"] = [dict(caso=nome, **o) for nome, o in op]
        out["tipo_operacao"] = m.method_id
        out["v2"] = dict(r.derivados_v2)
    return out


def _feixe_mais_proximo(rt):
    """MC do trocador inviável: o feixe mais próximo de atender, com os bloqueios por critério e
    caso e a operação de cada caso nele."""
    fp = memoria.feixe_mais_proximo(rt.resultado)
    if fp is None:
        return {}
    bloqueios, row, op, v2 = fp
    nomes = [n for n, *_ in rt.resultado.preparo]
    rot = cfg()["bloqueios"]
    return {"feixe_proximo": dict(x=row.x, l=row.y, d_shell=row.derivados.get("d_shell", math.nan),
                                  bloqueios=[dict(criterio=rot.get(c, c), caso=nomes[i] if i >= 0 else "")
                                             for c, i in bloqueios]),
            "operacao": [dict(caso=n, **o) for n, o in op], "tipo_operacao": rt.entradas.metodo.method_id,
            "v2": v2}


def continuidade(ctx, rt):
    """Rastreabilidade balanço preliminar → rating do P-001 → este MC: as grandezas que o rating
    alterou, antes e depois, caso a caso, a parcela não recuperada pelo P-001 e o fechamento de
    massa e energia do estado operacional. None se o TAG não usa (nem produz) esse estado."""
    e = rt.entradas
    if e.avulso or e.modo == MANUAL or not ctx.balanco_resolvido:
        return None
    if rt.operacao is None and rt.etapa_balanco != ETAPA_RATING:
        return None
    _, op, operacional = ctx.integracao_p001()
    if op is None or op.geometria is None:
        return None
    c = cfg()["continuidade"]
    refs = None if rt.tag.tag == TAG_RATING else referencias_rating(rt.tag)
    grandezas = [g for g in c["grandeza"] if refs is None or g.get("sempre") or g["id"] in refs]
    def valor(estado, g):
        return estado["T"][g["id"]] if g["tipo"] == "temperatura" else estado["duties"][g["id"]]
    lim = criterios_balanco()["fechamento_max"]
    linhas, fechamento = [], dict(tolerancia=lim, em_max=0.0, eE_max=0.0, caso_em=None, caso_eE=None)
    for r in operacional:
        antes, depois = r.antes_do_rating, {"T": r.T, "duties": r.duties}
        nao_recuperado = antes["duties"]["Q_pre"] - r.duties["Q_pre"]
        vals = []
        for g in grandezas:
            pre, pos = valor(antes, g), valor(depois, g)
            vals.append(dict(pre=pre, pos=pos, delta=pos - pre,
                             residuo=(pos - pre - nao_recuperado) if g.get("recebe_nao_recuperado") else None))
        linhas.append(dict(num=r.num, nome=op.caso(r.num).nome, valores=vals, nao_recuperado=nao_recuperado))
        for b in (balanco_global(r), *balancos_por_bloco(r).values()):
            for k, caso in (("em", "caso_em"), ("eE", "caso_eE")):
                if b[k] > fechamento[f"{k}_max"]:
                    fechamento[f"{k}_max"], fechamento[caso] = b[k], r.num
    fechamento["atende"] = fechamento["em_max"] <= lim and fechamento["eE_max"] <= lim
    ref = op.caso_projeto
    return dict(documento_preliminar=c["documento_preliminar"], mc_p001=numero(TAG_RATING)[1],
                arquivo_casos=ctx.dados.origem, sha256=ctx.dados.sha256, proprio=refs is None,
                grandezas=[dict(dict(sempre=False, recebe_nao_recuperado=False), **g) for g in grandezas], linhas=linhas, caso_referencia=ref,
                referencia=next(li for li in linhas if li["num"] == ref) if ref else None,
                geometria=asdict(op.geometria), areas=dict(op.areas), fechamento=fechamento,
                por_tabela=int(c["grandezas_por_tabela"]))


def pendencias(rt):
    e = rt.entradas
    sem_fonte = [dict(chave=k, casos=v) for k, v in _sem_fonte(e).items()]
    return dict(revisoes=[dict(chave=v.chave, valor=v.numero if hasattr(v, "numero") else v.valor, fonte=v.fonte,
                               origem=rotulo_origem(v.origem), estado=v.estado, casos=list(v.casos))
                          for v in e.revisoes()],
                lacunas=[lac.chave for lac in e.lacunas], avisos=[dict(texto=a, casos=n) for a, n in e.avisos()],
                sem_fonte=sem_fonte, limitacoes=limitacoes(), propostas=propostas_usadas(rt))


def propostas_usadas(rt):
    """Valores propostos pelo usuário que entraram no cálculo (origem `proposta`), por
    entrada, com os casos: separados dos valores com fonte e dos calculados."""
    grupos = {}
    for c in rt.entradas.casos:
        if not c.ativo:
            continue
        for k, v in (*c.valores.items(), *c.insumos.items()):
            if v.proposta:
                grupos.setdefault((k, v.valor, v.fonte), []).append(c.num)
    specs, ins = rt.entradas.specs, rt.entradas.tag.insumos
    return [dict(chave=k, rotulo=specs[k].label if k in specs else ins[k]["rotulo"],
                 unidade=specs[k].unit if k in specs else ins[k]["unidade"], valor=v, fonte=f, casos=nums)
            for (k, v, f), nums in grupos.items()]


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
    doc = dict(identificacao=ident, alarme=alarme(rt), conteudo=conteudo_metodo(m), conteudo_tag=cfg().get("tags", {}).get(rt.tag.tag, {}),
               correntes=correntes(ctx, rt), casos=casos(rt), entradas=entradas(rt),
               lacunas=lacunas(rt), premissas=premissas(ctx, rt, ident), pendencias=pendencias(rt),
               operacao_integrada=rt.operacao.estrutura() if rt.operacao is not None else None,
               continuidade=continuidade(ctx, rt), calculo=None)
    r = rt.resultado
    if r is None:
        return doc
    p_env = r.p_env
    if not r.per_case:
        # o motor parou na preparação de um caso (ex.: cruzamento de temperatura): só diagnóstico
        doc["calculo"] = dict(caso_governante="", indice_governante=None, viavel=False, equacoes=[], rastro=[],
                              iteracoes=[], selecao=None, banda=None, tabela=dict(colunas=[], linhas=[], tem_teto=False),
                              criterios=criterios(rt, None), diagnostico=diagnostico(rt, None),
                              resultados=resultados(rt), nao_aplicaveis=nao_aplicaveis(rt),
                              series=_series_do_metodo(rt, conteudo_metodo(m).get("graficos", [])),
                              x_referencia=None,
                              eixo=m.sweep_axis(p_env).label if p_env else "",
                              unidade_eixo=m.sweep_axis(p_env).unit if p_env else "", exigencia=m.requirement_spec())
        return doc
    i = indice_governante(r)
    x = memoria.x_referencia(r)
    sel = memoria.selecao(r, i)
    doc["calculo"] = dict(caso_governante=r.case_names[i], indice_governante=i, viavel=r.feasible,
                          equacoes=equacoes(rt, i, sel),
                          rastro=[dict(bloco=x.block, eq=x.eq, var=x.var, formula=x.formula, valor=x.value,
                                       unidade=x.unit) for x in r.per_case[i].trace],
                          iteracoes=iteracoes(rt, i, "gas"), selecao=sel,
                          banda=memoria.banda(r),
                          tabela=tabela_casos(rt, x), criterios=criterios(rt, x), diagnostico=diagnostico(rt, x),
                          resultados=resultados(rt), nao_aplicaveis=nao_aplicaveis(rt),
                          series=series(rt), x_referencia=x,
                          eixo=m.sweep_axis(p_env).label if p_env else "", unidade_eixo=m.sweep_axis(p_env).unit
                          if p_env else "", exigencia=m.requirement_spec())
    return doc


ESTADOS_MC = {DIMENSIONADO: "dimensionado", INVIAVEL: "diagnostico", AGUARDANDO: "aguardando", INATIVO: "aguardando"}
