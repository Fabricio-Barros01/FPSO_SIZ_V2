"""Motor de dimensionamento: caso único e envelope multi-caso
(port de src/engine/single.jl e src/engine/envelope.jl).

O envelope entrega UM equipamento que atende a todos os casos, envelopando a curva de
exigência e não os dados de entrada (correto sem hipótese de monotonicidade):

    y_env(x) = max_c requirement(m, x, cons_c)        x_adm ≤ min_c ceiling_of(m, cons_c)

O corpo não cita nenhuma grandeza — só os hooks de contrato.py (invariante 4). As
mensagens reproduzem o texto do Julia, inclusive o formato dos números.
"""
import math

from fpso_siz.core.contrato import (EnvelopeResult, EnvelopeRow, SizingResult, SweepRow, infeasible,
                                    infeasible_envelope)
from fpso_siz.core.formato_julia import jl_round
from fpso_siz.core.parametros import with_defaults


def _erro(e):
    """`sprint(showerror, ArgumentError(msg))` do Julia."""
    return f"ArgumentError: {e}"


def _numerico(e):
    """Erro aritmético que a física não previu (divisão por zero, estouro). No Julia ele
    viraria Inf/NaN; aqui vira inviabilidade explícita — nunca exceção (contrato do projeto)."""
    return f"Erro numérico no cálculo ({type(e).__name__}: {e}). Confira as entradas deste caso."


def sweep_row(m, x, cons, k, p):
    y = m.requirement(x, cons)
    gov = m.governing_of(x, cons)
    d = m.derived(x, y, gov, cons, k, p)
    ok = x <= m.ceiling_of(cons) and m.case_admissible(x, cons, p) and m.admissible(x, d, p)
    return SweepRow(x, y, m.per_constraint(x, cons), d, gov, ok, m.presentation_data(x, cons, k, p))


def size_single(eq, m, entrada, params):
    """Varre a grade, descarta o que passa do teto ou sai da banda, e minimiza objective."""
    p = with_defaults(m.parameters(), params)
    k = m.constants()
    try:
        return _size_single(m, entrada, p, k)
    except ArithmeticError as e:
        return infeasible(m.method_id, _numerico(e))


def _size_single(m, entrada, p, k):
    ok, cons, tr = m.sizing_constraints(entrada, p, k)
    if not ok:
        return infeasible(m.method_id, cons, trace=tr)
    eixo = m.sweep_axis(p)
    teto = m.ceiling_of(cons)
    mecan = m.ceiling_mechanism_of(cons)
    if not eixo.values:
        return infeasible(m.method_id, (f"Grade de {eixo.label} vazia. " + m.grid_hint(p)).strip(),
                          trace=tr, ceiling=teto, ceiling_mechanism=mecan)
    sweep = [sweep_row(m, x, cons, k, p) for x in eixo.values]
    admissivel = [r for r in sweep if r.ok]
    if not admissivel:
        return infeasible(m.method_id, m.selection_message(sweep, teto, p, mechanism=mecan),
                          sweep=sweep, trace=tr, ceiling=teto, ceiling_mechanism=mecan)
    best = min(admissivel, key=lambda r: m.objective(r.x, r.derivados, p))
    m.trace_selection(tr, best, p)
    return SizingResult(True, "", best.x, best.y, best.derivados, best.governing, teto, mecan,
                        m.method_id, sweep, tr)


def _menor_teto(m, conss):
    if not conss:
        return math.inf, -1
    tetos = [m.ceiling_of(c) for c in conss]
    i = min(range(len(tetos)), key=tetos.__getitem__)
    return tetos[i], i


def _faixa_texto(s):
    return jl_round(s[0], 2) if len(s) == 1 else f"{jl_round(min(s), 2)}–{jl_round(max(s), 2)}"


def _sem_intersecao(m, eixo, conss, names, pcs):
    """Cada caso, sozinho, tem solução, e as soluções não se cruzam — só o motor sabe."""
    if len(conss) < 2:
        return ""
    aceitos = [[x for x in eixo.values if x <= m.ceiling_of(c) and m.case_admissible(x, c, pc)]
               for c, pc in zip(conss, pcs)]
    if any(not a for a in aceitos):
        return ""
    if set(aceitos[0]).intersection(*aceitos[1:]):
        return ""
    faixas = [f"'{n}' aceita {_faixa_texto(s)} {eixo.unit}" for n, s in zip(names, aceitos)]
    return (f" Isolado, cada caso tem {eixo.label} admissível, mas as faixas não se cruzam: " + "; ".join(faixas)
            + ". Como o equipamento é um só, amplie a banda, ou trate os casos em equipamentos separados.")


def size_envelope(eq, m, cases, max_corners=None):
    """Um equipamento para todos os casos ativos de `cases` (faixas viram cantos)."""
    try:
        return _size_envelope(eq, m, cases, max_corners)
    except ArithmeticError as e:
        return infeasible_envelope(_numerico(e))


def _preparar_todos(m, expanded, specs, k):
    """[(nome, entrada, restrições ou None, parâmetros)] de TODOS os casos — o diagnóstico de um
    envelope que parou na preparação de um caso ainda mostra os que preparam."""
    out = []
    for name, vals in expanded:
        p = with_defaults(specs, vals)
        try:
            entrada = m.case_input(vals)
            ok, cons, _ = m.sizing_constraints(entrada, p, k)
        except (ValueError, ArithmeticError):
            out.append((name, None, None, p))
            continue
        out.append((name, entrada, cons if ok else None, p))
    return tuple(out)


def _size_envelope(eq, m, cases, max_corners):
    if m.applies_to().method_id != eq.method_id:
        return infeasible_envelope(f"O método '{m.label}' não se aplica a '{eq.label}'.")
    specs = m.parameters()
    k = m.constants()
    try:
        expanded = cases.expand(max_corners=max_corners)
    except ValueError as e:
        return infeasible_envelope(_erro(e))
    if not expanded:
        return infeasible_envelope("Nenhum caso ativo. Adicione ao menos uma corrente.")

    names, conss, per_case, params, preparo = [], [], [], [], []
    for name, vals in expanded:
        try:
            entrada = m.case_input(vals)
        except ValueError as e:
            return infeasible_envelope(f"Caso '{name}': {_erro(e)}")
        p = with_defaults(specs, vals)
        ok, cons, _ = m.sizing_constraints(entrada, p, k)
        if not ok:
            todos = _preparar_todos(m, expanded, specs, k)
            ok_p, p_env = m.envelope_params([p for *_, p in todos])
            return infeasible_envelope(f"Caso '{name}': {cons}", case_names=names, metodo=m, preparo=todos,
                                       p_env=p_env if ok_p else None)
        names.append(name)
        conss.append(cons)
        params.append(p)
        preparo.append((name, entrada, cons, p))
        per_case.append(m.size_equipment(eq, entrada, vals))

    ok_p, p_env = m.envelope_params(params)
    if not ok_p:
        return infeasible_envelope(p_env, case_names=names, per_case=per_case, ceiling=_menor_teto(m, conss)[0],
                                   metodo=m, preparo=preparo)
    eixo = m.sweep_axis(p_env)
    if not eixo.values:
        return infeasible_envelope(f"Grade de {eixo.label} vazia.", case_names=names, per_case=per_case,
                                   metodo=m, preparo=preparo, p_env=p_env)

    # extensão do V2: o método pode marcar as restrições com que o envelope varre a grade
    # (um caso só classificado, não dimensionante). O default devolve as mesmas, e aí nada muda.
    conss = list(m.envelope_constraints(conss, p_env))
    preparo = [(nome, entrada, c, p) for (nome, entrada, _, p), c in zip(preparo, conss)]
    teto, i_teto = _menor_teto(m, conss)
    mecan = m.ceiling_mechanism_of(conss[i_teto])
    pcs = m.envelope_case_params(conss, p_env)
    def linha(x):
        per_case_y = [m.requirement(x, c) for c in conss]
        idx = max(range(len(per_case_y)), key=per_case_y.__getitem__)
        y = per_case_y[idx]
        gov = m.governing_of(x, conss[idx])
        d = m.derived(x, y, gov, conss[idx], k, p_env)
        ok = x <= teto and all(m.case_admissible(x, c, pc) for c, pc in zip(conss, pcs)) and m.admissible(x, d, p_env)
        return EnvelopeRow(x, y, d, gov, names[idx], per_case_y, ok, m.presentation_data(x, conss[idx], k, p_env))

    rows = [linha(x) for x in eixo.values]
    admissivel = [r for r in rows if r.ok]
    if admissivel:   # refino local (extensão do V2): o método diz que abscissas extra avaliar
        escolhido = min(admissivel, key=lambda r: m.objective(r.x, r.derivados, p_env))
        vistos = {r.x for r in rows}
        extra = [linha(x) for x in m.refinar_eixo(p_env, escolhido.x, eixo) if x not in vistos]
        if extra:
            rows = sorted(rows + extra, key=lambda r: r.x)
            admissivel = [r for r in rows if r.ok]
    if not admissivel:
        msg = m.selection_message(rows, teto, p_env, mechanism=mecan) + _sem_intersecao(m, eixo, conss, names, pcs)
        return infeasible_envelope(f"Não há equipamento que atenda simultaneamente aos {len(names)} casos. " + msg,
                                   case_names=names, rows=rows, per_case=per_case, ceiling=teto,
                                   ceiling_case=names[i_teto], ceiling_mechanism=mecan, metodo=m, preparo=preparo,
                                   p_env=p_env, pcs=pcs)
    best = min(admissivel, key=lambda r: m.objective(r.x, r.derivados, p_env))
    slack = [best.y - v for v in best.per_case_y]
    return EnvelopeResult(True, "", best.x, best.y, best.derivados, best.governing, best.driver_case, teto,
                          names[i_teto], mecan, names, rows, slack, per_case,
                          m.envelope_derived(best.x, conss, pcs, p_env), metodo=m, preparo=tuple(preparo),
                          p_env=p_env, pcs=tuple(pcs))


def governing_summary(m, r):
    """Uma linha: quem governa, por qual caso, e o teto (se houver)."""
    if not r.feasible:
        return r.message
    resumo = f"Governa: {m.governing_label(r.governing)}, pelo caso '{r.driver_case}'."
    if not math.isfinite(r.ceiling):
        return resumo
    return resumo + f" Teto de decantação: {round(r.ceiling)} mm, imposto pelo caso '{r.ceiling_case}'."



