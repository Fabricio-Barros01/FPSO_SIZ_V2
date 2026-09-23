"""Método configurado por um TOML de config/equipment/ (rótulo, referência, descritores)
e, opcionalmente, com campos de corrente reescritos por um segundo TOML."""
from dataclasses import replace

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.contrato import MetodoDimensionamento
from fpso_siz.core.parametros import parameter_specs


class MetodoTOML(MetodoDimensionamento):
    config = ""             # ex. "equipment/separator/stewart_arnold.toml"
    rotulo_padrao = ""
    ajustes_corrente = ""   # TOML com os campos de corrente que o método reescreve

    def method_config(self):
        return carregar(self.config)

    @property
    def label(self):
        return self.method_config().get("label", self.rotulo_padrao)

    def method_reference(self):
        return self.method_config().get("reference", "")

    def parameters(self):
        return parameter_specs(self.method_config())

    def stream_parameters(self):
        """Default filtrado por stream_keys; campos listados em `ajustes_corrente` têm rótulo,
        default e nota reescritos (unidade, faixa e ordem continuam de stream.toml)."""
        base = super().stream_parameters()
        if not self.ajustes_corrente:
            return base
        aj = carregar(self.ajustes_corrente)
        return [replace(s, **aj[s.key]) if s.key in aj else s for s in base]


def driver_case(r):
    """Um SizingResult não tem caso governante — ele É um caso: travessão."""
    return getattr(r, "driver_case", "—")
