"""Os casos BOT que mantinham os alarmes abertos, depois da película nos três regimes.

É o item do aceite que amarra a física nova aos casos reais: BOT 04, BOT 05 e BOT 06 (os de
baixa carga) e os dez casos ativos do P-001. O que se prova aqui é que NENHUM caso é mais
recusado por falta de correlação, e que o que restou de inviabilidade tem restrição governante
identificada — a ÁREA no P-001. No P-003 o comprimento só volta a bloquear com o tubo de 25,4 mm.

Os regimes afirmados aqui são os medidos na geometria recomendada de cada TAG (12,7 mm, um
passe): o Reynolds de cada caso está no teste, e a tabela completa está em
`docs/validacao/24-pelicula-baixo-reynolds.md`.
"""
import math
from types import SimpleNamespace

import pytest

from fpso_siz.core import memoria
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd.tags import tag
from fpso_siz.sizing import pelicula as pel


def candidato(ctx, ident, edits=None, ligada=True):
    """O TAG com as recomendações e as edições dadas, pelo serviço; no inviável, o feixe mais
    próximo de atender (hook `bloqueios`, pelo lado do dimensionamento)."""
    e = servico.estado_inicial(ident)
    valores = {k: v["valor"] for k, v in tag(ident).recomendadas.items()}
    valores.update(edits or {})
    valores["pelicula_baixo_re"] = 1.0 if ligada else 0.0
    for chave, valor in valores.items():
        e.editar(chave, float(valor), None, {})
    rt = servico.dimensionar(servico.preparar(ctx, e), e)
    r = rt.resultado
    if r.feasible:
        return SimpleNamespace(rt=rt, viavel=True, x=r.x, y=r.y, bloqueios=(), operacao=memoria.operacao(r))
    bloqueios, row, op, _ = memoria.feixe_mais_proximo(r)
    return SimpleNamespace(rt=rt, viavel=False, x=row.x, y=row.y, bloqueios=bloqueios, operacao=op)


def operacao(c):
    return {nome[:6]: dict(caso=nome, **o) for nome, o in c.operacao}


def test_a_pelicula_esta_ligada_nos_tres_tags_com_fonte():
    """A extensão entra por recomendação com fonte no TAG, não por default do método — o default
    continua sendo a regra do Julia (só Dittus-Boelter)."""
    from fpso_siz.sizing.trocador import SaariLMTD
    padrao = {s.key: s.default for s in SaariLMTD().parameters()}
    assert padrao["pelicula_baixo_re"] == 0.0 and padrao["razao_visc_parede"] == 1.0
    for ident in ("P-001", "P-002", "P-003"):
        rec = tag(ident).recomendadas["pelicula_baixo_re"]
        assert rec["valor"] == 1.0 and "Branan" in rec["fonte"] and "2-10" in rec["fonte"]


def test_p002_viavel_e_os_casos_de_baixa_carga_calculam(planta_propostas):
    """O BOT 06 (3,6 % da carga de projeto) era o único bloqueio do P-002. Na geometria que a
    reotimização escolhe (12,7 mm, um passe) ele cai no LAMINAR, Re ≈ 1.416, e é calculado por
    Hausen; o BOT 04 (Re ≈ 4.145) e o BOT 05 (Re ≈ 5.461) caem na transição. O TAG fica viável —
    sem circulação fixa e sem mudar arquitetura."""
    ctx = planta_propostas.contexto
    c = candidato(ctx, "P-002")
    assert c.viavel and not c.bloqueios
    op = operacao(c)
    seis = op["BOT 06"]
    assert seis["regime"] == pel.LAMINAR and seis["nu_valido"]
    assert seis["re"] <= 2000 and math.isfinite(seis["h_i"]) and seis["h_i"] > 0
    assert "2-10" in seis["correlacao"]
    # a interpolação da transição é exercida pela planta, e não só pelo caso-ouro
    for caso in ("BOT 04", "BOT 05"):
        o = op[caso]
        assert o["regime"] == pel.TRANSICAO and o["nu_valido"], caso
        assert 2000 < o["re"] < 1e4 and o["h_i"] > 0, caso
        assert "2-12" in o["correlacao"], caso
    # e o estado do TAG na planta é dimensionado
    assert planta_propostas.tag("P-002").status == servico.DIMENSIONADO


def test_os_dois_trocadores_sao_viaveis_com_um_casco(planta_propostas):
    """Item da ordem de execução: não se adota divisão em cascos antes de saber se ela é
    necessária — e ela NÃO é. Com a geometria recomendada, sobre a física corrigida
    (tubo de 12,7 mm), P-002 e P-003 são viáveis com um casco só, dentro dos limites de 6 m e
    2.500 mm."""
    ctx = planta_propostas.contexto
    for ident in ("P-002", "P-003"):
        c = candidato(ctx, ident)
        assert c.viavel and not c.bloqueios, ident
        assert c.y <= 6.0, ident
        for caso in c.rt.entradas.casos:
            if caso.ativo:
                for chave in ("cascos_serie", "cascos_paralelo"):
                    assert chave not in caso.valores or caso.valores[chave].valor == 1.0, (ident, chave)


# Reynolds medido na geometria escolhida (12,7 mm, um passe, 7.526 tubos/passe): os três casos de
# baixa carga ficam no laminar, e a transição aparece nos BOT 11, 15 e 16.
@pytest.mark.parametrize("caso, regime", [("BOT 04", pel.LAMINAR), ("BOT 05", pel.LAMINAR),
                                          ("BOT 06", pel.LAMINAR), ("BOT 11", pel.TRANSICAO),
                                          ("BOT 15", pel.TRANSICAO), ("BOT 16", pel.TRANSICAO)])
def test_p003_casos_de_baixa_carga_calculam(planta_propostas, caso, regime):
    """Os casos que o P-003 não conseguia calcular agora calculam, no regime que o Reynolds
    indica, e nenhum é recusado por correlação."""
    c = candidato(planta_propostas.contexto, "P-003")
    op = operacao(c)[caso]
    assert op["regime"] == regime and op["nu_valido"] and op["h_i"] > 0
    assert (op["re"] <= 2000) if regime == pel.LAMINAR else (2000 < op["re"] < 1e4)
    assert "dittus_boelter" not in {crit for crit, _ in c.bloqueios}


def test_p003_o_comprimento_deixa_de_bloquear_com_o_tubo_menor(planta_propostas):
    """Com a física corrigida, o que restava no P-003 era o limite de estoque de 6 m — e ele cai com
    o tubo de 12,7 mm, que acomoda mais tubos no mesmo casco. Com o tubo de 25,4 mm (o que a física
    antiga escolhia) o bloqueio de comprimento reaparece: é geometria, não correlação."""
    ctx = planta_propostas.contexto
    escolhido = candidato(ctx, "P-003")
    assert escolhido.viavel and escolhido.y <= 6.0
    grosso = candidato(ctx, "P-003", {"d_externo": 25.4})
    assert not grosso.viavel and {crit for crit, _ in grosso.bloqueios} == {"comprimento"}
    assert grosso.y > 6.0
    # em nenhum dos dois há recusa por correlação
    for c in (escolhido, grosso):
        assert "dittus_boelter" not in {crit for crit, _ in c.bloqueios}


def test_p001_todos_os_casos_calculam_e_o_que_governa_e_area(planta_propostas):
    """No P-001 a lacuna metodológica fechou: os dez casos ativos calculam. O que impede é a área
    — comprimento de tubo muito acima do limite —, e com 2 passes o domínio do fator F vem antes."""
    ctx = planta_propostas.contexto
    # estudo DESIGN sobre o alvo preliminar (o TAG da planta apresenta a geometria do rating, nota 45)
    e = servico.estado_inicial("P-001")
    dois_passes = servico.dimensionar(servico.preparar(ctx, e), e).resultado
    assert not dois_passes.feasible and "fator de correção F" in dois_passes.message
    c = candidato(ctx, "P-001", {"passes_tubo": 1.0})
    assert not c.viavel and {crit for crit, _ in c.bloqueios} == {"comprimento"}
    op = operacao(c)
    assert len(op) == 10
    assert all(o["nu_valido"] and o["h_i"] > 0 for o in op.values())
    assert {o["regime"] for o in op.values()} <= {pel.LAMINAR, pel.TRANSICAO, pel.TURBULENTO}
    # o platô laminar é o que explica a área: h_i de uma ordem de grandeza abaixo do turbulento
    laminares = [o["h_i"] for o in op.values() if o["regime"] == pel.LAMINAR]
    turbulentos = [o["h_i"] for o in op.values() if o["regime"] == pel.TURBULENTO]
    if laminares and turbulentos:
        assert max(laminares) < min(turbulentos)


def test_nenhum_caso_dos_tres_tags_e_recusado_por_correlacao(planta_propostas):
    """A varredura do aceite: em nenhum dos três TAGs sobra recusa por correlação do lado tubo."""
    ctx = planta_propostas.contexto
    for ident, edits in (("P-001", {"passes_tubo": 1.0}), ("P-002", {}), ("P-003", {})):
        c = candidato(ctx, ident, edits)
        assert "dittus_boelter" not in {crit for crit, _ in c.bloqueios}, ident
        assert all(o["nu_valido"] for _, o in c.operacao), ident


def test_a_temperatura_de_parede_vai_para_o_rastro(planta_propostas):
    """A eq. 2-9 é calculada e rastreada — a hipótese do fator de parede não é silenciosa."""
    rt = planta_propostas.tag("P-002")
    vars_ = {e.var for pc in rt.resultado.per_case for e in pc.trace.entries}
    assert "T média do tubo" in vars_ and "T média do casco" in vars_ and "hipótese" in vars_
    c = candidato(planta_propostas.contexto, "P-002")
    conss = memoria.restricoes(c.rt.resultado)
    from fpso_siz.sizing import trocador as tr
    t = tr._tubo(conss[0], int(c.x))
    assert math.isfinite(t["t_parede"])
