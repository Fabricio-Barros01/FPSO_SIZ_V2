"""A planta inteira: o atalho que percorre o serviço por TAG (pfd/equipamento.py) para os
11 TAGs, com o mesmo contexto (o balanço é resolvido uma vez).

Um envelope independente por TAG, sobre os casos ativos naquele TAG, sem interpolação
entre casos. TAG com lacuna não é dimensionado: fica "aguardando entrada", com a lista do
que falta; os demais seguem. Cada TAG usa o modo salvo nos ajustes (manual ou automático);
sem estado salvo, o automático.
"""
from dataclasses import dataclass, field

from fpso_siz.balanco.balancos import topologia
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


def dimensionar(dados=None, prem=None, ajustes=None, balanco=None, contexto=None, oleo_vivo=True,
                topologia_julia=False):
    """Planta dimensionada: um ResultadoTAG por TAG, todos pelo serviço por TAG.
    `ajustes`: Ajustes, ou o dict do arquivo de ajustes. `oleo_vivo=False`: viscosidade do
    óleo morto; `topologia_julia=True`: alocação de correntes do PFD F1 do Julia (os dois são o
    modo de paridade com as fixtures do Julia e da F10b)."""
    ctx = contexto if contexto is not None else Contexto(dados, prem=prem, balanco=balanco, oleo_vivo=oleo_vivo,
                                                         topologia_julia=topologia_julia)
    aj = normalizar(ajustes)
    estados = [aj.tags.get(t.tag) or equipamento.estado_inicial(t.tag) for t in tags()]
    if any(e.modo == equipamento.AUTOMATICO for e in estados):
        ctx.balanco  # noqa: B018  (valida uma vez, antes de percorrer os TAGs)
    return Planta(ctx, [equipamento.executar(ctx, e) for e in estados], aj)
