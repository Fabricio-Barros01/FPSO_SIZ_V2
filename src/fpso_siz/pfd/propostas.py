"""Valores propostos para as entradas sem fonte (F10x): `pendencias_propostas.toml`.

Uma proposta é um valor inicial que o usuário (autor) escolhe para uma entrada que o
catálogo deixa como LACUNA — sem fonte citável no acervo, no BOT ou numa norma — para que
o fluxo rode. Ela não é dado validado e não se confunde com ele:

- só preenche lacuna (precedência mais baixa: usuário > regra do TAG > recomendada >
  default do método com fonte > PROPOSTA > lacuna); uma chave que tem fonte no catálogo é
  recusada no arquivo;
- entra com a origem própria `proposta` e fica em revisão pendente até o usuário confirmá-la
  (terminal, JSON e MC a mostram separada dos valores com fonte e dos calculados);
- só `status = "proposto"` entra por este mecanismo; o arquivo não pode citar fonte nem
  referência (o campo é `justificativa`, texto do autor).

A validação confere esquema, tipos, unidade (a do descritor), faixa do descritor, limite do
insumo e duplicidade. Arquivo inválido ou ausente é erro de entrada (ValueError), nunca
valor suposto.
"""
import hashlib
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from fpso_siz.pfd.entradas import especificacoes, metodos
from fpso_siz.pfd.tags import tag as tag_por_nome

ESQUEMA = 1
STATUS = "proposto"
ORIGEM = "proposta"
PREFIXO_ORIGEM = "proposta do usuário"
OBRIGATORIOS = ("tag", "chave", "valor", "unidade", "status", "origem", "justificativa")
OPCIONAIS = ("casos",)
PROIBIDOS = ("fonte", "referencia", "referência", "bibliografia", "norma")


@dataclass(frozen=True)
class Proposta:
    tag: str
    chave: str
    valor: float
    unidade: str
    origem: str
    justificativa: str
    casos: tuple = ()        # vazio = todos os casos em que a entrada é lacuna

    def vale_para(self, num):
        return not self.casos or num in self.casos


@dataclass(frozen=True)
class Propostas:
    itens: tuple = ()
    arquivo: str = ""
    sha256: str = ""

    def de(self, tag, chave, num):
        """A proposta para (TAG, chave) no caso `num`, ou None."""
        for p in self.itens:
            if p.tag == tag and p.chave == chave and p.vale_para(num):
                return p
        return None

    def do_tag(self, tag):
        return [p for p in self.itens if p.tag == tag]

    def __bool__(self):
        return bool(self.itens)


NENHUMA = Propostas()


def _erro(arquivo, i, msg):
    onde = f"{arquivo}: " if arquivo else ""
    return ValueError(f"{onde}proposta {i}: {msg}")


def _descritor(t, chave):
    """(unidade, faixa (mín, máx) ou (), limite máximo ou None) da entrada que pode ser
    lacuna no TAG; ValueError se a chave tem valor com fonte no catálogo (não é lacuna)."""
    _, m, specs = especificacoes(t)
    if chave in t.insumos:
        ins = t.insumos[chave]
        if "valor" in ins:
            raise ValueError(f"{t.tag}.{chave} tem valor com fonte no TAG; proposta não se aplica")
        return ins["unidade"], (), ins.get("limite_max")
    if chave not in specs:
        conhecidas = sorted([*specs, *t.insumos])
        raise ValueError(f"{t.tag} não tem a entrada {chave!r}; entradas: {', '.join(conhecidas)}")
    com_fonte = chave in t.entradas or chave in t.recomendadas or chave in metodos().get(m.method_id, {})
    if com_fonte:
        raise ValueError(f"{t.tag}.{chave} tem regra, recomendação ou default com fonte no catálogo; proposta só "
                         "preenche lacuna")
    s = specs[chave]
    return s.unit, (s.min, s.max), None


def ler(dados, arquivo=""):
    """Propostas validadas a partir do dict lido do TOML."""
    if not isinstance(dados, dict):
        raise ValueError(f"{arquivo}: conteúdo inválido")
    if dados.get("esquema") != ESQUEMA:
        raise ValueError(f"{arquivo}: esquema {dados.get('esquema')!r} não suportado (use esquema = {ESQUEMA})")
    lista = dados.get("proposta", [])
    if not isinstance(lista, list) or not lista:
        raise ValueError(f"{arquivo}: nenhuma tabela [[proposta]]")
    itens, vistos = [], {}
    for i, d in enumerate(lista, 1):
        if not isinstance(d, dict):
            raise _erro(arquivo, i, "não é uma tabela")
        faltam = [c for c in OBRIGATORIOS if c not in d]
        if faltam:
            raise _erro(arquivo, i, f"faltam os campos {faltam}")
        proibidos = [c for c in d if c in PROIBIDOS]
        if proibidos:
            raise _erro(arquivo, i, f"campo {proibidos} não é aceito: proposta não cita fonte nem referência "
                                    "(use 'justificativa')")
        extras = sorted(set(d) - set(OBRIGATORIOS) - set(OPCIONAIS))
        if extras:
            raise _erro(arquivo, i, f"campos desconhecidos {extras}")
        if d["status"] != STATUS:
            raise _erro(arquivo, i, f"status {d['status']!r}: só status = {STATUS!r} entra por este mecanismo "
                                    "(valor confirmado vai para os ajustes do usuário)")
        for c in ("tag", "chave", "unidade", "origem", "justificativa"):
            if not isinstance(d[c], str) or not d[c].strip():
                raise _erro(arquivo, i, f"{c} deve ser texto não vazio")
        if not d["origem"].startswith(PREFIXO_ORIGEM):
            raise _erro(arquivo, i, f"origem deve começar por {PREFIXO_ORIGEM!r} (entrada proposta pelo usuário)")
        v = d["valor"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise _erro(arquivo, i, f"valor {v!r} não é número finito")
        casos = d.get("casos", [])
        if not isinstance(casos, list) or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in casos):
            raise _erro(arquivo, i, "casos deve ser lista de números de caso (inteiros ≥ 1)")
        try:
            t = tag_por_nome(d["tag"])
        except KeyError as e:
            raise _erro(arquivo, i, e.args[0]) from None
        try:
            unidade, faixa, limite = _descritor(t, d["chave"])
        except ValueError as e:
            raise _erro(arquivo, i, e) from None
        if d["unidade"] != unidade:
            raise _erro(arquivo, i, f"{t.tag}.{d['chave']}: unidade {d['unidade']!r}, mas o descritor usa {unidade!r}")
        if faixa and not faixa[0] <= v <= faixa[1]:
            raise _erro(arquivo, i, f"{t.tag}.{d['chave']} = {v} fora da faixa do descritor {faixa[0]}–{faixa[1]} "
                                    f"{unidade}")
        if limite is not None and v > limite:
            raise _erro(arquivo, i, f"{t.tag}.{d['chave']} = {v} acima do limite de {limite} {unidade} do TAG")
        alvo = frozenset(casos)            # vazio = todos os casos
        for outro in vistos.get((t.tag, d["chave"]), []):
            if not alvo or not outro or alvo & outro:
                raise _erro(arquivo, i, f"{t.tag}.{d['chave']} proposto mais de uma vez para o mesmo caso")
        vistos.setdefault((t.tag, d["chave"]), []).append(alvo)
        itens.append(Proposta(t.tag, d["chave"], float(v), unidade, d["origem"], d["justificativa"].strip(),
                              tuple(sorted(casos))))
    return Propostas(tuple(itens), arquivo)


def carregar(caminho):
    """Propostas do arquivo; ausente ou inválido é ValueError (nada é suposto)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ValueError(f"arquivo de propostas não encontrado: {caminho}")
    bruto = caminho.read_bytes()
    try:
        dados = tomllib.loads(bruto.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"{caminho.name}: TOML inválido ({e})") from None
    p = ler(dados, caminho.name)
    return Propostas(p.itens, caminho.name, hashlib.sha256(bruto).hexdigest())


def conferir_casos(propostas, nums):
    """Casos citados nas propostas devem existir no arquivo de casos."""
    fora = sorted({n for p in propostas.itens for n in p.casos} - set(nums))
    if fora:
        raise ValueError(f"{propostas.arquivo}: propostas citam casos inexistentes: {fora}")
