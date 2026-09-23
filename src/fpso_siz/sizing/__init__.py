"""Métodos de dimensionamento de equipamentos, registrados no núcleo ao importar."""
from fpso_siz.core import registro
from fpso_siz.sizing.knockout import KnockoutDrum, StewartArnoldTwoPhase
from fpso_siz.sizing.separador import Separator, StewartArnold
from fpso_siz.sizing.tratador import ArnoldElectrostatic, ElectrostaticTreater


def registrar():
    for obj in (Separator(), StewartArnold(), KnockoutDrum(), StewartArnoldTwoPhase(), ElectrostaticTreater(),
                ArnoldElectrostatic()):
        registro.register(obj)


registrar()
