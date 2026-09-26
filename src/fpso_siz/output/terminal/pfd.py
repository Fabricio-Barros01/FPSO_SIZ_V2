"""Telas da planta e de um equipamento/TAG: esquema, estados, pendências, recomendações,
entradas com Origem e resultado. Composição só; os dados vêm do serviço por TAG
(pfd/equipamento.py) e os textos de config/interativo.toml. Invariante 4: itera
descritores (ParameterSpec, ResultField, Lacuna, Revisao), nunca nomeia parâmetro, TAG ou
corrente."""
from fpso_siz.balanco.balancos import topologia
from fpso_siz.output.terminal import esquema
from fpso_siz.output.terminal.estilo import TRAVESSAO, largura, num, sig, tabela
from fpso_siz.output.terminal.relatorio import cfg, quebrar, resumo_dimensionamento, titulo
from fpso_siz.pfd.ajustes import MANUAL
from fpso_siz.pfd.equipamento import AGUARDANDO, DIMENSIONADO, ESTADOS, INATIVO, INVIAVEL

MAX_DETALHE = 3   # recomendações listadas por TAG no resumo do comando `pfd`


def textos():
    return cfg()["textos"]


def faixa_casos(nums):
    """[1, 2, 3, 5] → '1–3, 5'."""
    nums = sorted(nums)
    partes, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        partes.append(str(nums[i]) if i == j else f"{nums[i]}–{nums[j]}")
        i = j + 1
    return ", ".join(partes) or TRAVESSAO


def rotulo_estado(status):
    return cfg()["pfd"]["estados"][status]


def marcador(status, estilo):
    m = estilo.t(cfg()["pfd"]["marcadores"][status])
    cor = {DIMENSIONADO: estilo.ok, AGUARDANDO: estilo.aviso, INVIAVEL: estilo.erro, INATIVO: estilo.fraco}[status]
    return cor(m)


def estado_colorido(status, estilo):
    txt = estilo.t(rotulo_estado(status))
    cor = {DIMENSIONADO: estilo.ok, AGUARDANDO: estilo.aviso, INVIAVEL: estilo.erro, INATIVO: estilo.fraco}[status]
    return cor(txt)


def contagem(resultados):
    n = {s: sum(r.status == s for r in resultados) for s in ESTADOS}
    return textos()["contagem"].format(dimensionado=n[DIMENSIONADO], aguardando=n[AGUARDANDO],
                                       inviavel=n[INVIAVEL], inativo=n[INATIVO])


def origem_tela(v):
    rot = cfg()["origens_tela"][v.origem]
    if v.origem == "premissa":  # a premissa mantém seu identificador (P-xx)
        return f"{rot} {v.fonte.split(' ')[0]}"
    return rot


def valor_texto(v):
    if v.lacuna or v.nao_aplicavel:
        return TRAVESSAO
    if v.faixa:
        return f"{sig(v.faixa[0])} – {sig(v.faixa[1])}"
    return sig(v.valor)


def faixa_descritor(f):
    return f"{sig(f[0])}–{sig(f[1])}" if f else TRAVESSAO


def tabela_ajustada(decl, linhas, estilo, colunas, chave, recuo="  "):
    """Tabela das colunas declaradas (id, rótulo, prioridade). Se não couber, as colunas
    de maior prioridade saem da tabela e viram linhas de detalhe — nada é truncado."""
    ativas = list(decl)
    while True:
        out = tabela([c["rotulo"] for c in ativas], [[li[c["id"]] for c in ativas] for li in linhas], estilo, recuo)
        opcionais = [c for c in ativas if c["prioridade"] > 0]
        if max(largura(x) for x in out) <= colunas or not opcionais:
            break
        ativas.remove(max(opcionais, key=lambda c: c["prioridade"]))
    removidas = [c for c in decl if c not in ativas]
    for li in linhas:
        for c in removidas:
            if li[c["id"]] not in ("", TRAVESSAO):
                out += [estilo.fraco(x) for x in quebrar(estilo.t(f"{li[chave]} · {c['rotulo']}: {li[c['id']]}"),
                                                         colunas, recuo + "  ")]
    return out


# ------------------------------------------------------------------ planta
def marcadores(resultados, estilo, caso=None):
    """{bloco: marcador} dos TAGs. Com `caso`, inativo nele vira '-'; senão, o estado do
    envelope (a atividade num caso não se confunde com a viabilidade do envelope)."""
    out = {}
    for r in resultados:
        st = r.status
        if caso is not None and not next(c for c in r.entradas.casos if c.num == caso).ativo:
            st = INATIVO
        out[r.tag.bloco] = marcador(st, estilo)
    return out


def _resultado_curto(r):
    if r.resultado is None or not r.resultado.feasible:
        return TRAVESSAO
    campos = [f for f in r.entradas.metodo.result_fields(r.resultado) if f.highlight]
    return "; ".join(f"{f.label}: {num(f.value, f.digits)} {f.unit}" for f in campos) or TRAVESSAO


def tabela_tags(resultados, estilo, colunas):
    linhas = [{"tag": r.tag.tag, "estado": estado_colorido(r.status, estilo),
               "ativos": str(sum(c.ativo for c in r.entradas.casos)), "resultado": _resultado_curto(r),
               "governante": r.resultado.driver_case if r.resultado is not None and r.resultado.feasible
               else TRAVESSAO} for r in resultados]
    return tabela_ajustada(cfg()["colunas_planta"], linhas, estilo, colunas, "tag")


def tela_planta(ctx, resultados, estilo, colunas, caso=None, topo=None):
    topo = topo if topo is not None else topologia()
    tx = textos()
    nums = [c["num"] for c in ctx.dados.casos]
    if caso is None:
        cab = tx["titulo_planta"].format(arquivo=ctx.dados.origem, casos=faixa_casos(nums))
    else:
        nome = next(c.nome for c in resultados[0].entradas.casos if c.num == caso)
        cab = tx["titulo_planta_caso"].format(arquivo=ctx.dados.origem, caso=nome)
    out = titulo(estilo.t(cab), estilo, colunas)
    out += quebrar(estilo.t(contagem(resultados)), colunas)
    out.append("")
    out += esquema.planta(topo, marcadores(resultados, estilo, caso), estilo, colunas)
    out.append("")
    leg = cfg()["pfd"]["legenda"]
    out += [estilo.fraco(x) for x in quebrar(estilo.t(leg["estados"]), colunas)]
    out += [estilo.fraco(x) for x in quebrar(estilo.t(leg["blocos"]), colunas)]
    if caso is not None:
        out += [estilo.fraco(x) for x in quebrar(estilo.t(tx["nota_filtro"]), colunas)]
    out.append("")
    out += tabela_tags(resultados, estilo, colunas)
    return [estilo.t(x) for x in out]


def detalhes_planta(resultados, estilo, colunas):
    """Por TAG: o que falta, recomendações em revisão, inviabilidade, inativos, avisos."""
    tx = textos()
    out = []
    for r in resultados:
        e, res = r.entradas, r.resultado
        linhas = []
        for l in e.lacunas:
            linhas += quebrar(estilo.t(f"! {l.chave} — {l.rotulo} [{l.unidade}]; casos {faixa_casos(l.casos)}"),
                              colunas, "    ")
        revs = e.revisoes()
        for x in revs[:MAX_DETALHE]:
            s = e.specs[x.chave]
            linhas += quebrar(estilo.t(f"{cfg()['revisao_tela'][x.estado]}: {s.label} = "
                                       f"{_numero(x.valor)} {s.unit} ({cfg()['origens_tela'][x.origem]}); "
                                       f"casos {faixa_casos(x.casos)}"), colunas, "    ")
        if len(revs) > MAX_DETALHE:
            linhas += quebrar(estilo.t(f"… +{len(revs) - MAX_DETALHE}"), colunas, "    ")
        if res is not None and res.message:
            linhas += quebrar(estilo.t(res.message), colunas, "    ")
        inativos = [c.num for c in e.casos if not c.ativo]
        if inativos:
            linhas += quebrar(estilo.t(tx["casos_inativos"].format(lista=faixa_casos(inativos))), colunas, "    ")
        if e.avisos():
            linhas += quebrar(estilo.t(tx["avisos_n"].format(n=len(e.avisos()))), colunas, "    ")
        if linhas:
            out += ["", estilo.negrito(estilo.t(f"  {r.tag.tag} — {r.tag.nome}")), *linhas]
    return out


def resumo(planta, estilo, colunas, caso=None):
    """Tela da planta e o detalhe por TAG (comando `pfd`)."""
    out = tela_planta(planta.contexto, planta.tags, estilo, colunas, caso)
    out += detalhes_planta(planta.tags, estilo, colunas)
    out += ["", *quebrar(estilo.t(textos()["blocos_sem"].format(lista=", ".join(planta.sem_dimensionamento))),
                         colunas)]
    return [estilo.t(x) for x in out]


# ------------------------------------------------------------------ TAG
def _numero(x):
    return f"{sig(x[0])} – {sig(x[1])}" if isinstance(x, tuple) else sig(x)


def modo_texto(rt):
    tx = textos()
    e = rt.estado
    if rt.entradas.modo != MANUAL:
        return tx["modo_automatico"]
    return tx["modo_manual_arquivo"].format(arquivo=e.arquivo) if e is not None and e.arquivo else tx["modo_manual"]


def cabecalho_tag(ctx, rt, estilo, colunas):
    e = rt.entradas
    tx = textos()
    out = titulo(estilo.t(f"{rt.tag.tag} · {rt.tag.nome}"), estilo, colunas)
    nums = [c.num for c in e.casos]
    out += quebrar(estilo.t(f"casos {faixa_casos(nums)} · {modo_texto(rt)} · ") + estado_colorido(rt.status, estilo),
                   colunas)
    if e.modo != MANUAL and not e.avulso:
        prem = ", ".join(f"{k} = {v}" for k, v in ctx.alteracoes.items()) or tx["premissas_base_curto"]
        out += quebrar(estilo.t(tx["contexto_auto"].format(arquivo=ctx.dados.origem, sha=ctx.dados.sha256[:12],
                                                           premissas=prem)), colunas)
    return out


def esquema_tag(rt, estilo, colunas, topo=None):
    if rt.entradas.avulso:
        return quebrar(estilo.t(textos()["avulso_sem_esquema"]), colunas)
    topo = topo if topo is not None else topologia()
    return esquema.local(topo, rt.tag.bloco, marcador(rt.status, estilo), estilo, colunas)


def alerta_lacunas(rt, estilo, colunas):
    e = rt.entradas
    if not e.lacunas:
        return []
    tx = textos()
    afetados = sorted({n for l in e.lacunas for n in l.casos})
    out = [estilo.aviso(estilo.negrito(estilo.t("  " + tx["alerta_lacunas"].format(n=len(e.lacunas),
                                                                                   casos=len(afetados)))))]
    linhas = [{"chave": l.chave, "entrada": l.rotulo, "unidade": l.unidade, "casos": faixa_casos(l.casos)}
              for l in e.lacunas]
    out += tabela_ajustada(cfg()["colunas_lacunas"], linhas, estilo, colunas, "chave")
    for l in e.lacunas:
        det = [f"{l.chave}:"]
        if l.faixa:
            det.append(tx["lacuna_faixa"].format(faixa=faixa_descritor(l.faixa)))
        det.append(tx["lacuna_valor"])
        if l.dica:
            det.append(tx["lacuna_dica"].format(dica=l.dica))
        if l.dependentes:
            det.append(tx["lacuna_dependentes"].format(lista=", ".join(l.dependentes)))
        out += [estilo.fraco(x) for d in det for x in quebrar(estilo.t(d), colunas, "    ")]
    return out


def linhas_revisao(rt):
    e = rt.entradas
    return [{"item": str(i), "chave": x.chave, "valor": _numero(x.valor), "unidade": e.specs[x.chave].unit,
             "casos": faixa_casos(x.casos),
             "origem": f"{cfg()['origens_tela'][x.origem]} · {cfg()['revisao_tela'][x.estado]}",
             "fonte": x.fonte} for i, x in enumerate(e.revisoes(), 1)]


def bloco_revisoes(rt, estilo, colunas):
    linhas = linhas_revisao(rt)
    if not linhas:
        return []
    tx = textos()
    out = ["", estilo.negrito(estilo.t("  " + tx["titulo_revisoes"]))]
    out += tabela_ajustada(cfg()["colunas_revisoes"], linhas, estilo, colunas, "chave")
    out += [estilo.fraco(x) for x in quebrar(estilo.t(tx["nota_revisoes"]), colunas)]
    return out


def tabela_entradas(rt, num_caso, estilo, colunas):
    e = rt.entradas
    c = e.caso(num_caso)
    tx = textos()
    out = ["", estilo.negrito(estilo.t("  " + tx["titulo_entradas"].format(caso=c.nome)))]
    if not c.ativo:
        out += quebrar(estilo.t(f"{rotulo_estado(INATIVO)}: {c.motivo}"), colunas)
    linhas = []
    for k, v in c.valores.items():
        s = e.specs[k]
        fonte = v.fonte if not v.lacuna else (", ".join(p for p in v.pendente if p != k) or v.fonte)
        if v.anterior is not None:
            fonte += f" [{cfg()['origens_tela'][v.anterior['origem']]}: {_numero(v.anterior['valor']) if v.anterior['valor'] is not None else TRAVESSAO}]"
        linhas.append({"chave": k, "entrada": s.label, "valor": valor_texto(v), "unidade": s.unit,
                       "origem": origem_tela(v), "revisao": cfg()["revisao_tela"].get(v.revisao, ""),
                       "fonte": fonte})
    for k, v in c.insumos.items():
        ins = e.tag.insumos[k]
        linhas.append({"chave": k, "entrada": ins["rotulo"], "valor": valor_texto(v), "unidade": ins["unidade"],
                       "origem": origem_tela(v), "revisao": "", "fonte": v.fonte})
    out += tabela_ajustada(cfg()["colunas_entradas"], linhas, estilo, colunas, "chave")
    for aviso in c.avisos:
        out += [estilo.aviso(x) for x in quebrar(estilo.t(f"! {aviso}"), colunas)]
    return [estilo.t(x) for x in out]


def bloco_resultado(rt, estilo, colunas):
    e, r = rt.entradas, rt.resultado
    tx = textos()
    out = []
    inativos = [c for c in e.casos if not c.ativo]
    if inativos:
        lista = "; ".join(f"{c.num} ({c.motivo})" for c in inativos)
        out += [""] + quebrar(estilo.t(tx["casos_inativos"].format(lista=lista)), colunas)
    if rt.status == INATIVO:
        return out + [""] + quebrar(estilo.t(tx["inativo_todo"]), colunas)
    if r is None:
        return out + [""] + [estilo.aviso(x) for x in quebrar(estilo.t(tx["pendente_sem_resultado"]), colunas)]
    out += [estilo.t(x) for x in resumo_dimensionamento(e.equipamento, e.metodo, r, estilo, colunas)]
    if e.preliminar:
        out += [""] + [estilo.aviso(x) for x in quebrar(estilo.t(tx["preliminar"].format(n=len(e.revisoes()))),
                                                        colunas)]
    if e.avisos():
        out += quebrar(estilo.t(tx["avisos_n"].format(n=len(e.avisos()))), colunas)
    out += [estilo.fraco(x) for x in quebrar(estilo.t(tx["memorial_disponivel"]), colunas)]
    return out


def tela_tag(ctx, rt, estilo, colunas, topo=None):
    out = cabecalho_tag(ctx, rt, estilo, colunas)
    out += [""] + esquema_tag(rt, estilo, colunas, topo)
    lac = alerta_lacunas(rt, estilo, colunas)
    if lac:
        out += [""] + lac
    out += bloco_revisoes(rt, estilo, colunas)
    out += bloco_resultado(rt, estilo, colunas)
    return [estilo.t(x) for x in out]


def tabela_estado(ajustes, estilo):
    tx = textos()
    linhas = []
    for e in ajustes.todos():
        n = len(e.geral) + sum(len(d) for d in e.por_caso.values())
        linhas.append([e.id, e.modo, str(n), str(len(e.revisoes)), e.arquivo or TRAVESSAO])
    return tabela(tx["estado_colunas"], linhas, estilo)
