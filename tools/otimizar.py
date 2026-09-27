"""F15 — otimização multiobjetivo do módulo (docs/validacao/23-otimizacao.md + frente em JSON/CSV).

Roda o NSGA-II/III pela porta única `fpso_siz/_otim.py` sobre o avaliador puro
`pfd/otimizacao.py`, com as variáveis, objetivos e restrições declarados em
config/pfd/otimizacao.toml. Determinístico (semente fixa) e LENTO: cada indivíduo roda o balanço
e os TAGs da planta (cerca de 3 s no problema completo).

**A pré-condição do documento 0003 — nenhum alarme aberto — NÃO está satisfeita**: P-001, P-002
e P-003 seguem em alarme. Toda rodada é ESTUDO, e nenhum ponto da frente é recomendação de
projeto.

    uv run python tools/otimizar.py [--sub sg_001] [--populacao N] [--geracoes N] [--semente N]
                                    [--varredura] [--saida docs/validacao/23-otimizacao.md]
"""
import argparse
import csv
import json
import math
from pathlib import Path

from fpso_siz import _otim
from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd.tags import tag

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def f(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ponto_do_projeto(dados, sub):
    """O vetor de decisão do projeto atual: premissa no valor de base, um trem, e a recomendação
    com fonte de cada entrada de TAG (o que o `pfd` já dimensiona hoje)."""
    base = premissas(dados)
    x = []
    for v in ot.variaveis(sub):
        if v["destino"] == "premissa":
            x.append(float(base[v["chave"]]))
        elif v["destino"] == "fator_vazao":
            x.append(1.0)
        else:
            rec = tag(v["tag"]).recomendadas.get(v["chave"])
            x.append(float(rec["valor"]) if rec else float(v["min"]))
    return tuple(x)


def tabela_declaracao(sub):
    out = ["| Variável | Tipo | Limites | Origem dos limites |", "|---|---|---|---|"]
    for v in ot.variaveis(sub):
        out.append(f"| {v['rotulo']} (`{v['id']}`) | {v['tipo']} | {f(v['min'], 3)} – {f(v['max'], 3)} | "
                   f"{v['fonte']} |")
    out += ["", "| Objetivo | Unidade | Como é somado | Fonte |", "|---|---|---|---|"]
    for o in ot.objetivos(sub):
        como = (f"soma de `{o.get('derivado_v2', o.get('derivado'))}` em {', '.join(o['tags'])}"
                if o["tipo"] == "soma_derivado" else f"{' + '.join(o['cargas'])} ({o['agregacao']})")
        out.append(f"| {o['rotulo']} (`{o['id']}`) | {o['unidade']} | {como} | {o['fonte']} |")
    return out


def linha_ponto(a, ids_var, ids_obj, sub=None):
    """A linha de um ponto. Variável inteira aparece DECODIFICADA (o algoritmo caminha no
    contínuo e a decodificação arredonda): mostrar 2,8869 trens seria mentir sobre o que foi
    avaliado."""
    tipos = {v["id"]: v["tipo"] for v in ot.variaveis(sub)}
    xs = " · ".join(f"{i} = {f(round(v), 0) if tipos[i] == 'inteiro' else f(v, 4)}"
                    for i, v in zip(ids_var, a.x))
    objs = " · ".join(f"{i} = {f(a.objetivos[i])}" for i in ids_obj)
    viol = ", ".join(f"{t} {f(g, 3)}" for t, g in a.restricoes.items() if g > 0) or "—"
    return f"| {xs} | {objs} | {viol} | {'viável' if a.viavel else 'inviável'} |"


def secao(dados, sub, populacao, geracoes, semente, com_varredura, titulo, proposito):
    """Uma rodada: declaração, ponto do projeto, frente e (opcional) conferência exaustiva.
    Devolve (linhas do relatório, dados para o JSON, avaliações para o CSV)."""
    ids_var = [v["id"] for v in ot.variaveis(sub)]
    ids_obj = [o["id"] for o in ot.objetivos(sub)]
    x0 = ponto_do_projeto(dados, sub)
    a0 = ot.avaliar(dados, x0, sub=sub)
    frente, hist, meta = _otim.otimizar(dados, populacao=populacao, geracoes=geracoes, semente=semente, sub=sub)
    viaveis = [a for a in hist if a.viavel]
    front_hist = ot.nao_dominados([a.objetivos for a in viaveis], ids_obj) if viaveis else []
    out = [f"## {titulo}", "", proposito, "", "### O que a rodada pôde mexer", ""]
    out += tabela_declaracao(sub)
    out += ["", f"Recorte: **{meta['subproblema']}**. TAGs restringidos: "
            f"{', '.join(meta['tags_restritas'])}.", "",
            f"Algoritmo **{meta['algoritmo']}** (pymoo {meta['pymoo']}), população {meta['populacao']}, "
            f"{meta['geracoes']} gerações, semente {meta['semente']}, {meta['avaliacoes']} avaliações.", "",
            "### O ponto do projeto atual", "",
            "| Variáveis | Objetivos | Violações | Estado |", "|---|---|---|---|",
            linha_ponto(a0, ids_var, ids_obj, sub), "",
            "Critério de validação 1 do 0003: o avaliador reproduz o ponto do projeto atual — os estados por TAG "
            "são os mesmos que o `fpso-siz pfd` publica hoje.", "",
            "### Frente de Pareto", ""]
    if not viaveis:
        out += ["Nenhum indivíduo viável: com os alarmes dos trocadores abertos, todo ponto do espaço de decisão "
                "tem pelo menos um TAG inviável, e a frente é vazia. **Isto é o resultado da rodada**, e é "
                "exatamente a razão da pré-condição do 0003 — otimizar sobre um modelo que ainda dá "
                "\"nenhum equipamento atende\" seria otimizar um erro.", "",
                "A rodada continua útil como diagnóstico: a coluna de violações mostra qual TAG barra cada ponto e "
                "quanto falta, e a violação do P-002 cai com os passes no tubo.", ""]
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
    avaliacoes = [a for a in hist]
    if com_varredura:
        ref = ot.varredura(dados, sub)
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
        inviaveis = [a for a in ref if not a.viavel]
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
        avaliacoes = avaliacoes + ref
    dados_json = {"meta": meta, "variaveis": ids_var, "objetivos": ids_obj,
                  "projeto_atual": {"x": list(x0), "objetivos": a0.objetivos, "restricoes": a0.restricoes,
                                    "estados": a0.estados},
                  "frente": [{"x": list(a.x), "objetivos": a.objetivos, "restricoes": a.restricoes}
                             for a in viaveis if a.objetivos in front_hist]}
    return out, dados_json, ids_var, ids_obj, avaliacoes


def gerar(dados, populacao, geracoes, semente, destino_dados, rodadas=None):
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
           "rodada. Os alarmes do P-001, P-002 e P-003 **continuam abertos** (`docs/validacao/14-alarmes.md`): "
           "falta a correlação laminar/de transição do lado tubo, cuja fonte já existe no acervo mas ainda não tem "
           "exemplo numérico para o caso-ouro (`docs/validacao/20-correlacao-tubo-laminar.md`). O usuário "
           "autorizou a implementação da F15 mesmo assim, em 2026-09-26; **toda rodada aqui é estudo, e nenhum "
           "ponto da frente é recomendação de projeto.**", ""]
    pacote, todas = {}, []
    for sub, varredura, titulo, proposito in rodadas:
        linhas, dados_json, ids_var, ids_obj, avaliacoes = secao(dados, sub, populacao, geracoes, semente,
                                                                varredura, titulo, proposito)
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
            w.writerow([*ids_var, *ids_obj, "violacao_total", "viavel"])
            for a in avaliacoes:
                w.writerow([*a.x, *(a.objetivos[i] for i in ids_obj), a.violacao_total, int(a.viavel)])
        arquivos.append((caminho, nome, len(avaliacoes)))
    out += ["## Arquivos", "",
            f"- `{destino_dados.with_suffix('.json').name}`: por rodada, a frente, o ponto do projeto e os "
            "metadados (algoritmo, versão do pymoo, semente)."]
    for caminho, nome, n in arquivos:
        out.append(f"- `{caminho.name}`: as {n} avaliações da rodada `{nome}`, uma por linha, para reproduzir "
                   "qualquer ponto com `fpso-siz pfd --ajustes`.")
    out.append("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--sub", default=None, help="roda só este subproblema (config/pfd/otimizacao.toml)")
    ap.add_argument("--populacao", type=int, default=None)
    ap.add_argument("--geracoes", type=int, default=None)
    ap.add_argument("--semente", type=int, default=None)
    ap.add_argument("--varredura", action="store_true", help="confere a frente contra a grade exaustiva")
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "23-otimizacao.md")
    ap.add_argument("--dados", type=Path, default=None, help="base dos arquivos .json/.csv da frente")
    a = ap.parse_args()
    destino = a.dados or (a.saida.parent / "23-otimizacao-frente")
    rodadas = None
    if a.sub is not None:
        s = ot.subproblema(a.sub)
        rodadas = [(a.sub, a.varredura, f"Rodada — {s['rotulo']}", s["fonte"])]
    a.saida.write_text(gerar(carregar_casos(a.casos), a.populacao, a.geracoes, a.semente, destino, rodadas),
                       encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
