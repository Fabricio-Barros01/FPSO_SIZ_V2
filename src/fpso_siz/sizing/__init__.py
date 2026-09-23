"""Métodos de dimensionamento de equipamentos, registrados no núcleo ao importar."""
from fpso_siz.core import registro
from fpso_siz.sizing.bomba import CentrifugalPump, MoranPumpSizing
from fpso_siz.sizing.knockout import KnockoutDrum, StewartArnoldTwoPhase
from fpso_siz.sizing.separador import Separator, StewartArnold
from fpso_siz.sizing.tratador import ArnoldElectrostatic, ElectrostaticTreater
from fpso_siz.sizing.trocador import SaariLMTD, ShellTubeExchanger


def registrar():
    for obj in (Separator(), StewartArnold(), KnockoutDrum(), StewartArnoldTwoPhase(), ElectrostaticTreater(),
                ArnoldElectrostatic(), CentrifugalPump(), MoranPumpSizing(), ShellTubeExchanger(), SaariLMTD()):
        registro.register(obj)


registrar()
