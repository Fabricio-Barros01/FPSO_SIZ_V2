"""Resumos de terminal do balanço e do dimensionamento. Invariante 4: só itera descritores
(config/interativo.toml, saida_correntes.toml, ParameterSpec, ResultField, SweepColumn,
trace_blocks); não nomeia grandeza.
"""
import math
import textwrap

from fpso_siz.balanco import indicadores
from fpso_siz.balanco.exportacao import colunas_correntes, tabela_correntes
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.contrato import column_value
from fpso_siz.core.motor import governing_summary
from fpso_siz.output.terminal.estilo import TRAVESSAO, ajustar, largura, num, sig, tabela

NOME_CASO = 44


def cfg():
    return carregar("interativo.toml")


def titulo(texto, estilo, colunas):
    """'━━ texto ━━━…' na largura; texto longo quebra em linhas (nada é cortado)."""
    texto = estilo.t(texto)
    marca = estilo.t("━━ ")
    faixa = colunas - largura(texto) - largura(marca) - 2
    if faixa >= 3:
        return ["", estilo.negrito(marca + texto + " ") + estilo.fraco(estilo.t("━" * faixa))]
    partes = textwrap.wrap(texto, width=max(colunas - largura(marca), 20), break_on_hyphens=False,
                           break_long_words=False)
    return ["", *(estilo.negrito((marca if i == 0 else " " * largura(marca)) + p) for i, p in enumerate(partes))]


def quebrar(texto, colunas, recuo="  "):
    """Quebra em palavras sem partir identificadores (TAG, corrente, chave) no hífen."""
    return textwrap.wrap(texto, width=max(colunas - len(recuo), 20), initial_indent=recuo, subsequent_indent=recuo,
                         break_on_hyphens=False, break_long_words=False)


def casos_lista(nums):
    return ", ".join(str(n) for n in nums)


def curto(nome, n=NOME_CASO):
    """Encurta o nome do caso preservando a etiqueta de canto ("[q_oil↑ …]"), que é o que
    distingue os cantos de uma mesma faixa."""
    if len(nome) <= n:
        return nome
    base, sep, etiqueta = nome.partition(" [")
    if sep:
        cabe = max(n - len(etiqueta) - 3, len(base[:1]) + 1)
        return (base if len(base) <= cabe else base[:cabe - 1] + "…") + " [" + etiqueta
    return nome[:n - 1] + "…"


# ------------------------------------------------------------------ balanço
def contexto_casos(dados, estilo):
    fonte = dados.bruto.get(cfg()["contexto"]["origem"], TRAVESSAO)
    fluidos = list(dados.composicoes)
    return [f"  Arquivo  {dados.origem} · sha256 {dados.sha256[:12]}…",
            f"  Fonte    {fonte}",
            f"  Casos    {len(dados.casos)} · {len(fluidos)} fluidos ({', '.join(fluidos)})",
            f"  Padrão   {sig(dados.T_std_C)} °C · {sig(dados.P_std_kPa)} kPa"]


def tabela_casos(dados, estilo):
    cols = cfg()["casos"]
    linhas = [[num(c.get(k["chave"]), k["casas"]) if "casas" in k else str(c.get(k["chave"], TRAVESSAO))
               for k in cols] for c in dados.casos]
    return tabela([k["rotulo"] for k in cols], linhas, estilo)


def resumo_balanco(resultados, auditoria, dados, prem, descritores, estilo, colunas, segundos=None):
    nao = [r for r in resultados if not r.convergiu]
    tempo = f" · {num(segundos, 2)} s" if segundos is not None else ""
    marca = estilo.ok("✓") if not nao else estilo.erro("✗")
    out = titulo("Balanço de massa e energia", estilo, colunas)
    out.append(f"  {len(resultados)} casos · {len(resultados) - len(nao)} convergidos {marca}{tempo}")
    for r in nao:
        out.append(estilo.aviso(f"  ATENÇÃO caso {r.num}: reciclo não convergiu ({r.iters + 1} iterações, "
                                f"resíduo {r.residuo_reciclo:.3e})"))
    alteradas = [d for d in descritores if d["valor"] is not None and prem[d["nome"]] != d["valor"]]
    if alteradas:
        out.append("  Premissas alteradas: " + "; ".join(
            f"{d['id']} {d['nome']} = {prem[d['nome']]} {d['unidade']} (base {d['valor']})" for d in alteradas))
    else:
        out.append(estilo.fraco("  Premissas: todas no valor de base."))
    out.append(f"  Auditoria independente: {len(auditoria)} verificações recalculadas fora do motor.")
    out += ["", estilo.negrito("  Caso que maximiza cada critério de dimensionamento")]
    rot = cfg()["criticos"]
    linhas = []
    for k, mx, casos in indicadores.criticos(resultados, dados, prem):
        c = rot[k]
        linhas.append([c["equipamento"], c["criterio"], num(mx, c["casas"]), c["unidade"], casos_lista(casos)])
    out += tabela(["Equipamento", "Critério", "Valor", "Unidade", "Caso(s)"], linhas, estilo)
    return out


def tabela_auditoria(auditoria, estilo):
    linhas = [[a["id"], f"{a['max_desvio_abs']:.3e}", a["unidade"]] for a in auditoria]
    return tabela(["Verificação", "Maior |desvio|", "Unidade"], linhas, estilo)


def tabela_correntes_caso(resultados, num_caso, estilo):
    """Colunas escolhidas em interativo.toml; a última (texto) fica sem alinhamento à direita."""
    c = cfg()["correntes"]
    ids = {d["id"] for d in colunas_correntes()}
    faltam = [k["id"] for k in c["colunas"] if k["id"] not in ids]
    if faltam:
        raise KeyError(f"interativo.toml cita colunas que o CSV não tem: {faltam}")
    linhas = [[num(li[k["id"]], k["casas"]) if "casas" in k else str(li[k["id"]]) for k in c["colunas"]]
              for li in tabela_correntes(resultados) if li[c["chave_caso"]] == num_caso]
    return tabela([k["rotulo"] for k in c["colunas"]], linhas, estilo)


# ------------------------------------------------------------------ dimensionamento
def resumo_dimensionamento(eq, m, r, estilo, colunas):
    out = titulo(f"Resultado · {eq.label}", estilo, colunas)
    out.append(estilo.t(f"  Método: {m.label}"))
    if r.feasible:
        out.append("  " + estilo.ok(estilo.t("✓ Viável")))
    else:
        out.append("  " + estilo.erro(estilo.t("✗ Inviável")))
    out += [""]
    campos = m.result_fields(r)
    rot = max(largura(estilo.t(f.label)) for f in campos)
    for f in campos:
        valor = num(f.value, f.digits) + (f" {f.unit}" if f.unit and num(f.value, f.digits) != TRAVESSAO else "")
        valor = estilo.t(valor)
        valor = estilo.destaque(valor) if f.highlight else valor
        simbolo = ajustar(estilo.t(estilo.status(f.status)), largura(estilo.t(estilo.status("ok"))))
        out.append(f"  {simbolo} {ajustar(estilo.t(f.label), rot)}  {valor}")
    out.append("")
    out += quebrar(estilo.t(governing_summary(m, r)), colunas)
    if r.case_names:
        out += ["", estilo.negrito("  Casos")] + tabela_por_caso(m, r, estilo, colunas)
    return out


def tabela_por_caso(m, r, estilo, colunas):
    """Cada caso sozinho (o que ele escolheria) e a folga dele no equipamento do envelope."""
    col_x = m.sweep_columns()[0]
    req, und = m.requirement_spec()
    cab = ["Caso", "Sozinho", col_x.label]
    if r.feasible:
        cab.append(f"Folga ({und})" if und else "Folga")
    linhas = []
    for i, (nome, pc) in enumerate(zip(r.case_names, r.per_case)):
        li = [curto(nome), estilo.ok("viável") if pc.feasible else estilo.erro("inviável"), num(pc.x, col_x.digits)]
        if r.feasible:
            li.append(num(r.slack[i], 2) if i < len(r.slack) else TRAVESSAO)
        linhas.append(li)
    out = tabela(cab, linhas, estilo)
    if r.feasible:
        nota = f"Folga = {req} do envelope − o que o caso exige; 0 no caso governante."
        out += [estilo.fraco(s) for s in quebrar(estilo.t(nota), colunas)]
    return out


def tabela_varredura(m, r, estilo):
    cols = m.sweep_columns()
    cab = [c.label for c in cols] + ["Governa", "Caso", "Adm."]
    linhas = []
    for row in r.rows:
        escolhido = r.feasible and row.x == r.x
        li = [num(column_value(row, c), c.digits) for c in cols]
        li += [m.governing_label(row.governing), curto(row.driver_case),
               (estilo.ok("✓") if row.ok else estilo.erro("✗")) + (" ◀" if escolhido else "")]
        linhas.append([estilo.destaque(c) for c in li] if escolhido else li)
    return tabela(cab, linhas, estilo)


def rastro_blocos(tr, titulos, estilo, colunas):
    """Um Rastro, bloco a bloco: [equação] variável = valor unidade, e a fórmula/fonte."""
    out = []
    for bloco in tr.block_order():
        out += ["", estilo.negrito(estilo.t(f"  {titulos.get(bloco, bloco)}"))]
        for e in tr.block_entries(bloco):
            eq = "" if e.eq in ("", TRAVESSAO) else estilo.fraco(estilo.t(f"[{e.eq}] "))
            val = sig(e.value) + (f" {e.unit}" if e.unit and e.unit != "–" else "")
            out.append(estilo.t(f"    {eq}{e.var} = {val}"))
            if e.formula:
                out += [estilo.fraco(s) for s in quebrar(estilo.t(e.formula), colunas, recuo="        ")]
    return out


def rastro(m, sr, estilo, colunas):
    """Rastro de cálculo de um caso, bloco a bloco (mesma fonte do memorial)."""
    out = rastro_blocos(sr.trace, dict(m.trace_blocks()), estilo, colunas)
    if not math.isfinite(sr.x) and sr.message:
        out += [""] + quebrar(estilo.t(sr.message), colunas)
    return out
