"""Desenhos de terminal a partir da topologia do diagrama de blocos (config/topologia_db.toml).

Nada de desenho fixo do FPSO: as linhas saem das adjacências (entradas/saídas de cada
bloco), na ordem declarada. Misturadores, reciclo (saída para um bloco anterior), os dois
lados do trocador e as correntes de fronteira aparecem como estão na topologia. O modelo
(`arestas`, `linhas_planta`, `vizinhos`) é separado da renderização para ser verificado
contra a topologia, não só pela aparência.
"""
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.output.terminal.estilo import largura


@dataclass(frozen=True)
class Aresta:
    corrente: str
    origem: str | None     # bloco de onde sai; None = entrada de fronteira
    destino: str | None    # bloco aonde chega; None = saída de fronteira


@dataclass(frozen=True)
class LinhaPlanta:
    bloco: str
    entradas: tuple        # correntes
    saidas: tuple          # (corrente, destino | None, retorno: bool)


def arestas(topo):
    """Uma aresta por corrente, na ordem em que as correntes aparecem nos blocos."""
    origem, destino, ordem = {}, {}, []
    for b in topo["blocos"]:
        for s in (*b["entradas"], *b["saidas"]):
            if s not in ordem:
                ordem.append(s)
        for s in b["entradas"]:
            destino[s] = b["id"]
        for s in b["saidas"]:
            origem[s] = b["id"]
    return [Aresta(s, origem.get(s), destino.get(s)) for s in ordem]


def linhas_planta(topo):
    """Um bloco por linha, na ordem da topologia; saída para bloco anterior (ou para o
    próprio) é retorno (reciclo)."""
    pos = {b["id"]: i for i, b in enumerate(topo["blocos"])}
    destino = {a.corrente: a.destino for a in arestas(topo)}
    out = []
    for b in topo["blocos"]:
        saidas = tuple((s, destino[s], destino[s] is not None and pos[destino[s]] <= pos[b["id"]])
                       for s in b["saidas"])
        out.append(LinhaPlanta(b["id"], tuple(b["entradas"]), saidas))
    return out


def vizinhos(topo, bloco):
    """([(bloco de origem | None, corrente)], [(corrente, bloco de destino | None)])."""
    arest = {a.corrente: a for a in arestas(topo)}
    b = next(x for x in topo["blocos"] if x["id"] == bloco)
    return ([(arest[s].origem, s) for s in b["entradas"]], [(s, arest[s].destino) for s in b["saidas"]])


def glifos(estilo):
    return carregar("interativo.toml")["esquema"]["unicode" if estilo.unicode else "ascii"]


def _notas():
    return carregar("interativo.toml")["pfd"]["notas"]


def _quebrar_itens(prefixo, itens, colunas, recuo):
    """prefixo + itens separados por vírgula; o que não cabe continua alinhado ao início
    dos itens. Item nunca é partido."""
    linhas, atual = [], prefixo
    base = " " * largura(prefixo)
    for i, item in enumerate(itens):
        peca = item + ("," if i < len(itens) - 1 else "")
        vazio = atual in (prefixo, base)
        candidato = atual + ("" if vazio else " ") + peca
        if not vazio and largura(recuo + candidato) > colunas:
            linhas.append(atual)
            atual = base + peca
        else:
            atual = candidato
    linhas.append(atual)
    return [recuo + li.rstrip() for li in linhas]


def planta(topo, marcadores, estilo, colunas, recuo="  "):
    """Linhas `entradas → [BLOCO m] → saídas`. `marcadores`: {bloco: marcador} (TAG) ou
    ausente (bloco sem dimensionamento)."""
    g, notas = glifos(estilo), _notas()
    sem = estilo.t(carregar("interativo.toml")["pfd"]["marcadores"]["sem_dimensionamento"])
    modelo = linhas_planta(topo)
    larg_ent = max(largura(", ".join(li.entradas)) for li in modelo)
    larg_blk = max(largura(li.bloco) for li in modelo)
    out = []
    for li in modelo:
        marca = marcadores.get(li.bloco, sem)
        caixa = f"[{li.bloco.ljust(larg_blk)} {marca}]"
        saidas = []
        for s, destino, retorno in li.saidas:
            if destino is None:
                saidas.append(f"{s} ({estilo.t(notas['saida'])})")
            elif retorno:
                saidas.append(f"{s} ({estilo.t(notas['retorno'].format(bloco=destino))})")
            else:
                saidas.append(s)
        entradas = ", ".join(li.entradas)
        prefixo = f"{entradas.ljust(larg_ent)}  {g['seta']} {caixa} {g['seta']} "
        cabe_um = largura(recuo + prefixo) + max(largura(x) + 1 for x in saidas) <= colunas
        if cabe_um:
            out += _quebrar_itens(prefixo, saidas, colunas, recuo)
        else:  # muito estreito: o bloco numa linha, origem e destino abaixo
            out.append(recuo + caixa)
            out += _quebrar_itens(f"  {estilo.t(notas['de'])}: ", list(li.entradas), colunas, recuo)
            out += _quebrar_itens(f"  {estilo.t(notas['para'])}: ", saidas, colunas, recuo)
    return out


def local(topo, bloco, marcador, estilo, colunas, recuo="  "):
    """Esquema do bloco com as correntes de entrada à esquerda (e o bloco de onde vêm) e
    as de saída à direita (e o bloco aonde vão), linha a linha."""
    g, notas = glifos(estilo), _notas()
    entradas, saidas = vizinhos(topo, bloco)
    esq = [f"{o if o else estilo.t(notas['entrada'])} {g['traco']} {s} {g['seta_longa']} " for o, s in entradas]
    dir_ = [f" {g['traco']} {s} {g['seta_longa']} {d if d else estilo.t(notas['saida'])}" for s, d in saidas]
    rotulo = f" {bloco}  {marcador} "
    miolo = max(largura(rotulo) + 2, 8)
    larg_esq = max((largura(x) for x in esq), default=0)
    total = largura(recuo) + larg_esq + miolo + 2 + max((largura(x) for x in dir_), default=0)
    if total > colunas:
        out = [recuo + f"[{bloco} {marcador}]"]
        out += _quebrar_itens(f"  {estilo.t(notas['de'])}: ", [f"{o or estilo.t(notas['entrada'])} ({s})"
                                                                for o, s in entradas], colunas, recuo)
        out += _quebrar_itens(f"  {estilo.t(notas['para'])}: ", [f"{d or estilo.t(notas['saida'])} ({s})"
                                                                  for s, d in saidas], colunas, recuo)
        return out
    vazio = " " * larg_esq
    out = [recuo + vazio + g["canto_se"] + g["horizontal"] * miolo + g["canto_sd"]]
    for i in range(max(len(esq), len(dir_), 1)):
        e = esq[i] if i < len(esq) else ""
        folga = miolo - largura(rotulo)
        meio = " " * (folga // 2) + rotulo + " " * (folga - folga // 2) if i == 0 else " " * miolo
        d = dir_[i] if i < len(dir_) else ""
        out.append((recuo + " " * (larg_esq - largura(e)) + e + g["vertical"] + meio + g["vertical"] + d).rstrip())
    out.append(recuo + vazio + g["canto_ie"] + g["horizontal"] * miolo + g["canto_id"])
    return out
