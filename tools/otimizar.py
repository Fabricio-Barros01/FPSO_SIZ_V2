"""F15 — otimização multiobjetivo do módulo (docs/validacao/23-otimizacao.md + frente em JSON/CSV).

Roda o NSGA-II/III pela porta única `fpso_siz/_otim.py` sobre o avaliador puro
`pfd/otimizacao.py`, com as variáveis, objetivos e restrições declarados em
config/pfd/otimizacao.toml. Determinístico (semente fixa) e LENTO: cada indivíduo roda o balanço
e os TAGs da planta (cerca de 3 s no problema completo).

**A pré-condição do documento 0003 — nenhum alarme aberto — ainda NÃO está satisfeita**: o
P-002 e o P-003 fecharam (docs/validacao/24-pelicula-baixo-reynolds.md); o P-001 é a geometria
instalada por rating, com o comprimento do tubo como decisão pendente (docs/validacao/46, 47).
Toda rodada é ESTUDO, e nenhum ponto da frente é recomendação de projeto. A comparação finita de
configurações é `tools/comparar_configuracoes.py`.

    uv run python tools/otimizar.py [--sub sg_001] [--populacao N] [--geracoes N] [--semente N]
                                    [--varredura] [--saida docs/validacao/23-otimizacao.md]

Subproblema de pressão (docs/validacao/42): `--sub pressao` roda a grade-oráculo, o NSGA-II, a
conferência da frente na resolução da grade e a ficha de cada ponto da frente, reavaliado fora do
otimizador; `--repetir` roda o algoritmo de novo com a mesma semente e compara.

    uv run python tools/otimizar.py --sub pressao [--repetir] [--saida docs/validacao/otimizacao_pressao]
"""
import argparse
import csv
import json
import math
import os
import pickle
from collections import Counter
from pathlib import Path

from fpso_siz import _otim
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd import propostas as mod_propostas

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def f(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ponto_do_projeto(dados, sub):
    """O vetor de decisão do projeto atual (a mesma regra da comparação: `ot.ponto_referencia`)."""
    return ot.ponto_referencia(dados, sub)


def tabela_declaracao(sub):
    out = ["| Variável | Tipo | Limites | Origem dos limites |", "|---|---|---|---|"]
    for v in ot.variaveis(sub):
        out.append(f"| {v['rotulo']} (`{v['id']}`) | {v['tipo']} | {f(v['min'], 3)} – {f(v['max'], 3)} | "
                   f"{v['fonte']} |")
    out += ["", "| Objetivo | Unidade | Como é somado | Fonte |", "|---|---|---|---|"]
    for o in ot.objetivos(sub):
        como = (f"soma de `{o['derivado']}` em {', '.join(o['tags'])}" if o["tipo"] == "soma_derivado" else
                f"soma da área `{o['base']}` em {', '.join(o['tags'])}" if o["tipo"] == "soma_area_troca" else
                f"{' + '.join(o['cargas'])} ({o['agregacao']}, {o.get('etapa', 'preliminar')})")
        out.append(f"| {o['rotulo']} (`{o['id']}`) | {o['unidade']} | {como} | {o['fonte']} |")
    return out


# Os quatro desfechos possíveis de um PONTO, distintos do status de cada TAG. "não avaliável"
# não é um jeito educado de dizer inviável: é falta de dado, e não pode virar viabilidade.
SITUACAO = {"viavel": "viável", "verificacao_incompleta": "admissível, com verificação incompleta (não aprovado)",
            "decisao_pendente": "admissível, com decisão de projeto pendente (não aprovado)",
            "inviavel": "inviável",
            "nao_avaliavel": "não avaliável (lacuna de entrada ou grandeza sem solução)",
            "nao_convergiu": "balanço não convergiu"}


def contagem(avaliacoes):
    """"n inviáveis, m não avaliáveis" — a composição real de um conjunto de pontos. Dizer
    "todos inviáveis" quando parte deles só esperava dado seria a confusão que a F15 desfez."""
    n = Counter(a.situacao for a in avaliacoes)
    return ", ".join(f"{n[s]} {SITUACAO[s]}" for s in SITUACAO if n[s]) or "nenhum ponto avaliado"


def linha_ponto(a, ids_var, ids_obj, sub=None):
    """A linha de um ponto. Variável inteira aparece DECODIFICADA (o algoritmo caminha no
    contínuo e a decodificação arredonda): mostrar 2,8869 trens seria mentir sobre o que foi
    avaliado."""
    tipos = {v["id"]: v["tipo"] for v in ot.variaveis(sub)}
    xs = " · ".join(f"{i} = {f(round(v), 0) if tipos[i] == 'inteiro' else f(v, 4)}"
                    for i, v in zip(ids_var, a.x))
    objs = " · ".join(f"{i} = {f(a.objetivos[i])}" for i in ids_obj)
    viol = ", ".join(f"{t} {f(g, 3)}" for t, g in a.restricoes.items() if g > 0) or "—"
    return f"| {xs} | {objs} | {viol} | {SITUACAO[a.situacao]} |"


def secao(dados, sub, populacao, geracoes, semente, com_varredura, titulo, proposito, processos):
    """Uma rodada: declaração, ponto do projeto, frente e (opcional) conferência exaustiva.
    Devolve (linhas do relatório, dados para o JSON, avaliações para o CSV)."""
    ids_var = [v["id"] for v in ot.variaveis(sub)]
    ids_obj = [o["id"] for o in ot.objetivos(sub)]
    x0 = ponto_do_projeto(dados, sub)
    a0 = ot.avaliar(dados, x0, sub=sub)
    frente, hist, meta = _otim.otimizar(dados, populacao=populacao, geracoes=geracoes, semente=semente,
                                        sub=sub, processos=processos)
    viaveis = [a for a in hist if a.viavel]
    sem_dado = [a for a in hist if a.situacao == "nao_avaliavel"]
    front_hist = ot.nao_dominados([a.objetivos for a in viaveis], ids_obj) if viaveis else []
    out = [f"## {titulo}", "", proposito, "", "### O que a rodada pôde mexer", ""]
    out += tabela_declaracao(sub)
    out += ["", f"Recorte: **{meta['subproblema']}**. TAGs restringidos: "
            f"{', '.join(meta['tags_restritas'])}.", "",
            f"Algoritmo **{meta['algoritmo']}** (pymoo {meta['pymoo']}), população {meta['populacao']}, "
            f"{meta['geracoes']} gerações, semente {meta['semente']}, {meta['avaliacoes']} avaliações "
            f"(avaliadas em {meta['processos']} processo(s); o paralelismo não muda o resultado — o algoritmo "
            "segue sequencial e a ordem é preservada).", "",
            "### O ponto do projeto atual", "",
            "| Variáveis | Objetivos | Violações | Estado |", "|---|---|---|---|",
            linha_ponto(a0, ids_var, ids_obj, sub), "",
            "Critério de validação 1 do 0003: o avaliador reproduz o ponto do projeto atual — os estados por TAG "
            "são os mesmos que o `fpso-siz pfd` publica hoje.", "",
            "### Frente de Pareto", ""]
    if not viaveis:
        out += [f"Nenhum indivíduo viável, e a frente é vazia: {contagem(hist)}. **Isto é o resultado da "
                "rodada**, e é exatamente a razão da pré-condição do 0003 — otimizar sobre um modelo que ainda "
                "dá \"nenhum equipamento atende\" seria otimizar um erro.", "",
                "A rodada continua útil como diagnóstico: a coluna de violações mostra qual TAG barra cada ponto e "
                "quanto falta.", ""]
    else:
        out += ["| Variáveis | Objetivos | Violações | Estado |", "|---|---|---|---|"]
        for a in sorted(viaveis, key=lambda a: tuple(a.objetivos[i] for i in ids_obj)):
            if a.objetivos in front_hist:
                out.append(linha_ponto(a, ids_var, ids_obj, sub))
        out.append("")
        if len(front_hist) == 1:
            out += ["A frente tem **um ponto só**, e isso é resultado, não falha da rodada: neste recorte os dois "
                    "objetivos melhoram na mesma direção (mais trens reduzem o volume por vaso, e η maior reduz a "
                    "carga de aquecimento), então não há troca a mostrar — o conjunto de Pareto degenera num ponto.",
                    ""]
    if sem_dado:
        out += [f"{len(sem_dado)} dos {len(hist)} pontos ficaram **não avaliáveis**: algum TAG restringido "
                "esperava entrada (lacuna). Eles não entram na frente — falta de dado não é viabilidade —, e o "
                "que eles pedem é dado, não ajuste de projeto.", ""]
    avaliacoes = [a for a in hist]
    if com_varredura:
        ref = _otim.avaliar_pontos(dados, ot.grade(sub), sub=sub, processos=processos)
        ref_viaveis = [a for a in ref if a.viavel]
        frente_ref = ot.nao_dominados([a.objetivos for a in ref_viaveis], ids_obj)
        out += ["### Conferência contra varredura exaustiva (critério 2 do 0003)", "",
                f"Grade declarada em `config/pfd/otimizacao.toml`: {len(ref)} pontos; "
                f"{len(ref_viaveis)} viáveis, {len(frente_ref)} não dominados.", "",
                "| Variáveis | Objetivos | Violações | Estado |", "|---|---|---|---|"]
        for a in sorted(ref_viaveis, key=lambda a: tuple(a.objetivos[i] for i in ids_obj)):
            if a.objetivos in frente_ref:
                out.append(linha_ponto(a, ids_var, ids_obj, sub))
        dominados = [p for p in front_hist if any(ot.domina(q, p, ids_obj) for q in frente_ref)]
        out += ["", ("Nenhum ponto da varredura domina um ponto da frente do algoritmo." if not dominados
                     else f"**{len(dominados)} ponto(s) da frente do algoritmo são dominados pela varredura** — "
                          "a rodada não convergiu; aumente população ou gerações."), ""]
        # inviável é o ponto que FOI julgado e não atende. O que esperava dado, ou cujo balanço
        # não convergiu, não é fronteira de viabilidade — vai numa lista à parte.
        inviaveis = [a for a in ref if a.situacao == "inviavel"]
        outros = [a for a in ref if a.situacao not in ("viavel", "inviavel")]
        if inviaveis:
            barrando = sorted({t for a in inviaveis for t, g in a.restricoes.items() if g > 0})
            out += ["#### Fronteira de viabilidade encontrada na grade", "",
                    f"{len(inviaveis)} dos {len(ref)} pontos da grade são **inviáveis**, e quem os barra é: "
                    f"{', '.join(barrando)}. Isto é resultado da rodada: a otimização encontrou uma fronteira de "
                    "viabilidade DENTRO de uma faixa que a fonte declara admissível, e ela é pendência de decisão "
                    "do usuário, não algo que a otimização possa resolver escolhendo um valor.", "",
                    "| Variáveis | Objetivos | Violações | Estado |", "|---|---|---|---|"]
            for a in sorted(inviaveis, key=lambda a: a.x):
                out.append(linha_ponto(a, ids_var, ids_obj, sub))
            out.append("")
        if outros:
            out += ["#### Pontos da grade que não puderam ser julgados", "",
                    f"{len(outros)} dos {len(ref)} pontos não são inviáveis: {contagem(outros)}. Eles não dizem "
                    "nada sobre viabilidade — o que falta neles é **dado**, e é isso que precisa ser fornecido "
                    "antes de a faixa ser lida como fronteira de projeto.", "",
                    "| Variáveis | Objetivos | Violações | Estado |", "|---|---|---|---|"]
            for a in sorted(outros, key=lambda a: a.x):
                out.append(linha_ponto(a, ids_var, ids_obj, sub))
            out.append("")
        avaliacoes = avaliacoes + ref
    dados_json = {"meta": meta, "variaveis": ids_var, "objetivos": ids_obj,
                  "projeto_atual": {"x": list(x0), "objetivos": a0.objetivos, "restricoes": a0.restricoes,
                                    "estados": a0.estados},
                  "frente": [{"x": list(a.x), "objetivos": a.objetivos, "restricoes": a.restricoes}
                             for a in viaveis if a.objetivos in front_hist]}
    return out, dados_json, ids_var, ids_obj, avaliacoes


def gerar(dados, populacao, geracoes, semente, destino_dados, rodadas=None, processos=None):
    """O relatório inteiro: o problema completo (diagnóstico da pré-condição) e o subproblema
    declarado (validação contra varredura exaustiva)."""
    rodadas = rodadas if rodadas is not None else [
        (None, False, "Rodada 1 — problema completo (diagnóstico)",
         "Todas as variáveis, os três objetivos e os onze TAGs. Esta rodada existe para MOSTRAR o efeito dos "
         "alarmes abertos, não para recomendar projeto."),
        ("sg_001", True, "Rodada 2 — subproblema do SG-001 (validação)",
         "O recorte do critério de validação 2 do 0003: pequeno o bastante para a frente ser conferida contra uma "
         "varredura exaustiva da mesma grade."),
    ]
    out = ["# F15 — otimização multiobjetivo do módulo (estudo)", "",
           "Gerado por `tools/otimizar.py`; a frente sai do NSGA-II/III pela porta única `fpso_siz/_otim.py`, e "
           "cada avaliação é o mesmo serviço por TAG do `pfd` — a otimização não fala com o motor.", "",
           "## Aviso de pré-condição", "",
           "O documento `docs/decisoes/0003-otimizacao-pymoo.md` exige **nenhum alarme aberto** antes da primeira "
           "rodada. Os alarmes do **P-002 e do P-003 fecharam** quando a película do lado tubo passou a ter os "
           "três regimes (`docs/validacao/24-pelicula-baixo-reynolds.md`). O **P-001** deixou de ser DESIGN "
           "inviável: é a geometria instalada avaliada por rating (ADR 0005), com recuperação parcial aceita e "
           "o comprimento do tubo como **decisão pendente** (`docs/validacao/46`); por isso nenhum ponto que o "
           "contém sai como viável (`decisao_pendente`). **Toda rodada aqui é estudo, e nenhum ponto da frente "
           "é recomendação de projeto** (`docs/validacao/47`).", "",
           "Um TAG replicado (`fator_vazao`) é dimensionado como UMA unidade, com a vazão dividida pelo número "
           "de unidades; os objetivos que somam um derivado extensivo dele somam o valor unitário **vezes o "
           "número de unidades**.", ""]
    pacote, todas = {}, []
    for sub, varredura, titulo, proposito in rodadas:
        linhas, dados_json, ids_var, ids_obj, avaliacoes = secao(dados, sub, populacao, geracoes, semente,
                                                                varredura, titulo, proposito, processos)
        out += linhas
        pacote[sub or "completo"] = dados_json
        todas.append((sub or "completo", ids_var, ids_obj, avaliacoes))
    destino_dados.with_suffix(".json").write_text(json.dumps(pacote, indent=2, ensure_ascii=False,
                                                            sort_keys=True) + "\n", encoding="utf-8")
    # um CSV por rodada, LARGO (uma linha por avaliação): as rodadas têm variáveis diferentes, e
    # é essa forma que se lê ao reproduzir um ponto
    arquivos = []
    for nome, ids_var, ids_obj, avaliacoes in todas:
        caminho = destino_dados.with_name(f"{destino_dados.name}-{nome}").with_suffix(".csv")
        with caminho.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            # `situacao` distingue os quatro desfechos; `viavel` fica pelo histórico do formato,
            # e é o que ela seria: 1 só quando a situação é "viavel"
            w.writerow([*ids_var, *ids_obj, "violacao_total", "situacao", "viavel"])
            for a in avaliacoes:
                w.writerow([*a.x, *(a.objetivos[i] for i in ids_obj), a.violacao_total, a.situacao,
                            int(a.viavel)])
        arquivos.append((caminho, nome, len(avaliacoes)))
    out += ["## Arquivos", "",
            f"- `{destino_dados.with_suffix('.json').name}`: por rodada, a frente, o ponto do projeto e os "
            "metadados (algoritmo, versão do pymoo, semente)."]
    for caminho, nome, n in arquivos:
        out.append(f"- `{caminho.name}`: as {n} avaliações da rodada `{nome}`, uma por linha, para reproduzir "
                   "qualquer ponto com `fpso-siz pfd --ajustes`.")
    out.append("")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ subproblema de pressão (docs/validacao/42)
def ficha(dados, x, sub):
    """As grandezas de um ponto, lidas do mesmo serviço (Contexto → resolver_todos → TAGs), fora do
    otimizador: gás por estágio e potências das bombas (máximo entre os 16 casos, com o caso), a
    carga da VRU e a TVP máxima com o caso que as governa, e cada vaso restringido."""
    s = ot.subproblema(sub)
    prem, _, _ = ot.decodificar(x, sub)
    ctx = servico.Contexto(dados, alteracoes=prem, propostas=mod_propostas.padrao())
    b = ctx.balanco
    out = {v["id"]: float(xi) for v, xi in zip(ot.variaveis(sub), x)}
    for chave in [*s["relatorio_gas"], *s["relatorio_potencias"]]:
        campo = "gas" if chave in s["relatorio_gas"] else "duties"
        out[chave], out[chave + "_caso"] = max((float(getattr(r, campo)[chave]), r.num) for r in b)
    for o in ot.objetivos(sub):
        if o["tipo"] == "carga_balanco":
            campo = o.get("campo", "duties")
            out[o["id"] + "_caso"] = max((sum(getattr(r, campo)[c] for c in o["cargas"]), r.num) for r in b)[1]
    for rb in ot.restricoes_balanco(sub):
        g, caso = ot.restricao_balanco(rb, b)
        out[rb["id"] + "_max"], out[rb["id"] + "_caso"] = (g + 1) * ot.limite(rb), caso
    for ident in ot.tags_restritas(sub):
        res = servico.executar(ctx, servico.estado_inicial(ident)).resultado
        out[ident] = dict(d_mm=res.x, Leff_m=res.y, volume_m3=res.derivados["volume"], governante=res.governing,
                          caso=res.driver_case, viavel=res.feasible)
    return out


def _unicos(avaliacoes):
    """Uma Avaliacao por x (o algoritmo pode revisitar um ponto), na ordem em que apareceram."""
    vistos = {}
    for a in avaliacoes:
        vistos.setdefault(a.x, a)
    return list(vistos.values())


def _frente(avaliacoes, ids):
    viaveis = _unicos([a for a in avaliacoes if a.viavel])
    objs = ot.nao_dominados([a.objetivos for a in viaveis], ids)
    return sorted([a for a in viaveis if a.objetivos in objs], key=lambda a: tuple(a.objetivos[i] for i in ids))


def _linha_frente(a, ids_var, ids_obj):
    pct = {"perda_oleo": 100}
    return (f"| {' | '.join(f(v, 1) for v in a.x)} | "
            + " | ".join(f(a.objetivos[i] * pct.get(i, 1), 4 if i in pct else 0) for i in ids_obj)
            + f" | {f(a.restricoes.get('tvp', math.nan), 4)} |")


def gerar_pressao(dados, destino, processos, populacao=None, geracoes=None, semente=None, repetir=False,
                  reusar=False):
    sub = "pressao"
    s = ot.subproblema(sub)
    ids_var = [v["id"] for v in ot.variaveis(sub)]
    ids_obj = [o["id"] for o in ot.objetivos(sub)]
    destino.mkdir(parents=True, exist_ok=True)
    # os resultados brutos ficam guardados (fora do git) antes de formatar: a rodada custa horas
    bruto = destino / ".rodada.pkl"
    guardado = pickle.loads(bruto.read_bytes()) if reusar and bruto.exists() else {}
    # 1. grade-oráculo: avaliada ANTES do algoritmo; dela sai a resolução da conferência
    pontos_grade = ot.grade(sub)
    if "grade" not in guardado:
        guardado["grade"] = _otim.avaliar_pontos(dados, pontos_grade, sub=sub, processos=processos)
        bruto.write_bytes(pickle.dumps(guardado))
    grade = guardado["grade"]
    eps = ot.resolucao(grade, sub)
    frente_grade = _frente(grade, ids_obj)
    # 2. NSGA-II com os parâmetros declarados (não ajustados à frente)
    if "nsga2" not in guardado:
        guardado["nsga2"] = _otim.otimizar(dados, populacao=populacao, geracoes=geracoes, semente=semente, sub=sub,
                                           processos=processos)[1:]
        bruto.write_bytes(pickle.dumps(guardado))
    hist, meta = guardado["nsga2"]
    frente_alg = _frente(hist, ids_obj)
    superados, descobertos = ot.conferir_frente([a.objetivos for a in frente_alg],
                                                [a.objetivos for a in frente_grade], eps)
    # 3. cada ponto da frente reavaliado FORA do otimizador, pelo mesmo avaliador
    if "reavaliacao" not in guardado:
        guardado["reavaliacao"] = _otim.avaliar_pontos(dados, [a.x for a in frente_alg], sub=sub,
                                                       processos=processos)
        guardado["fichas"] = [ficha(dados, a.x, sub) for a in frente_alg]
        bruto.write_bytes(pickle.dumps(guardado))
    reav, fichas = guardado["reavaliacao"], guardado["fichas"]
    reproduz = all(r.objetivos == a.objetivos and r.restricoes == a.restricoes and r.estados == a.estados
                   for r, a in zip(reav, frente_alg))
    mesma_semente = None
    if repetir:
        if "repeticao" not in guardado:
            guardado["repeticao"] = _otim.otimizar(dados, populacao=populacao, geracoes=geracoes, semente=semente,
                                                   sub=sub, processos=processos)[1]
            bruto.write_bytes(pickle.dumps(guardado))
        hist2 = guardado["repeticao"]
        mesma_semente = ([a.x for a in hist2] == [a.x for a in hist]
                         and [a.objetivos for a in _frente(hist2, ids_obj)] == [a.objetivos for a in frente_alg])
    # --- relatório
    n_grade = Counter(a.situacao for a in grade)
    barrando = Counter(t for a in grade if a.situacao == "inviavel" for t, g in a.restricoes.items() if g > 0)
    out = ["# Subproblema de pressão — grade-oráculo, NSGA-II e frente (tabelas geradas)", "",
           f"Gerado por `tools/otimizar.py --sub pressao`. {s['fonte']}.", "",
           "## Declaração", ""]
    out += ["| Variável | Domínio | Natureza dos extremos | Origem |", "|---|---|---|---|"]
    for v in ot.variaveis(sub):
        out.append(f"| {v['rotulo']} | {f(v['min'], 1)} – {f(v['max'], 1)} {v['unidade']} | "
                   f"{v['natureza_min']} / {v['natureza_max']} | {v['fonte']} |")
    out += ["", "| Objetivo | Unidade | Sentido | Definição |", "|---|---|---|---|"]
    out += [f"| {o['rotulo']} (`{o['id']}`) | {o['unidade']} | {o['sentido']} | {o['fonte']} |"
            for o in ot.objetivos(sub)]
    out += ["", "| Restrição | Natureza | Definição |", "|---|---|---|"]
    out += [f"| {r['rotulo']} (`{r['id']}`) | {r['natureza']} | {r['fonte']} |"
            for r in [*ot.restricoes_variavel(sub), *ot.restricoes_balanco(sub)]]
    out += [f"| viabilidade de {t} | contrato | mesmo serviço por TAG; violação = medida de distância "
            "(`_violacao`) |" for t in ot.tags_restritas(sub)]
    out += ["", "## Grade-oráculo", "",
            "Eixos da grade (passos declarados em `grade_passo`): "
            + "; ".join(f"{i} = {f(min(p[k] for p in pontos_grade), 1)} a {f(max(p[k] for p in pontos_grade), 1)} kPa, "
                        f"{len({p[k] for p in pontos_grade})} valores" for k, i in enumerate(ids_var))
            + f". {len(grade)} pontos: " + ", ".join(f"{n} {SITUACAO[k]}" for k, n in sorted(n_grade.items())) + ".", "",
            "Restrições que barram os pontos inviáveis da grade: "
            + (", ".join(f"`{t}` em {n}" for t, n in sorted(barrando.items())) or "nenhuma") + ".", "",
            "Resolução da grade no espaço dos objetivos (maior diferença entre vizinhos viáveis): "
            + ", ".join(f"ε(`{i}`) = {f(e * (100 if i == 'perda_oleo' else 1), 4 if i == 'perda_oleo' else 0)}"
                        + (" p.p." if i == "perda_oleo" else " Sm³/d") for i, e in eps.items()) + ".", "",
            "### Frente da grade", "",
            f"| {' | '.join(ids_var)} | perda de óleo (%) | carga VRU (Sm³/d) | g_TVP |",
            "|---:|---:|---:|---:|---:|"]
    out += [_linha_frente(a, ids_var, ids_obj) for a in frente_grade]
    out += ["", "## NSGA-II", "",
            f"Algoritmo **{meta['algoritmo']}** (pymoo {meta['pymoo']}), população {meta['populacao']}, "
            f"{meta['geracoes']} gerações, semente {meta['semente']} (os valores declarados em "
            f"`[algoritmo]`), {meta['avaliacoes']} avaliações, {len(_unicos(hist))} pontos distintos: "
            + contagem(_unicos(hist)) + ".", "",
            f"| {' | '.join(ids_var)} | perda de óleo (%) | carga VRU (Sm³/d) | g_TVP |",
            "|---:|---:|---:|---:|---:|"]
    out += [_linha_frente(a, ids_var, ids_obj) for a in frente_alg]
    out += ["", "## Conferência contra a grade", "",
            f"- pontos da frente do NSGA-II que a grade supera por mais que ε em todo objetivo: **{len(superados)}**;",
            f"- pontos da frente da grade que a do NSGA-II não cobre dentro de ε: **{len(descobertos)}**;",
            "- veredito: " + ("**a frente do NSGA-II reproduz a da grade na resolução declarada**."
                              if not superados and not descobertos else
                              "**a frente do NSGA-II NÃO reproduz a da grade na resolução declarada**."), "",
            f"Reavaliação de cada ponto da frente fora do otimizador (`ot.avaliar`): "
            + ("**idêntica** (objetivos, restrições e estados bit a bit)." if reproduz else "**DIFERENTE**.")]
    sem = [a for a in _unicos(hist) if a.situacao == "nao_avaliavel"]
    if sem:
        objs_frente = [a.objetivos for a in frente_alg]
        out += ["", f"Pontos **não avaliáveis** do NSGA-II ({len(sem)}): a grandeza de uma restrição não existe "
                "(para a TVP: flash sem equilíbrio num passo da bisseção). Não entram na frente — falta de "
                "dado não é viabilidade. A última coluna diz se a frente os domina mesmo que fossem viáveis.", "",
                f"| {' | '.join(ids_var)} | sem grandeza | perda de óleo (%) | carga VRU (Sm³/d) | dominado pela frente |",
                "|---:|---:|---|---:|---:|---|"]
        out += [f"| {' | '.join(f(v, 1) for v in a.x)} | {', '.join(sorted(a.sem_dado))} | "
                f"{f(100 * a.objetivos['perda_oleo'], 4)} | {f(a.objetivos['carga_vru'], 0)} | "
                f"{'sim' if any(ot.domina(q, a.objetivos, ids_obj) for q in objs_frente) else 'não'} |" for a in sem]
        out.append("")
    if mesma_semente is not None:
        out.append(f"Segunda rodada com a mesma semente: " + ("**mesma sequência de pontos e mesma frente**."
                                                              if mesma_semente else "**DIFERENTE**."))
    out += ["", "## Ficha de cada ponto da frente do NSGA-II", "",
            "Máximos entre os 16 casos (TVP: 12 avaliáveis), com o caso que governa. Potências das bombas: "
            "métrica auxiliar, não objetivo.", "",
            "| P_D1 | P_D2 | recuperação (%) | Q_G V-001 (Sm³/d) | Q_G V-002 (Sm³/d) | VRU máx. (Sm³/d) / caso | "
            "TVP máx. (kPa) / caso | SG-001 vol. (m³) / d / gov. / caso | V-001 | V-002 | "
            "W B-001 / B-002 / B-003 (kW) | estado |",
            "|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|"]

    def vaso(t):
        return f"{f(t['volume_m3'], 1)} / {f(t['d_mm'], 0)} / {t['governante']} / {t['caso'].split(' — ')[0]}"

    for a, fi in zip(frente_alg, fichas):
        out.append(f"| {f(fi['P_D1'], 1)} | {f(fi['P_D2'], 1)} | {f(100 * (1 - a.objetivos['perda_oleo']), 3)} | "
                   f"{f(fi['G_D1'], 0)} | {f(fi['G_D2'], 0)} | {f(a.objetivos['carga_vru'], 0)} / BOT {fi['carga_vru_caso']:02d} | "
                   f"{f(fi['tvp_max'], 2)} / BOT {fi['tvp_caso']:02d} | {vaso(fi['SG-001'])} | {vaso(fi['V-001'])} | "
                   f"{vaso(fi['V-002'])} | {f(fi['W_Bo'])} / {f(fi['W_B1'])} / {f(fi['W_B2'])} | {SITUACAO[a.situacao]} |")
    out.append("")
    (destino / "otimizacao_pressao.md").write_text("\n".join(out), encoding="utf-8")
    pacote = {"meta": meta, "resolucao": eps, "superados": len(superados), "descobertos": len(descobertos),
              "reproduz_fora_do_otimizador": reproduz, "mesma_semente": mesma_semente,
              "frente_grade": [{"x": list(a.x), "objetivos": a.objetivos, "restricoes": a.restricoes}
                               for a in frente_grade],
              "frente_nsga2": [{"x": list(a.x), "objetivos": a.objetivos, "restricoes": a.restricoes, "ficha": fi}
                               for a, fi in zip(frente_alg, fichas)]}
    (destino / "otimizacao_pressao.json").write_text(json.dumps(pacote, indent=2, ensure_ascii=False, sort_keys=True)
                                                     + "\n", encoding="utf-8")
    ids_r = ot.ids_restricoes(sub)
    for nome, avs in (("grade", grade), ("nsga2", hist)):
        with (destino / f"{nome}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow([*ids_var, *ids_obj, *(f"g_{i}" for i in ids_r), "situacao"])
            for a in avs:
                w.writerow([*a.x, *(a.objetivos[i] for i in ids_obj), *(a.restricoes[i] for i in ids_r), a.situacao])
    return destino / "otimizacao_pressao.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--sub", default=None, help="roda só este subproblema (config/pfd/otimizacao.toml)")
    ap.add_argument("--populacao", type=int, default=None)
    ap.add_argument("--geracoes", type=int, default=None)
    ap.add_argument("--semente", type=int, default=None)
    ap.add_argument("--varredura", action="store_true", help="confere a frente contra a grade exaustiva")
    # metade das CPUs lógicas: com SMT ligado isso é o número de núcleos FÍSICOS, e cada processo
    # carrega um modelo de planta inteiro — a memória aperta antes dos núcleos
    ap.add_argument("--processos", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="processos que avaliam a população de cada geração (1 = sequencial)")
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "23-otimizacao.md")
    ap.add_argument("--dados", type=Path, default=None, help="base dos arquivos .json/.csv da frente")
    ap.add_argument("--repetir", action="store_true", help="(pressão) repete o algoritmo com a mesma semente")
    ap.add_argument("--reusar", action="store_true", help="(pressão) reaproveita os resultados brutos guardados")
    a = ap.parse_args()
    if a.sub == "pressao":
        saida = a.saida if a.saida.suffix != ".md" else RAIZ / "docs" / "validacao" / "otimizacao_pressao"
        print(gerar_pressao(carregar_casos(a.casos), saida, a.processos, a.populacao, a.geracoes, a.semente,
                            a.repetir, a.reusar))
        return
    destino = a.dados or (a.saida.parent / "23-otimizacao-frente")
    rodadas = None
    if a.sub is not None:
        s = ot.subproblema(a.sub)
        rodadas = [(a.sub, a.varredura, f"Rodada — {s['rotulo']}", s["fonte"])]
    a.saida.write_text(gerar(carregar_casos(a.casos), a.populacao, a.geracoes, a.semente, destino, rodadas,
                             a.processos), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
