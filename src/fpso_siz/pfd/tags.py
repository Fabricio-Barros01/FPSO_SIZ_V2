"""TAGs do PFD (config/pfd/tags/*.toml): qual método dimensiona cada equipamento da planta e
de onde sai cada entrada. Declarativo — a interface itera estes descritores."""
from dataclasses import dataclass, field
from functools import cache

from fpso_siz.core import registro
from fpso_siz.core.configuracao import carregar, listar

PASTA = "pfd/tags"
CAMPOS = ("tag", "nome", "equipamento", "metodo", "bloco")


@dataclass(frozen=True)
class Tag:
    tag: str
    nome: str
    equipamento: str
    metodo: str
    bloco: str
    condicao: str = ""                                # corrente cuja T e P é a condição do vaso
    entradas: dict = field(default_factory=dict)      # chave do método → regra
    recomendadas: dict = field(default_factory=dict)  # chave → {valor, fonte, perguntar}
    insumos: dict = field(default_factory=dict)       # entradas do TAG que não são do método
    inativo_se: dict = field(default_factory=dict)
    servico: dict = field(default_factory=dict)       # unidades físicas; vazio = lacuna declarada

    def resolver(self):
        """(equipamento, método) registrados."""
        import fpso_siz.sizing  # noqa: F401  (registra os métodos)
        return registro.resolver(self.equipamento, self.metodo)


def _tag(nome_arquivo, pasta=PASTA):
    d = carregar(f"{pasta}/{nome_arquivo}")
    faltam = [c for c in CAMPOS if c not in d]
    if faltam:
        raise ValueError(f"{nome_arquivo}: faltam os campos {faltam}")
    return Tag(d["tag"], d["nome"], d["equipamento"], d["metodo"], d["bloco"], d.get("condicao", ""),
               dict(d.get("entradas", {})), dict(d.get("recomendadas", {})), dict(d.get("insumos", {})),
               dict(d.get("inativo_se", {})), dict(d.get("servico", {})))


VARIANTES = "pfd/variantes"


def topologia_alternativa(nome):
    """TAG com outra alocação de correntes (estudo de alarme, F13): mesmo esquema de
    pfd/tags, em pfd/variantes/<nome>.toml. Não entra na planta."""
    return _tag(f"{nome}.toml", VARIANTES)


@cache
def tags():
    """Os TAGs da planta, em ordem de TAG."""
    return tuple(sorted((_tag(n) for n in listar(PASTA)), key=lambda t: t.tag))


def tag(nome):
    for t in tags():
        if t.tag == nome:
            return t
    raise KeyError(f"TAG desconhecido {nome!r}; conhecidos: {', '.join(t.tag for t in tags())}")


def compativeis(equipamento, metodo=None):
    """TAGs da planta dimensionados pelo mesmo equipamento (e método, se dado)."""
    return [t for t in tags() if t.equipamento == equipamento and metodo in (None, t.metodo)]


def avulso(ident, equipamento, metodo):
    """Descritor de um equipamento avulso: sem bloco, correntes, regras nem recomendações.
    Só o catálogo de defaults com fonte do método (metodos.toml) completa as entradas."""
    import fpso_siz.sizing  # noqa: F401  (registra os métodos)
    eq, _ = registro.resolver(equipamento, metodo)
    return Tag(ident, eq.label, equipamento, metodo, "")
