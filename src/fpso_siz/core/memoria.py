"""Dados da memória de cálculo de um envelope, do lado do DIMENSIONAMENTO.

Tudo o que o memorial mostra e que exige avaliar o método — critério governante por caso,
capacidades e bordas da banda no diagrama, operandos da seleção, perfil T × Q, parcelas de
1/U, curva do sistema, NPSH, operação por caso, feixe mais próximo de um envelope inviável —
sai daqui, sobre as restrições que o PRÓPRIO motor preparou (`EnvelopeResult.preparo`) e os
parâmetros que ele usou (`p_env`, `pcs`). Nada é re-preparado: o memorial (`pfd/memorial.py`)
só lê e formata. Como o motor, este módulo não cita grandeza nenhuma: só hooks do método.
"""
import math


def _linha_em(sweep, x):
    return next((r for r in sweep if r.x == x), None)


def indice_governante(r):
    """Caso do passo a passo: o que governa o ponto escolhido; se inviável, o do teto; se não
    há nem um nem outro, o primeiro caso ativo."""
    for nome in (r.driver_case, r.ceiling_case):
        if nome and nome in r.case_names:
            return r.case_names.index(nome)
    return 0


def restricoes(r):
    """Restrições de cada caso (None para o que não preparou), na ordem da preparação."""
    return [c for _, _, c, _ in r.preparo]


def x_referencia(r):
    """Abscissa das comparações por caso: o ponto escolhido, ou, se inviável, o menor x da
    grade admissível pelo método (o que o teto impede)."""
    if r.feasible:
        return r.x
    if r.p_env is None:
        return None
    na_banda = [row.x for row in r.rows if r.metodo.admissible(row.x, row.derivados, r.p_env)]
    return min(na_banda) if na_banda else None


def governantes(r, x):
    """Critério governante de cada caso em `x`, por `governing_of` sobre as restrições do caso —
    não por busca na varredura individual, cuja grade pode não conter `x`
    (docs/validacao/32-auditoria-de-saida.md)."""
    if x is None:
        return [None] * len(r.case_names)
    return [None if c is None else r.metodo.governing_of(x, c) for c in restricoes(r)]


def capacidades(r, x):
    """Exigência de cada critério em `x`, envelopada sobre os casos (`per_constraint`)."""
    caps = {}
    for c in restricoes(r):
        if c is None:
            continue
        for chave, v in r.metodo.per_constraint(x, c).items():
            caps[chave] = max(caps.get(chave, -math.inf), v)
    return caps


def diagrama(r):
    """Linhas do diagrama x × exigência: capacidades envelopadas e bordas da banda por linha.
    Vazio se o método não declara banda."""
    m = r.metodo
    if not r.rows or r.p_env is None or not hasattr(m, "bordas_banda"):
        return []
    k = m.constants()
    out = []
    for row in r.rows:
        lo, hi = m.bordas_banda(row.x, row.governing, r.p_env, k)
        out.append(dict(x=row.x, y=row.y, capacidades=capacidades(r, row.x), banda_min=lo, banda_max=hi,
                        admissivel=int(row.ok)))
    return out


def banda(r):
    m = r.metodo
    return m.banda_memorial(r.p_env) if r.p_env is not None and hasattr(m, "banda_memorial") else None


def selecao(r, i):
    """Operandos do ponto escolhido do envelope (só com resultado viável)."""
    m = r.metodo
    if not r.feasible or not hasattr(m, "selecao_memorial"):
        return None
    return m.selecao_memorial(r.x, r.y, r.derivados, r.per_case[i].trace, m.constants())


def caso_do_metodo(r):
    """Índice do caso dos gráficos próprios do método: o governante, ou, se ele não preparou,
    o primeiro caso que prepara."""
    cons = restricoes(r)
    i = indice_governante(r)
    if i >= len(cons) or cons[i] is None:
        i = next((j for j, c in enumerate(cons) if c is not None), i)
    return i


def perfil_tq(r):
    """Perfil T × Q do caso do método: [(q, t_tubo, t_casco)]. Sai também no inviável."""
    m = r.metodo
    i = caso_do_metodo(r)
    _, entrada, c, _ = r.preparo[i]
    if not hasattr(m, "perfil_tq") or c is None:
        return None
    perfil = m.perfil_tq(entrada, c)
    return [(q, tt, tc) for (q, tt), (_, tc) in zip(perfil["tubo"], perfil["casco"])]


def parcelas_u(r):
    """(parcelas de 1/U, U) no ponto escolhido e no caso do método."""
    m = r.metodo
    c = r.preparo[caso_do_metodo(r)][2]
    if not r.feasible or not hasattr(m, "parcelas_u") or c is None:
        return None
    return m.parcelas_u(r.x, c)


def curva_sistema(r, fracoes):
    """(curva [(q, h)], h estática, ponto (q, h)) da bomba no DN escolhido."""
    m = r.metodo
    i = caso_do_metodo(r)
    c = r.preparo[i][2]
    if not r.feasible or not hasattr(m, "curva_sistema") or c is None:
        return None
    return m.curva_sistema(c, r.x, fracoes), c.h_est, (c.q_m3h, _linha_em(r.rows, r.x).per_case_y[i])


def npsh(r):
    """[(caso, NPSH disponível, NPSH exigido)] no DN escolhido."""
    m = r.metodo
    if not r.feasible or not hasattr(m, "npsh_exigido"):
        return None
    out = []
    for j, (pc, c) in enumerate(zip(r.per_case, restricoes(r))):
        lin = _linha_em(pc.sweep, r.x)
        if lin is None or c is None:
            continue
        out.append((j + 1, m.npsh_disponivel(lin.derivados), m.npsh_exigido(c)))
    return out


def operacao(r):
    """[(nome, operação)] de cada caso no ponto escolhido."""
    m = r.metodo
    cons = restricoes(r)
    if not r.feasible or not hasattr(m, "operacao_por_caso") or r.p_env is None or any(c is None for c in cons):
        return None
    return list(zip([n for n, *_ in r.preparo], m.operacao_por_caso(cons, r.x, list(r.pcs))))


def melhor_feixe(r, fator_area=1.0):
    """Diagnóstico de um envelope inviável pelo hook `bloqueios`: (bloqueios, área × fator,
    linha) da linha com menos bloqueios (critério, caso) e, entre elas, a de menor área. None
    se o método não diagnostica ou algum caso não prepara."""
    m = r.metodo
    cons = restricoes(r)
    if not r.rows or r.p_env is None or not hasattr(m, "bloqueios") or any(c is None for c in cons):
        return None
    pcs = list(r.pcs)
    linhas = [(tuple(sorted(set(m.bloqueios(row.x, cons, pcs, r.p_env)))), row.derivados.get("area", math.inf) * fator_area,
               row) for row in r.rows]
    return min(linhas, key=lambda t: (len(t[0]), t[1]))


def feixe_mais_proximo(r):
    """(bloqueios, linha, operação por caso, derivados V2) do feixe mais próximo de atender."""
    melhor = melhor_feixe(r)
    if melhor is None:
        return None
    bloqueios, _, row = melhor
    m = r.metodo
    cons, pcs = restricoes(r), list(r.pcs)
    return (bloqueios, row, list(zip([n for n, *_ in r.preparo], m.operacao_por_caso(cons, row.x, pcs))),
            dict(m.envelope_derived(row.x, cons, pcs, r.p_env)))
