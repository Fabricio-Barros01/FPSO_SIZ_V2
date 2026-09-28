"""Contrato único de proveniência de propriedade (config/termo/proveniencia.toml).

`validade` (validada | nao_validada | ausente) e `origem` (o modelo ou o dado) são conceitos
independentes; `consumidores` diz quem usa o valor hoje. A proveniência de um cálculo é o que
ele CONSUMIU: `consumidas("balanco")` e `da_regra(regra)` só devolvem propriedades com aquele
consumidor. Nada aqui promove propriedade — o contrato é lido, não negociado em runtime.

`casos` (opcional) restringe o consumo a uma classe de caso: "avaliaveis" (o trem produtivo:
recombinação da Nota 4 + flash) ou "nao_avaliaveis" (casos com gás de lift, por Standing).
"""
from fpso_siz.core.configuracao import carregar

VALIDADA, NAO_VALIDADA, AUSENTE = "validada", "nao_validada", "ausente"
AVALIAVEIS, NAO_AVALIAVEIS = "avaliaveis", "nao_avaliaveis"


def cfg():
    return carregar("termo/proveniencia.toml")


def declaracoes():
    """{id: declaração}, na ordem do contrato."""
    return {p["id"]: p for p in cfg()["propriedade"]}


def de(ident):
    d = declaracoes()
    if ident not in d:
        raise ValueError(f"propriedade fora do contrato de proveniência: {ident!r}")
    return d[ident]


def aplica(p, avaliavel):
    """A declaração vale para um caso avaliável (True), não avaliável (False) ou qualquer (None)?"""
    casos = p.get("casos")
    return casos is None or avaliavel is None or casos == (AVALIAVEIS if avaliavel else NAO_AVALIAVEIS)


def consumidas(consumidor, avaliavel=None):
    """{id: {origem, validade}} das propriedades que `consumidor` realmente usa — num caso
    avaliável, não avaliável, ou em algum caso (None)."""
    return {i: dict(origem=list(p["origem"]), validade=p["validade"])
            for i, p in declaracoes().items() if consumidor in p["consumidores"] and aplica(p, avaliavel)}


def da_regra(regra):
    """Id da propriedade entregue pela regra de entrada de TAG `regra`, ou None."""
    return next((i for i, p in declaracoes().items() if p.get("regra") == regra), None)


def conferir():
    """Divergências internas do contrato (vazia = válido): enums conhecidos, e nada que não
    seja validado tem consumidor."""
    c = cfg()
    erros = []
    for i, p in declaracoes().items():
        if p["validade"] not in c["validade"]:
            erros.append(f"{i}: validade desconhecida {p['validade']!r}")
        for o in p["origem"]:
            if o not in c["origem"]:
                erros.append(f"{i}: origem desconhecida {o!r}")
        if p["validade"] != VALIDADA and p["consumidores"]:
            erros.append(f"{i}: {p['validade']} e consumida por {p['consumidores']}")
        if p["validade"] == AUSENTE and p["origem"]:
            erros.append(f"{i}: ausente, mas declara origem {p['origem']}")
        if p.get("casos") not in (None, AVALIAVEIS, NAO_AVALIAVEIS):
            erros.append(f"{i}: classe de caso desconhecida {p['casos']!r}")
    return erros
