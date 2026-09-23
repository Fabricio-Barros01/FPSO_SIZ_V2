"""A planta inteira (F10b): balanço → entradas de cada TAG → envelope de cada TAG.

Um envelope independente por TAG, sobre os casos do balanço ativos naquele TAG, sem
interpolação entre casos. TAG com lacuna não é dimensionado: fica "aguardando entrada",
com a lista do que falta.
"""
from dataclasses import dataclass, field

from fpso_siz.balanco.balancos import topologia
from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core.motor import size_envelope
from fpso_siz.pfd import fluidos
from fpso_siz.pfd.entradas import montar
from fpso_siz.pfd.tags import tags

AGUARDANDO = "aguardando_entrada"
DIMENSIONADO = "dimensionado"
INVIAVEL = "inviavel"
INATIVO = "inativo"


@dataclass
class ResultadoTAG:
    entradas: object          # EntradasTAG
    resultado: object = None  # EnvelopeResult, ou None se aguardando entrada

    @property
    def tag(self):
        return self.entradas.tag

    @property
    def status(self):
        if not any(c.ativo for c in self.entradas.casos):
            return INATIVO
        if not self.entradas.pronto:
            return AGUARDANDO
        return DIMENSIONADO if self.resultado.feasible else INVIAVEL


@dataclass
class Planta:
    dados: object
    prem: dict
    balanco: list
    tags: list
    ajustes: dict = field(default_factory=dict)
    versoes: dict = field(default_factory=dict)

    def tag(self, nome):
        return next(t for t in self.tags if t.tag.tag == nome)

    @property
    def completa(self):
        return all(t.status in (DIMENSIONADO, INATIVO) for t in self.tags)

    @property
    def sem_dimensionamento(self):
        mapeados = {t.tag.bloco for t in self.tags}
        return [b["id"] for b in topologia()["blocos"] if b["id"] not in mapeados]


def dimensionar(dados, prem=None, ajustes=None, balanco=None):
    """Planta dimensionada a partir do arquivo de casos. `ajustes`: {TAG: {chave: valor,
    'caso': {num: {chave: valor}}}} — o input extra do usuário."""
    prem = premissas(dados) if prem is None else prem
    ajustes = {} if ajustes is None else ajustes
    if not isinstance(ajustes, dict):
        raise ValueError("ajustes: esperada tabela por TAG")
    conhecidos = {t.tag for t in tags()}
    desconhecidos = sorted(set(ajustes) - conhecidos)
    if desconhecidos:
        raise ValueError(f"ajustes para TAGs desconhecidos: {desconhecidos}; conhecidos: {sorted(conhecidos)}")
    balanco = resolver_todos(dados, prem) if balanco is None else balanco
    if not balanco or len({r.num for r in balanco}) != len(balanco):
        raise ValueError("balanço sem casos ou com números de caso duplicados")
    if {r.num for r in balanco} != {c["num"] for c in dados.casos}:
        raise ValueError("casos do balanço não correspondem ao arquivo de entrada")
    if any(not r.convergiu for r in balanco):
        raise ValueError("balanço não convergiu; reveja os casos antes de dimensionar a planta")
    resultados = []
    for t in tags():
        e = montar(t, balanco, dados, prem, ajustes.get(t.tag, {}))
        r = size_envelope(e.equipamento, e.metodo, e.case_set()) if e.pronto and any(c.ativo for c in e.casos) else None
        resultados.append(ResultadoTAG(e, r))
    return Planta(dados, prem, balanco, resultados, ajustes, fluidos.versoes())
