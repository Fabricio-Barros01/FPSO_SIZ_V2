"""A planta inteira: o atalho que percorre o serviço por TAG (pfd/equipamento.py) para os
11 TAGs, com o mesmo contexto (o balanço é resolvido uma vez).

Um envelope independente por TAG, sobre os casos ativos naquele TAG, sem interpolação
entre casos. TAG com lacuna não é dimensionado: fica "aguardando entrada", com a lista do
que falta; os demais seguem. Cada TAG usa o modo salvo nos ajustes (manual ou automático);
sem estado salvo, o automático.
"""
import math
from dataclasses import dataclass, field, replace

from fpso_siz.balanco.balancos import topologia
from fpso_siz.balanco.modelo import aplicar_rating_termico
from fpso_siz.pfd import equipamento
from fpso_siz.pfd.ajustes import Ajustes, ler
# reexportados: a planta e o TAG isolado falam dos mesmos estados
from fpso_siz.pfd.equipamento import (AGUARDANDO, DIMENSIONADO, INATIVO, INVIAVEL, Contexto,  # noqa: F401
                                      ResultadoTAG)
from fpso_siz.pfd.tags import tags


@dataclass
class Planta:
    contexto: object
    tags: list                                        # ResultadoTAG, na ordem dos TAGs
    ajustes: object = field(default_factory=Ajustes)  # estado de sessão usado

    @property
    def dados(self):
        return self.contexto.dados

    @property
    def prem(self):
        return self.contexto.prem

    @property
    def balanco(self):
        return self.contexto.balanco

    @property
    def versoes(self):
        return self.contexto.versoes

    def tag(self, nome):
        return next(t for t in self.tags if t.tag.tag == nome)

    @property
    def completa(self):
        return all(t.concluido for t in self.tags)

    @property
    def sem_dimensionamento(self):
        return equipamento.blocos_sem_dimensionamento(topologia())


def normalizar(ajustes):
    """None, dict lido de TOML (esquema 2 ou legado F10b) ou Ajustes → Ajustes."""
    if ajustes is None:
        return Ajustes()
    if isinstance(ajustes, Ajustes):
        return ajustes
    return ler(ajustes)


def dimensionar(dados=None, prem=None, ajustes=None, balanco=None, contexto=None, somente=None):
    """Planta dimensionada: um ResultadoTAG por TAG, todos pelo serviço por TAG.
    `ajustes`: Ajustes, ou o dict do arquivo de ajustes. `somente`: os TAGs a dimensionar (None =
    todos) — cada TAG é dimensionado pelo serviço a partir do mesmo contexto, independente dos
    outros, então o recorte não muda o resultado dos que ficam."""
    ctx = contexto if contexto is not None else Contexto(dados, prem=prem, balanco=balanco)
    aj = normalizar(ajustes)
    estados = [aj.tags.get(t.tag) or equipamento.estado_inicial(t.tag) for t in tags()
               if somente is None or t.tag in somente]
    if any(e.modo == equipamento.AUTOMATICO for e in estados):
        ctx.balanco  # noqa: B018  (valida uma vez, antes de percorrer os TAGs)
    # P-001 é o elo entre balanço e sizing: primeiro materializa uma geometria, depois faz
    # rating dos 16 casos e só então P-002/P-003 recebem cargas e temperaturas realizadas.
    estado_p001 = next((e for e in estados if e.id == "P-001" and e.modo == equipamento.AUTOMATICO), None)
    operacao = None
    if estado_p001 is not None:
        entradas_p001 = equipamento.preparar(ctx, estado_p001)
        if entradas_p001.pronto:
            operacao = equipamento.avaliar_p001(ctx.balanco, entradas_p001)
            atualizados = []
            casos_operacao = []
            for r in ctx.balanco:
                op = operacao.caso(r.num)
                atualizado = aplicar_rating_termico(r, op.Q_real, ctx.prem)
                # A operação e o resolvedor usam a mesma equação. Esta conferência impede
                # que o objeto publicado pelo P-001 divirja do estado que alimenta P-002/003.
                publicados = (op.t_fria_out, op.t_quente_out, op.q_p002, op.q_p003)
                resolvidos = (atualizado.T["C-07"], atualizado.T["C-23"],
                              atualizado.duties["Q_H"], atualizado.duties["Q_C"])
                if not all(math.isclose(a, b) for a, b in zip(resolvidos, publicados)):
                    raise ValueError(f"P-001: segunda etapa térmica divergiu no caso {r.num}")
                atualizados.append(atualizado)
                casos_operacao.append(replace(op, t_fria_out=atualizado.T["C-07"],
                    t_quente_out=atualizado.T["C-23"], q_p002=atualizado.duties["Q_H"],
                    q_p003=atualizado.duties["Q_C"]))
            operacao = replace(operacao, casos=tuple(casos_operacao))
            ctx._resultados = ctx._balanco = atualizados
            ctx.cache.clear()
    resultados = [equipamento.executar(ctx, e) for e in estados]
    if operacao is not None:
        rt = next(r for r in resultados if r.tag.tag == "P-001")
        rt.operacao = operacao
    return Planta(ctx, resultados, aj)
