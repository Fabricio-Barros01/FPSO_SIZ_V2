"""Alarmes de inviabilidade e investigação por variantes (F13).

A unidade do BOT é um projeto básico real: um TAG inviável é ALARME de erro de premissa,
numérico ou de modelo (config/pfd/alarmes.toml). Aqui:

- `alarmes(planta)`: um alarme por TAG inviável, com a evidência do próprio resultado (o
  que falhou, que casos têm solução isolados e com que x) e as hipóteses registradas;
- `executar_variante(ctx, ident, v)`: o mesmo serviço por TAG com a alteração declarada
  (premissa do balanço, entrada geral do TAG ou vazão dividida por trens em paralelo). A
  variante é estudo: não muda o contexto nem o resultado padrão.

Nada aqui é física nova: só se escolhe o que o motor avalia.
"""
import copy
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd.equipamento import INVIAVEL


def cfg():
    return carregar("pfd/alarmes.toml")


def registro(ident):
    return next((a for a in cfg()["alarme"] if a["tag"] == ident), None)


@dataclass(frozen=True)
class Evidencia:
    mensagem: str
    casos_viaveis: tuple      # ((nome, x), ...) casos com solução isolados
    casos_inviaveis: tuple    # ((nome, motivo), ...)
    teto: float = math.nan
    caso_teto: str = ""


def evidencia(rt):
    r = rt.resultado
    viaveis = tuple((n, pc.x) for n, pc in zip(r.case_names, r.per_case) if pc.feasible)
    inviaveis = tuple((n, pc.message) for n, pc in zip(r.case_names, r.per_case) if not pc.feasible)
    return Evidencia(r.message, viaveis, inviaveis, r.ceiling, r.ceiling_case)


def alarmes(planta):
    """[(ResultadoTAG, Evidencia, registro ou None)] dos TAGs inviáveis, na ordem da planta.
    Registro ausente = alarme sem investigação anotada (também é pendência)."""
    return [(t, evidencia(t), registro(t.tag.tag)) for t in planta.tags if t.status == INVIAVEL]


def variante(nome):
    return cfg()["variantes"][nome]


def executar_variante(ctx, ident, v, estado=None):
    """ResultadoTAG do TAG com a variante `v` (dict de alarmes.toml). O contexto original não
    é tocado: premissas alteradas criam outro contexto (com o mesmo arquivo de casos e as
    mesmas propostas)."""
    if v.get("premissas"):
        ctx = servico.Contexto(ctx.dados, alteracoes={**ctx.alteracoes, **v["premissas"]}, propostas=ctx.propostas,
                               oleo_vivo=ctx.oleo_vivo)
    base = copy.deepcopy(estado) if estado is not None else servico.estado_inicial(ident)
    for chave, valor in v.get("geral", {}).items():
        base.editar(chave, float(valor), None, {})
    fator = v.get("fator_vazao")
    if fator:
        rt0 = servico.dimensionar(servico.preparar(ctx, base), base)
        for c in rt0.entradas.casos:
            for chave in v["chaves_vazao"]:
                val = c.valores.get(chave)
                if val is not None and not val.lacuna and not val.faixa and math.isfinite(val.valor):
                    base.editar(chave, val.valor / fator, [c.num], {})
    return servico.dimensionar(servico.preparar(ctx, base), base)


def investigar(ctx, planta):
    """[(ident, rótulo da variante, origem, ResultadoTAG)] das variantes registradas para os
    TAGs em alarme."""
    out = []
    for t, _, reg in alarmes(planta):
        if reg is None:
            continue
        for h in reg["hipoteses"]:
            for nome in h.get("variantes", []):
                v = variante(nome)
                out.append((t.tag.tag, nome, v, executar_variante(ctx, t.tag.tag, v)))
    return out
