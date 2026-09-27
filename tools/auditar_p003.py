"""Auditoria algorítmica do P-003 — de onde vêm as ~913 mil avaliações de Bell-Delaware.

A baseline (`docs/validacao/performance-baseline.md`) mostrou que o P-003 é 95 % do tempo de
`avaliar()`. Esta ferramenta responde uma pergunta diferente: **o custo é necessário?** Ela
instrumenta o caminho real e decompõe as chamadas por origem, de modo que o número medido seja
explicado pela árvore do algoritmo — e não aceito porque "trocador é complicado".

Não altera equação, correlação, critério nem estratégia: só conta.

    uv run python tools/auditar_p003.py [--tags P-003,P-002] [--dados auditoria.json]
"""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"

# A fase corrente do motor, para atribuir cada chamada de `_tubo` a quem a pediu.
FASE = {"nome": "?"}


class Auditor:
    """Conta `_tubo` por fase e por par (caso, n), e `bell_delaware` por chamada de `_tubo`."""

    def __init__(self):
        self.tubo_por_fase = Counter()
        self.tubo_por_par = Counter()
        self.pares_por_fase = defaultdict(set)
        self.iteracoes = Counter()          # histograma de iterações do ponto fixo
        self.bd_chamadas = 0
        self.bd_por_fase = Counter()
        self.feixe_chamadas = 0
        self.feixe_por_fase = Counter()
        self.js_variavel = Counter()        # n_b visto em cada iteração, por chamada de _tubo
        self.geo_por_tubo = 0
        self.casos = {}                     # marca estável por objeto de caso
        self._vivos = []
        self._restaurar = []

    def marca(self, c):
        m = self.casos.get(id(c))
        if m is None:
            m = len(self.casos)
            self.casos[id(c)] = m
            self._vivos.append(c)           # segura a referência: id() reciclado colidiria
        return m

    # ---------------------------------------------------------------- instrumentação
    def ligar(self, metodo):
        from fpso_siz.sizing import bell_delaware as bd
        from fpso_siz.sizing import trocador

        cls = type(metodo)
        for nome in ("requirement", "derived", "case_admissible", "admissible", "objective",
                     "operacao_por_caso", "bloqueios", "envelope_derived", "parcelas_u",
                     "selection_message", "envelope_case_params", "sizing_constraints",
                     "envelope_params", "governing_of", "perfil_tq", "trace_selection",
                     "result_fields", "grid_hint"):
            original = getattr(cls, nome, None)
            if original is None:
                continue
            self._envolver_fase(cls, nome, original)

        tubo = trocador._tubo

        def espiao_tubo(c, n):
            fase = FASE["nome"]
            self.tubo_por_fase[fase] += 1
            par = (self.marca(c), n)
            self.tubo_por_par[par] += 1
            self.pares_por_fase[fase].add(par)
            antes = self.bd_chamadas
            try:
                return tubo(c, n)
            finally:
                self.iteracoes[self.bd_chamadas - antes] += 1
        trocador._tubo = espiao_tubo
        self._restaurar.append(lambda: setattr(trocador, "_tubo", tubo))

        # Depois do R1 há DOIS passos: `feixe_ideal` (a parte cara, invariante no ponto fixo) e
        # `com_chicanas` (a combinação com Js, barata, uma por passagem). Contam-se os dois: é a
        # razão entre eles que mostra o efeito do R1.
        original_feixe = bd.feixe_ideal

        def espiao_feixe(g, w_s, cp_s, mu_s, k_s, k):
            self.feixe_chamadas += 1
            self.feixe_por_fase[FASE["nome"]] += 1
            return original_feixe(g, w_s, cp_s, mu_s, k_s, k)

        original_comb = bd.com_chicanas

        def espiao_comb(feixe, n_b, l_bi, l_bo, l_bc, k):
            self.bd_chamadas += 1
            self.bd_por_fase[FASE["nome"]] += 1
            return original_comb(feixe, n_b, l_bi, l_bo, l_bc, k)

        for modulo, nome, espiao, orig in ((bd, "feixe_ideal", espiao_feixe, original_feixe),
                                           (bd, "com_chicanas", espiao_comb, original_comb),
                                           # `trocador` importou os nomes: trocar só na origem não bastaria
                                           (trocador, "feixe_ideal", espiao_feixe, trocador.feixe_ideal),
                                           (trocador, "com_chicanas", espiao_comb, trocador.com_chicanas)):
            setattr(modulo, nome, espiao)
            self._restaurar.append(lambda m=modulo, n=nome, o=orig: setattr(m, n, o))

    def _envolver_fase(self, cls, nome, original):
        def espiao(*a, **k):
            anterior, FASE["nome"] = FASE["nome"], nome
            try:
                return original(*a, **k)
            finally:
                FASE["nome"] = anterior
        setattr(cls, nome, espiao)
        self._restaurar.append(lambda: setattr(cls, nome, original))

    def desligar(self):
        for f in reversed(self._restaurar):
            f()
        self._restaurar.clear()

    # ---------------------------------------------------------------- resultado
    def resumo(self):
        total_tubo = sum(self.tubo_por_fase.values())
        distintos = len(self.tubo_por_par)
        return {
            "tubo_chamadas": total_tubo,
            "tubo_pares_distintos": distintos,
            "tubo_fator_recomputacao": total_tubo / distintos if distintos else None,
            "tubo_por_fase": dict(self.tubo_por_fase.most_common()),
            "pares_distintos_por_fase": {f: len(s) for f, s in sorted(self.pares_por_fase.items())},
            "bell_delaware_chamadas": self.bd_chamadas,
            "bell_delaware_por_fase": dict(self.bd_por_fase.most_common()),
            "feixe_ideal_chamadas": self.feixe_chamadas,
            "feixe_ideal_por_fase": dict(self.feixe_por_fase.most_common()),
            "combinacoes_por_feixe": (self.bd_chamadas / self.feixe_chamadas) if self.feixe_chamadas else None,
            "iteracoes_por_tubo": {str(k): v for k, v in sorted(self.iteracoes.items())},
            "iteracoes_media": (self.bd_chamadas / total_tubo) if total_tubo else None,
            "casos_distintos": len(self.casos),
        }


def espaco_de_busca(rt):
    """A grade e os casos como o motor os vê — o espaço de projeto declarado, sem instrumentar."""
    from fpso_siz.core.casos import CaseSet  # noqa: F401  (documenta de onde vem `case_set`)
    from fpso_siz.core.parametros import with_defaults

    entradas = rt.entradas
    m = entradas.metodo
    cases = entradas.case_set()
    expandidos = cases.expand()
    specs = m.parameters()
    k = m.constants()
    params, conss = [], []
    for _nome, vals in expandidos:
        p = with_defaults(specs, vals)
        params.append(p)
        ok, cons, _ = m.sizing_constraints(m.case_input(vals), p, k)
        conss.append(cons if ok else None)
    ok_p, p_env = m.envelope_params(params)
    eixo = m.sweep_axis(p_env) if ok_p else None
    laco = k.get("laco_comprimento", {})
    return {
        "casos_expandidos": len(expandidos),
        "casos_com_restricao_valida": sum(1 for c in conss if c is not None),
        "grade_ok": ok_p,
        "n_min": p_env.get("n_min") if ok_p else None,
        "n_max": p_env.get("n_max") if ok_p else None,
        "n_step": p_env.get("n_step") if ok_p else None,
        "pontos_da_grade": len(eixo.values) if eixo else 0,
        "v_min": p_env.get("v_min") if ok_p else None,
        "v_max": p_env.get("v_max") if ok_p else None,
        "passes": params[0].get("passes_tubo") if params else None,
        "cascos_serie": params[0].get("cascos_serie") if params else None,
        "cascos_paralelo": params[0].get("cascos_paralelo") if params else None,
        "max_iter_ponto_fixo": laco.get("max_iter"),
        "tolerancia_ponto_fixo": laco.get("tolerancia"),
    }


def rejeicoes(rt, metodo, conss, pcs, p_env, eixo, teto):
    """Por ponto da grade: quantos casos foram testados em `case_admissible` antes do primeiro
    reprovado (o `all()` do motor faz curto-circuito), e qual critério reprovou. Diz onde um
    candidato inviável é descartado — e se poderia ter sido antes da chamada de Bell-Delaware."""
    from fpso_siz.sizing import trocador
    n_casos = len(conss)
    linhas = []
    for x in eixo.values:
        testados, reprovou_em, criterio = 0, None, None
        acima_do_teto = x > teto
        for i, (c, pc) in enumerate(zip(conss, pcs)):
            testados += 1
            t = trocador._tubo(c, x)
            if not t["ok"]:
                reprovou_em, criterio = i, "calculo"
                break
            if not t["nu_valido"]:
                reprovou_em, criterio = i, "correlacao_tubo"
                break
            if not (pc["v_min"] <= t["v"] <= pc["v_max"]):
                reprovou_em, criterio = i, "velocidade"
                break
        linhas.append({"x": x, "acima_do_teto": acima_do_teto, "casos_testados": testados,
                       "reprovou_no_caso": reprovou_em, "criterio": criterio,
                       "casos_poupados": n_casos - testados})
    return linhas


def invariantes_no_ponto_fixo(rt):
    """O que muda de uma iteração do ponto fixo para a seguinte, DENTRO de `bell_delaware`.

    Mede sem alterar nada: repete a chamada com o mesmo `g` e vazões, variando só `n_b`, e
    compara os fatores. O que não muda é trabalho refeito a cada iteração."""
    from fpso_siz.sizing import bell_delaware as bd
    from fpso_siz.sizing import trocador

    entradas = rt.entradas
    m = entradas.metodo
    cases = entradas.case_set()
    specs, k = m.parameters(), m.constants()
    from fpso_siz.core.parametros import with_defaults
    vals = cases.expand()[0][1]
    p = with_defaults(specs, vals)
    ok, c, _ = m.sizing_constraints(m.case_input(vals), p, k)
    if not ok:
        return {"aviso": "o primeiro caso não produz restrição válida"}

    # reconstrói a geometria como `_tubo_bell_delaware` faz, para um n típico da grade
    n = int((p["n_min"] + p["n_max"]) / 2)
    n_total = n * c.passes
    d_feixe = math.sqrt(4 * n_total * c.area_celula * (c.passo_m * c.passo_m) / math.pi)
    d_s = d_feixe + 2 * c.d_o
    folga = bd.baffle_clearance(d_s * 1000.0, c.kbd)
    p_n, p_p, _ = bd.layout_pitches(c.layout, c.passo_m, c.kbd)
    l_bc = c.espac_chicana * d_s
    g = bd.ShellGeometry(d_s, d_feixe, c.d_o, c.passo_m, p_n, p_p, c.corte_chicana * d_s, l_bc,
                         folga / 1000.0, c.folga_furo_m, float(n_total), c.pares_veda,
                         c.faixas_divisoras, 2 * c.d_o, c.layout)
    saidas = []
    for n_b in (1.0, 5.0, 20.0, 60.0):
        _h, f, _ok = bd.bell_delaware(g, c.m_casco, c.cp_casco, c.mu_casco, c.k_casco, n_b, l_bc, l_bc, c.kbd)
        saidas.append({"n_b": n_b, "re": f.re, "a_s": f.a_s, "h_ideal": f.h_ideal,
                       "jc": f.jc, "jl": f.jl, "jb": f.jb, "js": f.js, "jr": f.jr})
    fixos = [campo for campo in ("re", "a_s", "h_ideal", "jc", "jl", "jb", "jr")
             if len({repr(s[campo]) for s in saidas}) == 1]
    variaveis = [campo for campo in ("re", "a_s", "h_ideal", "jc", "jl", "jb", "js", "jr")
                 if len({repr(s[campo]) for s in saidas}) > 1]
    return {"n_usado": n, "amostras": saidas, "invariantes_em_n_b": fixos, "variam_com_n_b": variaveis}


def limites_fechados(m, conss, params, p_env, eixo):
    """Os limites que uma RELAÇÃO FECHADA já dá, sem enumerar nada.

    A velocidade no tubo é v = ṁ/(ρ·n·A_i): dado o par (v_min, v_max) de cada caso, o intervalo
    de n admissível é analítico, e o do envelope é a interseção. O diâmetro do casco cresce com
    √n, então o teto `d_casco_max` também dá um n máximo fechado. Conta quantos pontos da grade
    enumerada esses dois limites já excluiriam."""
    lo, hi = -math.inf, math.inf
    pcs = m.envelope_case_params(conss, p_env)
    for c, pc in zip(conss, pcs):
        base = c.m_tubo / (c.rho_tubo * c.area_tubo)
        lo = max(lo, base / pc["v_max"] if pc["v_max"] > 0 else 0.0)
        hi = min(hi, base / pc["v_min"] if pc["v_min"] > 0 else math.inf)
    c0 = conss[0]
    d_max = p_env["d_casco_max"] / 1000.0
    n_geom = math.pi * ((d_max - 2 * c0.d_o) ** 2) / (4 * c0.area_celula * c0.passo_m ** 2) / c0.passes
    xs = eixo.values
    return {"intersecao_velocidade": [lo, hi], "teto_geometrico_n": n_geom,
            "pontos_da_grade": len(xs),
            "dentro_da_intersecao": sum(1 for x in xs if lo <= x <= hi),
            "abaixo_do_teto_geometrico": sum(1 for x in xs if x <= n_geom),
            "sobrevivem_aos_dois": sum(1 for x in xs if lo <= x <= hi and x <= n_geom)}


def alinhamento_das_grades(m, params, p_env):
    """As varreduras por caso usam cada uma o seu n_min; a conjunta usa o menor de todos. Mede
    quanto as grades coincidem — é o que diria se os dois ramos poderiam compartilhar cálculo."""
    conj = set(m.sweep_axis(p_env).values)
    total = coincidentes = 0
    for p in params:
        xs = m.sweep_axis(p).values
        total += len(xs)
        coincidentes += sum(1 for x in xs if x in conj)
    return {"pontos_das_varreduras_por_caso": total, "coincidentes_com_a_conjunta": coincidentes,
            "fracao_coincidente": (coincidentes / total) if total else None,
            "pontos_da_grade_conjunta": len(conj)}


def posicao_do_otimo(r):
    """Onde está a resposta dentro da varredura, e o objetivo é monótono no eixo?

    Se o objetivo cresce com n nos admissíveis, o ótimo é o PRIMEIRO admissível, e tudo o que
    for avaliado depois dele não muda a resposta."""
    if not r.feasible or not r.rows:
        return {"viavel": False}
    adm = [w for w in r.rows if w.ok]
    areas = [w.derivados.get("area", math.nan) for w in adm]
    return {"viavel": True, "x_escolhido": r.x, "pontos": len(r.rows), "admissiveis": len(adm),
            "primeiro_admissivel": adm[0].x if adm else None,
            "indice_do_escolhido": [w.x for w in adm].index(r.x) if adm else None,
            "objetivo_monotono_crescente": all(b >= a for a, b in zip(areas, areas[1:])),
            "pontos_antes_do_primeiro_admissivel": sum(1 for w in r.rows if w.x < adm[0].x) if adm else 0,
            "pontos_depois_do_escolhido": sum(1 for w in r.rows if w.x > r.x)}


def arvore(r, n_casos, rejeicao, posicao, iteracoes_media):
    """A árvore quantitativa: de onde vem cada chamada de `_tubo`, e daí as de Bell-Delaware.

    Ramo A é o dimensionamento de cada caso ISOLADO (`per_case`, um produto do resultado);
    ramo B é o envelope conjunto. Dentro de B, separa-se o que é gasto antes do primeiro ponto
    admissível, no ponto escolhido, e depois dele."""
    if not posicao.get("viavel"):
        return {}
    antes = posicao["pontos_antes_do_primeiro_admissivel"]
    depois = posicao["pontos_depois_do_escolhido"]
    ca_total = rejeicao["case_admissible_testados"]
    # nos pontos reprovados o curto-circuito para no primeiro caso que reprova
    ca_reprovados = sum(int(k) + 1 for k, v in rejeicao["primeiro_caso_que_reprova"].items()
                        for _ in range(v) if k != "None")
    ca_aprovados = ca_total - ca_reprovados
    b_antes = antes * n_casos + antes + ca_reprovados
    b_escolhido = n_casos + 1 + n_casos
    b_depois = depois * n_casos + depois + (ca_aprovados - n_casos)
    return {"ramo_B_antes_do_primeiro_admissivel": b_antes,
            "ramo_B_ponto_escolhido": b_escolhido,
            "ramo_B_depois_do_escolhido": b_depois,
            "case_admissible_em_pontos_reprovados": ca_reprovados,
            "case_admissible_em_pontos_aprovados": ca_aprovados,
            "iteracoes_media_ponto_fixo": iteracoes_media}


def identidade_bell_delaware(ctx, ident):
    """Prova empírica: dentro de UMA chamada de `_tubo`, as saídas sucessivas de
    `bell_delaware` são iguais?

    O ponto fixo itera em L. `bell_delaware` só vê L através de `n_b`, e `n_b` só entra em `Js`
    (Eq. 2-28). Como `_tubo_bell_delaware` passa `l_bi = l_bo = l_bc`, a Eq. 2-28 dá
    Js = (n_b − 1 + 1 + 1)/(n_b − 1 + 1 + 1) = 1 para qualquer n_b — logo a saída inteira não
    depende do iterando. Isto CONFERE a álgebra contra o código, chamada a chamada, em vez de
    confiar nela."""
    from fpso_siz.pfd import equipamento as servico
    from fpso_siz.sizing import trocador

    estado = servico.estado_inicial(ident)
    entradas = servico.preparar(ctx, estado)
    orig_tubo, orig_bd = trocador._tubo, trocador.com_chicanas
    orig_feixe = trocador.feixe_ideal
    saidas, cont = [], Counter()

    def espiao_feixe(g, w_s, cp_s, mu_s, k_s, k):
        cont["feixe_ideal"] += 1
        return orig_feixe(g, w_s, cp_s, mu_s, k_s, k)

    def espiao_bd(feixe, n_b, l_bi, l_bo, l_bc, k):
        h, f, ok = orig_bd(feixe, n_b, l_bi, l_bo, l_bc, k)
        saidas.append((h, f.jc, f.jl, f.jb, f.js, f.jr, f.re, f.a_s, f.h_ideal, ok))
        cont["bd"] += 1
        if not (l_bi == l_bo == l_bc):
            cont["espacamento_de_ponta_desigual"] += 1
        if f.js == 1.0:
            cont["js_exatamente_1"] += 1
        return h, f, ok

    def espiao_tubo(c, n):
        del saidas[:]
        r = orig_tubo(c, n)
        cont["tubo"] += 1
        if len(saidas) > 1:
            cont["tubo_com_mais_de_uma_bd"] += 1
            cont["todas_identicas" if all(x == saidas[0] for x in saidas[1:]) else "alguma_diferente"] += 1
            cont["bd_redundantes"] += len(saidas) - 1
        return r

    trocador.com_chicanas, trocador.feixe_ideal, trocador._tubo = espiao_bd, espiao_feixe, espiao_tubo
    try:
        servico.dimensionar(entradas, estado)
    finally:
        trocador.com_chicanas, trocador.feixe_ideal, trocador._tubo = orig_bd, orig_feixe, orig_tubo
    return {**cont, "fracao_bd_redundante": (cont["bd_redundantes"] / cont["bd"]) if cont["bd"] else None}


# ----------------------------------------------------------------------------- auditoria


def auditar(dados, ident):
    from fpso_siz.core.parametros import with_defaults
    from fpso_siz.pfd import equipamento as servico
    from fpso_siz.pfd import propostas as mp
    from fpso_siz.sizing import trocador

    ctx = servico.Contexto(dados, propostas=mp.padrao())
    ctx.balanco
    estado = servico.estado_inicial(ident)
    entradas = servico.preparar(ctx, estado)
    rt0 = servico.dimensionar(entradas, estado)

    out = {"tag": ident, "status": rt0.status, "espaco": espaco_de_busca(rt0)}

    aud = Auditor()
    aud.ligar(entradas.metodo)
    try:
        servico.dimensionar(servico.preparar(ctx, estado), estado)
    finally:
        aud.desligar()
    out["contagem"] = aud.resumo()

    # rejeições e invariantes usam o caminho não instrumentado
    m = entradas.metodo
    cases = entradas.case_set()
    specs, k = m.parameters(), m.constants()
    params, conss = [], []
    for _nome, vals in cases.expand():
        p = with_defaults(specs, vals)
        ok, c, _ = m.sizing_constraints(m.case_input(vals), p, k)
        if ok:
            params.append(p)
            conss.append(c)
    if conss:
        ok_p, p_env = m.envelope_params(params)
        if ok_p:
            eixo = m.sweep_axis(p_env)
            pcs = m.envelope_case_params(conss, p_env)
            from fpso_siz.core.motor import _menor_teto
            teto = _menor_teto(m, conss)[0]
            out["limites_fechados"] = limites_fechados(m, conss, params, p_env, eixo)
            out["alinhamento_das_grades"] = alinhamento_das_grades(m, params, p_env)
            out["posicao_do_otimo"] = posicao_do_otimo(rt0.resultado) if rt0.resultado else {}
            linhas = rejeicoes(rt0, m, conss, pcs, p_env, eixo, teto)
            testados = sum(x["casos_testados"] for x in linhas)
            poupados = sum(x["casos_poupados"] for x in linhas)
            out["rejeicao"] = {
                "pontos": len(linhas),
                "casos_por_ponto_no_pior_caso": len(conss),
                "case_admissible_testados": testados,
                "case_admissible_poupados_pelo_curto_circuito": poupados,
                "criterios": dict(Counter(x["criterio"] for x in linhas if x["criterio"])),
                "primeiro_caso_que_reprova": dict(Counter(str(x["reprovou_no_caso"]) for x in linhas)),
                "pontos_aprovados": sum(1 for x in linhas if x["criterio"] is None),
            }
            out["arvore"] = arvore(rt0.resultado, len(conss), out["rejeicao"],
                                   out["posicao_do_otimo"], out["contagem"]["iteracoes_media"])
    out["ponto_fixo"] = invariantes_no_ponto_fixo(rt0)
    out["identidade_bell_delaware"] = identidade_bell_delaware(ctx, ident)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--tags", default="P-003,P-002,P-001")
    ap.add_argument("--dados", type=Path, required=True)
    a = ap.parse_args()

    from fpso_siz.balanco.dados import carregar_casos
    dados = carregar_casos(a.casos)
    out = {t: auditar(dados, t) for t in [x.strip() for x in a.tags.split(",") if x.strip()]}
    a.dados.write_text(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
                       encoding="utf-8")
    print(a.dados)


if __name__ == "__main__":
    main()
