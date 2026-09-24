"""Estado de sessão por TAG e por equipamento avulso (F10c), persistido em `ajustes_pfd.toml`.

Um único estado serve ao TAG isolado, ao PFD e ao modo interativo. Por equipamento:

- modo: automático (balanço + propriedades com fonte) ou manual (não consulta o balanço);
- entradas do usuário, gerais e por caso (caso prevalece sobre geral);
- valores importados de arquivo/exemplo (manual), com a identificação do arquivo;
- atividade por caso (manual) e casos do avulso;
- revisões: confirmação por campo × caso, com valor e fonte confirmados;
- substituídos: origem/fonte/valor que cada entrada do usuário substituiu (auditoria).

Este módulo só modela, valida e converte para a forma canônica (dict ordenado). A escrita
em TOML fica em output/ajustes.py; o esquema está em docs/esquemas/README.md.
"""
import hashlib
import math
from dataclasses import dataclass, field
from importlib.resources import files

from fpso_siz import __version__

ESQUEMA = 2
AUTOMATICO = "automatico"
MANUAL = "manual"
MODOS = (AUTOMATICO, MANUAL)
# arquivos de apresentação: mudar um texto de tela não muda a identidade da configuração
APRESENTACAO = ("interativo.toml",)


def _numero(v, onde):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{onde} = {v!r} não é número finito")
    return float(v)


def valor_entrada(v, onde, faixa=False):
    """float, ou (mín, máx) quando `faixa` é admitida (arquivos de casos com [min, max])."""
    if faixa and isinstance(v, (list, tuple)):
        if len(v) != len(("min", "max")):
            raise ValueError(f"{onde}: faixa deve ter [min, max]")
        lo, hi = sorted(_numero(x, onde) for x in v)
        return (lo, hi)
    return _numero(v, onde)


def _caso_num(n, onde):
    if isinstance(n, int) and not isinstance(n, bool):
        return n
    if not str(n).isdigit():
        raise ValueError(f"{onde}: caso {n!r} não é um número de caso")
    return int(n)


@dataclass
class EstadoTAG:
    """Estado de um TAG da planta (`avulso` = False) ou de um equipamento avulso."""
    id: str
    equipamento: str
    metodo: str
    modo: str = AUTOMATICO
    avulso: bool = False
    arquivo: str = ""                                   # origem dos valores importados
    nomes_casos: list = field(default_factory=list)     # avulso: nomes, na ordem (num = posição)
    geral: dict = field(default_factory=dict)           # chave → valor (usuário, todos os casos)
    por_caso: dict = field(default_factory=dict)        # num → {chave: valor} (usuário)
    importado_geral: dict = field(default_factory=dict)
    importado_caso: dict = field(default_factory=dict)  # num → {chave: valor} (arquivo)
    inativos: dict = field(default_factory=dict)        # num → motivo (manual)
    revisoes: dict = field(default_factory=dict)        # (chave, num) → (valor, fonte)
    substituidos: dict = field(default_factory=dict)    # (chave, num) → (origem, fonte, valor|None)

    def ajustes_do_caso(self, num):
        """Entradas do usuário que valem no caso: gerais sobrepostas pelas do caso."""
        return {**self.geral, **self.por_caso.get(num, {})}

    def importados_do_caso(self, num):
        return {**self.importado_geral, **self.importado_caso.get(num, {})}

    def ajustado(self, chave, num):
        return chave in self.geral or chave in self.por_caso.get(num, {})

    def chaves_ajustadas(self):
        vistas = list(self.geral)
        for d in self.por_caso.values():
            vistas += [k for k in d if k not in vistas]
        return vistas

    # ------------------------------------------------------------------ edição
    def editar(self, chave, valor, casos=None, anteriores=None):
        """Entrada do usuário para todos os casos (`casos` None) ou para os casos dados.
        `anteriores`: {num: (origem, fonte, valor)} do que foi substituído; a primeira
        substituição de cada campo × caso é a que fica registrada (a origem não-usuário)."""
        if casos is None:
            self.geral[chave] = valor
            for d in self.por_caso.values():
                d.pop(chave, None)
        else:
            for n in casos:
                self.por_caso.setdefault(n, {})[chave] = valor
        for n, ant in (anteriores or {}).items():
            if ant[0] != "usuario":
                self.substituidos.setdefault((chave, n), ant)
        self._limpar()

    def restaurar(self, chave, casos=None, todos=()):
        """Remove a entrada do usuário (todos os casos ou só os dados); a regra volta a valer.
        Se a entrada era geral e só alguns casos são restaurados, os demais (`todos`)
        mantêm o valor, agora como entrada daquele caso."""
        if casos is None:
            self.geral.pop(chave, None)
            for d in self.por_caso.values():
                d.pop(chave, None)
            for k in [k for k in self.substituidos if k[0] == chave]:
                del self.substituidos[k]
        else:
            if chave in self.geral:
                v = self.geral.pop(chave)
                for n in todos:
                    if n not in casos:
                        self.por_caso.setdefault(n, {}).setdefault(chave, v)
            for n in casos:
                self.por_caso.get(n, {}).pop(chave, None)
                self.substituidos.pop((chave, n), None)
        self._limpar()

    def confirmar(self, chave, itens):
        """Registra a revisão: itens = {num: (valor, fonte)}."""
        for n, (v, f) in itens.items():
            self.revisoes[(chave, n)] = (v, f)

    def definir_atividade(self, num, motivo=None):
        if motivo is None:
            self.inativos.pop(num, None)
        else:
            self.inativos[num] = motivo

    def restringir(self, nums):
        """Descarta o que se refere a casos fora de `nums` (outro arquivo de casos);
        devolve os casos descartados."""
        nums = set(nums)
        fora = sorted(({*self.por_caso, *self.importado_caso, *self.inativos}
                       | {n for _, n in self.revisoes} | {n for _, n in self.substituidos}) - nums)
        for grupo in (self.por_caso, self.importado_caso, self.inativos):
            for n in fora:
                grupo.pop(n, None)
        self.revisoes = {k: v for k, v in self.revisoes.items() if k[1] in nums}
        self.substituidos = {k: v for k, v in self.substituidos.items() if k[1] in nums}
        return fora

    def para_automatico(self):
        """Troca para o automático: importados, atividade informada e faixas (só do manual)
        saem; devolve as chaves de faixa descartadas."""
        faixas = [k for d in (self.geral, *self.por_caso.values()) for k, v in d.items() if isinstance(v, tuple)]
        for d in (self.geral, *self.por_caso.values()):
            for k in [k for k, v in d.items() if isinstance(v, tuple)]:
                del d[k]
        self.modo, self.arquivo = AUTOMATICO, ""
        self.importado_geral, self.importado_caso, self.inativos = {}, {}, {}
        self._limpar()
        return faixas

    def _limpar(self):
        self.por_caso = {n: d for n, d in self.por_caso.items() if d}


@dataclass
class Ajustes:
    """O estado da sessão: contexto de origem (se lido de arquivo), TAGs e avulsos."""
    contexto: dict = field(default_factory=dict)   # identidade gravada; vazio = legado/novo
    tags: dict = field(default_factory=dict)       # id → EstadoTAG
    avulsos: dict = field(default_factory=dict)    # nome → EstadoTAG
    legado: bool = False

    def estado(self, ident):
        return self.tags.get(ident) or self.avulsos.get(ident)

    def todos(self):
        return [*self.tags.values(), *self.avulsos.values()]


# ------------------------------------------------------------------ identidade do contexto
def identidade_configuracao():
    """SHA-256 dos TOML do modelo (métodos, TAGs, propriedades, premissas…), sem os de
    apresentação: identifica a configuração com que os ajustes foram feitos."""
    raiz = files("fpso_siz.config")
    h = hashlib.sha256()

    def visitar(p, rel):
        for filho in sorted(p.iterdir(), key=lambda x: x.name):
            nome = f"{rel}{filho.name}"
            if filho.is_dir():
                visitar(filho, nome + "/")
            elif filho.name.endswith(".toml") and nome not in APRESENTACAO:
                h.update(nome.encode("utf-8") + b"\0" + filho.read_bytes() + b"\0")
    visitar(raiz, "")
    return h.hexdigest()


def contexto_de(dados, alteracoes, versoes):
    """Identidade do contexto: BOT (nome e hash, casos), premissas alteradas, versões."""
    base = {"esquema": ESQUEMA}
    if dados is not None:
        base.update(casos_arquivo=dados.origem, casos_sha256=dados.sha256,
                    casos=[c["num"] for c in dados.casos])
    base.update(fpso_siz=__version__, configuracao=identidade_configuracao(),
                premissas=dict(sorted(alteracoes.items())), propriedades=dict(sorted(versoes.items())))
    return base


@dataclass(frozen=True)
class Divergencia:
    campo: str
    mensagem: str
    bloqueante: bool
    tag: str = ""


def comparar_contexto(gravado, atual, estados=()):
    """Divergências entre o contexto gravado nos ajustes e o atual. Bloqueantes: hash do
    arquivo de casos, números dos casos, premissas alteradas e método de um TAG. Versões e
    configuração só avisam: os valores são recalculados e revisões desatualizadas voltam a
    pendentes."""
    out = []
    if gravado:
        if "casos_sha256" in gravado and gravado.get("casos_sha256") != atual.get("casos_sha256"):
            out.append(Divergencia("casos_sha256", f"os ajustes foram feitos para {gravado.get('casos_arquivo', '?')} "
                                   f"(sha256 {gravado['casos_sha256']}); o arquivo de casos atual é "
                                   f"{atual.get('casos_arquivo', '?')} (sha256 {atual.get('casos_sha256')})", True))
        if "casos" in gravado and gravado.get("casos") != atual.get("casos"):
            out.append(Divergencia("casos", f"casos dos ajustes {gravado['casos']} ≠ casos atuais {atual.get('casos')}",
                                   True))
        if gravado.get("premissas", {}) != atual.get("premissas", {}):
            out.append(Divergencia("premissas", f"premissas alteradas nos ajustes {gravado.get('premissas', {})} ≠ "
                                   f"premissas da execução {atual.get('premissas', {})}", True))
        for campo in ("fpso_siz", "configuracao", "propriedades"):
            if campo in gravado and gravado[campo] != atual.get(campo):
                out.append(Divergencia(campo, f"{campo} dos ajustes difere da execução atual; os valores são "
                                       "recalculados e revisões com valor/fonte diferentes voltam a pendentes", False))
    for e in estados:
        if not e.avulso:
            from fpso_siz.pfd.tags import tag as catalogo
            t = catalogo(e.id)
            if (e.equipamento, e.metodo) != (t.equipamento, t.metodo):
                out.append(Divergencia("metodo", f"{e.id}: os ajustes usam {e.equipamento}/{e.metodo}; o TAG usa "
                                       f"{t.equipamento}/{t.metodo}", True, e.id))
    return out


# ------------------------------------------------------------------ leitura
def _tabela(d, onde):
    if not isinstance(d, dict):
        raise ValueError(f"{onde}: esperada tabela")
    return d


def _valores(d, onde, faixa):
    return {k: valor_entrada(v, f"{onde}: {k}", faixa) for k, v in _tabela(d, onde).items()}


def _grupos(lista, onde, campos):
    """[[revisao]] / [[substituido]] → {(chave, num): tupla dos campos}."""
    out = {}
    if not isinstance(lista, list):
        raise ValueError(f"{onde}: esperada lista de tabelas")
    for g in lista:
        g = _tabela(g, onde)
        if "chave" not in g or "casos" not in g:
            raise ValueError(f"{onde}: cada item precisa de chave e casos")
        vals = tuple(tuple(g[c]) if isinstance(g.get(c), list) else g.get(c) for c in campos)
        for n in g["casos"]:
            out[(g["chave"], _caso_num(n, onde))] = vals
    return out


def _estado(ident, d, avulso):
    onde = f"ajustes de {ident}"
    d = _tabela(d, onde)
    conhecidos = {"modo", "equipamento", "metodo", "arquivo", "casos", "entradas", "importados", "caso",
                  "revisao", "substituido"}
    extras = sorted(set(d) - conhecidos)
    if extras:
        raise ValueError(f"{onde}: campos desconhecidos {extras}")
    for c in ("equipamento", "metodo"):
        if not isinstance(d.get(c), str):
            raise ValueError(f"{onde}: falta {c!r}")
    modo = d.get("modo", MANUAL if avulso else AUTOMATICO)
    if modo not in MODOS or (avulso and modo != MANUAL):
        raise ValueError(f"{onde}: modo {modo!r} inválido")
    e = EstadoTAG(ident, d["equipamento"], d["metodo"], modo, avulso, str(d.get("arquivo", "")))
    if avulso:
        e.nomes_casos = [str(n) for n in d.get("casos", [])]
        if not e.nomes_casos or len(set(e.nomes_casos)) != len(e.nomes_casos):
            raise ValueError(f"{onde}: 'casos' deve listar nomes únicos")
    faixa = modo == MANUAL
    e.geral = _valores(d.get("entradas", {}), onde, faixa)
    e.importado_geral = _valores(d.get("importados", {}), onde, faixa)
    for n, sub in _tabela(d.get("caso", {}), onde).items():
        num = _caso_num(n, onde)
        sub = _tabela(sub, f"{onde}, caso {n}")
        extras = sorted(set(sub) - {"entradas", "importados", "inativo"})
        if extras:
            raise ValueError(f"{onde}, caso {n}: campos desconhecidos {extras}")
        if sub.get("entradas"):
            e.por_caso[num] = _valores(sub["entradas"], f"{onde}, caso {n}", faixa)
        if sub.get("importados"):
            e.importado_caso[num] = _valores(sub["importados"], f"{onde}, caso {n}", faixa)
        if "inativo" in sub:
            if modo != MANUAL:
                raise ValueError(f"{onde}, caso {n}: atividade só é informada no modo manual")
            e.inativos[num] = str(sub["inativo"])
    e.revisoes = {k: (v[0], v[1]) for k, v in _grupos(d.get("revisao", []), f"{onde}: revisao",
                                                     ("valor", "fonte")).items()}
    e.substituidos = _grupos(d.get("substituido", []), f"{onde}: substituido", ("origem", "fonte", "valor"))
    return e


def estado_legado(t, bruto):
    """Ajustes de um TAG no formato F10b ({chave: valor, 'caso': {n: {chave: valor}}}) →
    EstadoTAG automático, sem revisões. Os valores são conferidos na montagem, contra os
    descritores do método (mesmas mensagens da F10b)."""
    if not isinstance(bruto, dict) or not isinstance(bruto.get("caso", {}), dict):
        raise ValueError(f"ajustes de {t.tag}: esperada tabela, com subtabelas por caso")
    e = EstadoTAG(t.tag, t.equipamento, t.metodo)
    e.geral = {k: v for k, v in bruto.items() if k != "caso"}
    for n, sub in bruto.get("caso", {}).items():
        if not isinstance(sub, dict):
            raise ValueError(f"ajustes de {t.tag}, caso {n}: esperada tabela de entradas")
        if not str(n).isdigit():
            raise ValueError(f"ajustes de {t.tag}: caso {n!r} não existe no arquivo de casos")
        if int(n) in e.por_caso:
            raise ValueError(f"ajustes de {t.tag}: caso {n!r} duplicado")
        e.por_caso[int(n)] = dict(sub)
    return e


def _legado(d):
    """Formato F10b: ["TAG"] com entradas e ["TAG".caso."n"]; vira modo automático sem
    revisões registradas."""
    from fpso_siz.pfd.tags import tags
    conhecidos = {t.tag: t for t in tags()}
    desconhecidos = sorted(set(d) - set(conhecidos))
    if desconhecidos:
        raise ValueError(f"ajustes para TAGs desconhecidos: {desconhecidos}; conhecidos: {sorted(conhecidos)}")
    return Ajustes(tags={i: estado_legado(conhecidos[i], b) for i, b in d.items()}, legado=True)


def ler(d):
    """dict (tomllib) → Ajustes. Aceita o esquema 2 e o legado da F10b."""
    if not isinstance(d, dict):
        raise ValueError("ajustes: esperada tabela por TAG")
    if not ({"contexto", "tag", "avulso"} & set(d)):
        return _legado(d)
    extras = sorted(set(d) - {"contexto", "tag", "avulso"})
    if extras:
        raise ValueError(f"ajustes: seções desconhecidas {extras} (esperadas contexto, tag, avulso)")
    ctx = _tabela(d.get("contexto", {}), "ajustes: contexto")
    if ctx.get("esquema") != ESQUEMA:
        raise ValueError(f"ajustes: esquema {ctx.get('esquema')!r} não suportado (esperado {ESQUEMA})")
    from fpso_siz.pfd.tags import tags
    conhecidos = {t.tag for t in tags()}
    out = Ajustes(contexto=dict(ctx))
    for ident, sub in _tabela(d.get("tag", {}), "ajustes: tag").items():
        if ident not in conhecidos:
            raise ValueError(f"ajustes para TAGs desconhecidos: {[ident]}; conhecidos: {sorted(conhecidos)}")
        out.tags[ident] = _estado(ident, sub, False)
    for ident, sub in _tabela(d.get("avulso", {}), "ajustes: avulso").items():
        if ident in conhecidos:
            raise ValueError(f"avulso {ident!r}: o nome é de um TAG da planta; associe-o ao TAG em vez disso")
        out.avulsos[ident] = _estado(ident, sub, True)
    return out


# ------------------------------------------------------------------ forma canônica
def _ordem(chaves, ordem):
    pos = {k: i for i, k in enumerate(ordem)}
    return sorted(chaves, key=lambda k: (pos.get(k, len(pos)), k))


def _gravavel(v):
    """Número da forma canônica: float (ida e volta exata em repr) ou [mín, máx]."""
    if isinstance(v, (tuple, list)):
        return [float(x) for x in v]
    return v if v is None or isinstance(v, (str, bool)) else float(v)


def _dict_valores(d, ordem):
    return {k: _gravavel(d[k]) for k in _ordem(d, ordem)}


def _agrupar(registros, ordem, campos):
    """{(chave, num): tupla} → [{chave, casos, campos…}], agrupando casos com os mesmos
    campos; ordem: chave (ordem do método), depois primeiro caso."""
    grupos = {}
    for (k, n), vals in registros.items():
        grupos.setdefault((k, vals), []).append(n)
    itens = []
    for (k, vals), nums in grupos.items():
        g = {"chave": k, "casos": sorted(nums)}
        for c, v in zip(campos, vals):
            if v is not None:
                g[c] = _gravavel(v)
        itens.append(g)
    pos = {k: i for i, k in enumerate(ordem)}
    return sorted(itens, key=lambda g: (pos.get(g["chave"], len(pos)), g["chave"], g["casos"][0]))


def canonico_estado(e, ordem=()):
    """Forma canônica (dict ordenado, determinístico) do estado de um TAG/avulso.
    `ordem`: chaves na ordem do método, para que o arquivo leia como o formulário."""
    d = {"modo": e.modo, "equipamento": e.equipamento, "metodo": e.metodo}
    if e.arquivo:
        d["arquivo"] = e.arquivo
    if e.avulso:
        d["casos"] = list(e.nomes_casos)
    if e.geral:
        d["entradas"] = _dict_valores(e.geral, ordem)
    if e.importado_geral:
        d["importados"] = _dict_valores(e.importado_geral, ordem)
    nums = sorted(set(e.por_caso) | set(e.importado_caso) | set(e.inativos))
    if nums:
        d["caso"] = {}
        for n in nums:
            sub = {}
            if n in e.inativos:
                sub["inativo"] = e.inativos[n]
            if e.por_caso.get(n):
                sub["entradas"] = _dict_valores(e.por_caso[n], ordem)
            if e.importado_caso.get(n):
                sub["importados"] = _dict_valores(e.importado_caso[n], ordem)
            d["caso"][str(n)] = sub
    if e.revisoes:
        d["revisao"] = _agrupar(e.revisoes, ordem, ("valor", "fonte"))
    if e.substituidos:
        d["substituido"] = _agrupar(e.substituidos, ordem, ("origem", "fonte", "valor"))
    return d


def canonico(ajustes, contexto, ordens=None):
    """Forma canônica da sessão inteira; `contexto` é a identidade atual (contexto_de)."""
    ordens = ordens or {}
    from fpso_siz.pfd.tags import tags
    catalogo = [t.tag for t in tags()]
    tags_ = {i: canonico_estado(ajustes.tags[i], ordens.get(i, ())) for i in catalogo if i in ajustes.tags}
    avulsos = {i: canonico_estado(ajustes.avulsos[i], ordens.get(i, ())) for i in sorted(ajustes.avulsos)}
    out = {"contexto": contexto}
    if tags_:
        out["tag"] = tags_
    if avulsos:
        out["avulso"] = avulsos
    return out
