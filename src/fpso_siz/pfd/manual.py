"""Adaptador manual (F10c): arquivo de casos ou exemplo → valores importados de um TAG ou
de um equipamento avulso, com a origem identificada.

Um arquivo com um único [[case]] vale para todos os casos do TAG; com vários, cada caso é
casado pelo NOME com um caso do TAG (ex.: "BOT 01 — Early Life"). Valor não finito (a
lacuna explícita dos rascunhos do Julia) não é importado: o campo continua pendente.
Chave que o método não declara é erro de entrada; nada é completado com os defaults do
descritor — só o catálogo com fonte (pfd/metodos.toml) completa, na montagem.
"""
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from fpso_siz.core.configuracao import exemplos
from fpso_siz.pfd.ajustes import MANUAL, EstadoTAG, valor_entrada

PREFIXO_EXEMPLO = "exemplo:"
METADADOS = ("name", "enabled")


@dataclass
class Importacao:
    origem: str
    rotulo: str
    equipamento: str
    geral: dict = field(default_factory=dict)
    por_caso: dict = field(default_factory=dict)     # num → {chave: valor}
    inativos: dict = field(default_factory=dict)     # num → motivo
    nomes: list = field(default_factory=list)        # nomes dos casos do arquivo, na ordem
    nao_finitos: list = field(default_factory=list)  # (caso, chave) deixados pendentes


def ler_arquivo(caminho):
    """(dict, origem) de um TOML de casos; a origem é o nome do arquivo (sem a pasta)."""
    caminho = Path(caminho)
    return tomllib.loads(caminho.read_text(encoding="utf-8")), caminho.name


def ler_exemplo(nome):
    if nome not in exemplos():
        raise ValueError(f"exemplo desconhecido {nome!r}; embutidos: {', '.join(exemplos())}")
    return exemplos()[nome], PREFIXO_EXEMPLO + nome


def exemplos_de(equipamento):
    return [n for n, c in exemplos().items() if c.get("equipment") == equipamento]


def importar(cfg, origem, equipamento, metodo, specs, casos=None):
    """Valores do arquivo, validados contra os descritores `specs` do método. `casos`:
    [(num, nome)] do TAG, ou None para um avulso (os casos do arquivo viram os dele)."""
    declarado = cfg.get("equipment")
    if declarado not in (None, equipamento):
        raise ValueError(f"{origem} declara equipment = {declarado!r}, não {equipamento!r}")
    if cfg.get("method") not in (None, metodo):
        raise ValueError(f"{origem} declara method = {cfg['method']!r}, não {metodo!r}")
    blocos = cfg.get("case", [])
    if not isinstance(blocos, list) or not blocos:
        raise ValueError(f"{origem}: sem blocos [[case]]")
    imp = Importacao(origem, str(cfg.get("label", origem)), equipamento)
    for i, b in enumerate(blocos, 1):
        if not isinstance(b, dict) or "name" not in b:
            raise ValueError(f"{origem}: bloco [[case]] {i} sem 'name'")
        desconhecidas = sorted(set(b) - set(METADADOS) - set(specs))
        if desconhecidas:
            raise ValueError(f"{origem}, caso {b['name']!r}: entradas que o método não declara {desconhecidas}")
        vals = {}
        for k, v in b.items():
            if k in METADADOS:
                continue
            if isinstance(v, float) and not math.isfinite(v):
                imp.nao_finitos.append((str(b["name"]), k))
                continue
            vals[k] = valor_entrada(v, f"{origem}, caso {b['name']!r}: {k}", faixa=True)
        imp.nomes.append(str(b["name"]))
        imp.por_caso[i] = (vals, b.get("enabled", True) is not False)
    if len(set(imp.nomes)) != len(imp.nomes):
        raise ValueError(f"{origem}: nomes de caso repetidos")
    return _casar(imp, casos)


def _casar(imp, casos):
    bruto, imp.por_caso = imp.por_caso, {}
    motivo = f"desativado em {imp.origem}"
    if casos is None:
        for i, (vals, ativo) in bruto.items():
            imp.por_caso[i] = vals
            if not ativo:
                imp.inativos[i] = motivo
        return imp
    if len(bruto) == 1:
        vals, ativo = bruto[1]
        if not ativo:
            raise ValueError(f"{imp.origem}: o único caso do arquivo está desativado")
        imp.geral = vals
        return imp
    por_nome = {nome: n for n, nome in casos}
    sem_par = [nome for nome in imp.nomes if nome not in por_nome]
    if sem_par:
        raise ValueError(f"{imp.origem}: casos sem correspondente no TAG {sem_par}; com mais de um [[case]], "
                         f"os nomes devem ser os do TAG (ex.: {casos[0][1]!r})")
    for nome, (vals, ativo) in zip(imp.nomes, bruto.values()):
        imp.por_caso[por_nome[nome]] = vals
        if not ativo:
            imp.inativos[por_nome[nome]] = motivo
    return imp


def aplicar(estado, imp):
    """Estado manual com os valores importados; as entradas do usuário continuam valendo
    por cima deles. Atividade e importados anteriores são substituídos pelos do arquivo."""
    estado.modo = MANUAL
    estado.arquivo = imp.origem
    estado.importado_geral = dict(imp.geral)
    estado.importado_caso = {n: dict(v) for n, v in imp.por_caso.items() if v}
    estado.inativos = dict(imp.inativos)
    return estado


def associar(estado, t, casos):
    """Avulso → preenchimento manual do TAG `t` (decisão explícita do usuário). Um caso só
    vale para todos os casos do TAG; vários são casados pelo nome. Cada valor mantém a
    sua origem (usuário ou arquivo), revisões e substituições incluídas."""
    if (estado.equipamento, estado.metodo) != (t.equipamento, t.metodo):
        raise ValueError(f"{estado.id} ({estado.equipamento}/{estado.metodo}) não é compatível com {t.tag}")
    nums = [n for n, _ in casos]
    novo = EstadoTAG(t.tag, t.equipamento, t.metodo, MANUAL, arquivo=estado.arquivo)
    novo.geral, novo.importado_geral = dict(estado.geral), dict(estado.importado_geral)
    if len(estado.nomes_casos) == 1:  # o único caso do avulso vale para todos os casos do TAG
        novo.geral.update(estado.por_caso.get(1, {}))
        novo.importado_geral.update(estado.importado_caso.get(1, {}))
        mapa = {1: nums}
    else:
        por_nome = {nome: n for n, nome in casos}
        sem_par = [x for x in estado.nomes_casos if x not in por_nome]
        if sem_par:
            raise ValueError(f"{estado.id}: casos sem correspondente em {t.tag} {sem_par}")
        mapa = {i: [por_nome[x]] for i, x in enumerate(estado.nomes_casos, 1)}
        for i, (n,) in mapa.items():
            if estado.por_caso.get(i):
                novo.por_caso[n] = dict(estado.por_caso[i])
            if estado.importado_caso.get(i):
                novo.importado_caso[n] = dict(estado.importado_caso[i])
            if i in estado.inativos:
                novo.inativos[n] = estado.inativos[i]
    for alvo, origem in ((novo.revisoes, estado.revisoes), (novo.substituidos, estado.substituidos)):
        for (k, i), v in origem.items():
            for n in mapa.get(i, ()):
                alvo[(k, n)] = v
    return novo


def avulso(nome, equipamento, metodo, imp=None, nomes=None):
    """Estado de um equipamento avulso: casos do arquivo importado ou os nomes dados."""
    e = EstadoTAG(nome, equipamento, metodo, MANUAL, avulso=True)
    if imp is not None:
        e.nomes_casos = list(imp.nomes)
        aplicar(e, imp)
    else:
        e.nomes_casos = list(nomes or [])
    if not e.nomes_casos or len(set(e.nomes_casos)) != len(e.nomes_casos):
        raise ValueError(f"avulso {nome!r}: informe nomes de caso únicos")
    return e
