"""F15 — avaliador puro da otimização multiobjetivo (config/pfd/otimizacao.toml).

**Este módulo não importa `pymoo`.** Ele expõe o que o documento 0003 pediu: um avaliador puro

    avaliar(dados, x) → Avaliacao(objetivos, restricoes, estados)

que decodifica o vetor de decisão nas alterações declaradas (premissa do balanço, entrada de um
TAG ou divisão da vazão em trens), roda o balanço e os TAGs pelo **mesmo serviço por TAG** de
sempre, e devolve objetivos e violações. A otimização não fala com o motor: `_otim.py` é a porta
única do algoritmo e consome este avaliador.

Nada aqui nomeia variável, objetivo, TAG, corrente ou grandeza: tudo vem do TOML, com a origem
de cada limite declarada. Inviabilidade continua sendo estado — ela vira **violação** (g > 0),
nunca exceção; lacuna e caso inativo continuam sendo dado, e não violação de projeto.

**Pré-condição do 0003 (nenhum alarme aberto) ainda NÃO está satisfeita**: P-002 e P-003
fecharam com a película do lado tubo nos três regimes (`docs/validacao/24-pelicula-baixo-reynolds.md`);
**só o P-001 segue inviável**. Enquanto ele estiver aberto toda rodada é estudo, e quem gera
relatório tem de dizer isso.

Um TAG **replicado** (`fator_vazao`: a vazão é dividida por N unidades iguais) é dimensionado
como UMA unidade, então o objetivo que soma um derivado extensivo dele soma N vezes o valor
unitário — a multiplicidade sai da própria decodificação, sem o código citar TAG nenhum.
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.ajustes import Ajustes
from fpso_siz.pfd.planta import dimensionar


def cfg():
    return carregar("pfd/otimizacao.toml")


def subproblema(ident):
    """Declaração do subproblema, ou None para o problema completo."""
    if ident is None:
        return None
    s = next((s for s in cfg().get("subproblema", []) if s["id"] == ident), None)
    if s is None:
        conhecidos = [x["id"] for x in cfg().get("subproblema", [])]
        raise ValueError(f"subproblema desconhecido {ident!r}; declarados: {conhecidos}")
    return s


def variaveis(sub=None):
    s = subproblema(sub)
    todas = cfg()["variavel"]
    return todas if s is None else [v for v in todas if v["id"] in s["variaveis"]]


def objetivos(sub=None):
    s = subproblema(sub)
    todos = cfg()["objetivo"]
    return todos if s is None else [o for o in todos if o["id"] in s["objetivos"]]


def tags_restritas(sub=None):
    s = subproblema(sub)
    return list(cfg()["restricoes"]["tags"] if s is None else s["tags"])


@dataclass(frozen=True)
class Avaliacao:
    """Um ponto do espaço de decisão avaliado pelo serviço por TAG."""
    x: tuple                 # vetor de decisão, na ordem de `variaveis()`
    objetivos: dict          # id → valor (NaN se algum TAG que ele soma não está dimensionado)
    restricoes: dict         # id do TAG → violação g (0 = sem violação)
    estados: dict            # id do TAG → status
    convergiu: bool
    sem_dado: frozenset = frozenset()   # TAGs restringidos que aguardam entrada (lacuna)

    @property
    def avaliavel(self):
        """O ponto pôde ser julgado: o balanço convergiu e nenhum TAG restringido ficou
        esperando entrada. Lacuna não é violação de projeto — mas também não é projeto: sem o
        dado não se sabe se o TAG atende, e um ponto assim NÃO pode sair como viável."""
        return self.convergiu and not self.sem_dado

    @property
    def viavel(self):
        return self.avaliavel and all(g <= 0 for g in self.restricoes.values())

    @property
    def situacao(self):
        """Classificação do PONTO, distinta do status de cada TAG (que está em `estados`):
        `nao_convergiu`, `nao_avaliavel` (falta dado), `inviavel` ou `viavel`."""
        if not self.convergiu:
            return "nao_convergiu"
        if self.sem_dado:
            return "nao_avaliavel"
        return "viavel" if self.viavel else "inviavel"

    @property
    def violacao_total(self):
        return sum(max(0.0, g) for g in self.restricoes.values())


def limites(sub=None):
    """([mín], [máx], [é inteiro?]) na ordem das variáveis declaradas."""
    v = variaveis(sub)
    return ([float(d["min"]) for d in v], [float(d["max"]) for d in v],
            [d["tipo"] == "inteiro" for d in v])


def decodificar(x, sub=None):
    """(alterações de premissa, {tag: {chave: valor}}, {tag: (fator, chaves)}) do vetor `x`."""
    prem, geral, trens = {}, {}, {}
    for d, valor in zip(variaveis(sub), x):
        valor = round(float(valor)) if d["tipo"] == "inteiro" else float(valor)
        if d["destino"] == "premissa":
            prem[d["chave"]] = valor
        elif d["destino"] == "tag_geral":
            geral.setdefault(d["tag"], {})[d["chave"]] = float(valor)
        elif d["destino"] == "fator_vazao":
            trens[d["tag"]] = (int(valor), list(d["chaves"]))
        else:
            raise ValueError(f"variável {d['id']!r}: destino desconhecido {d['destino']!r}")
    return prem, geral, trens


def _violacao(rt, neutros):
    """Distância ao admissível do TAG (0 = sem violação). É MEDIDA de violação, não grandeza: a
    fração dos casos ativos sem solução isolada, mais o excesso relativo sobre o teto quando o
    motor publica um. Estado de dado (lacuna, caso inativo) não é violação de projeto."""
    if rt.status in neutros:
        return 0.0
    if rt.status == servico.DIMENSIONADO:
        return 0.0
    r = rt.resultado
    if r is None:
        return 1.0
    ativos = [pc for pc in r.per_case]
    sem = [pc for pc in ativos if not pc.feasible]
    g = (len(sem) + 1) / (len(ativos) + 1) if ativos else 1.0
    xs = [row.x for row in r.rows if math.isfinite(row.x)]
    if math.isfinite(r.ceiling) and r.ceiling > 0 and xs and min(xs) > r.ceiling:
        g += (min(xs) - r.ceiling) / r.ceiling
    return g


def multiplicidade(trens):
    """{tag: N} do que a decodificação replicou. O TAG replicado é dimensionado com a vazão
    dividida por N, isto é, como UMA unidade; quem soma um derivado extensivo dele tem de somar
    N vezes. Vem da declaração (`destino = "fator_vazao"`), não de um TAG citado no código.

    A conta só é honesta se a divisão chegou a TODAS as chaves declaradas — dividir parte delas
    e contar N unidades somaria N vezes um vaso que ainda passa o serviço inteiro em alguma
    corrente. É o que `montar_ajustes` garante: chave que ele não consegue dividir é lacuna ou
    faixa, e um TAG assim não fica `dimensionado`, de modo que `_objetivo` devolve NaN antes de
    multiplicar coisa nenhuma. `tests/pfd/test_otimizacao_trens.py` fixa esse acoplamento."""
    return {ident: fator for ident, (fator, _) in trens.items()}


def _objetivo(o, planta, mult=None):
    mult = mult or {}
    if o["tipo"] == "soma_derivado":
        total = 0.0
        for ident in o["tags"]:
            rt = planta.tag(ident)
            if rt.status != servico.DIMENSIONADO:
                return math.nan
            d, d2 = rt.resultado.derivados, rt.resultado.derivados_v2
            valor = d2.get(o["derivado_v2"]) if "derivado_v2" in o else None
            if valor is None:
                valor = d.get(o["derivado"], math.nan)
            total += int(mult.get(ident, 1)) * float(valor)
        return total
    if o["tipo"] == "carga_balanco":
        cargas = [sum(float(r.duties[c]) for c in o["cargas"]) for r in planta.balanco]
        if o["agregacao"] != "maximo_entre_casos":
            raise ValueError(f"objetivo {o['id']!r}: agregação desconhecida {o['agregacao']!r}")
        return max(cargas) if cargas else math.nan
    raise ValueError(f"objetivo {o['id']!r}: tipo desconhecido {o['tipo']!r}")


def montar_ajustes(ctx, geral, trens):
    """{tag: EstadoTAG} das alterações decodificadas. `geral` edita a entrada do método em todos
    os casos; `trens` divide as chaves declaradas pelo número de unidades iguais — a entrada
    dividida é lida do próprio preparo do TAG, caso a caso, e lacuna ou faixa fica como está.

    Chave que fica como está é, por construção, uma que deixa o TAG **fora** de `dimensionado`
    (lacuna não fica pronta; faixa só existe no modo manual, e a otimização é automática), então
    o objetivo não chega a multiplicá-la — ver `multiplicidade`."""
    ajustes = {}
    for ident, valores in geral.items():
        e = servico.estado_inicial(ident)
        for chave, valor in valores.items():
            e.editar(chave, valor, None, {})
        ajustes[ident] = e
    for ident, (fator, chaves) in trens.items():
        if fator > 1:
            ajustes[ident] = servico.dividir_vazao(ctx, ajustes.get(ident) or servico.estado_inicial(ident),
                                                   chaves, fator)
    return ajustes


def avaliar(dados, x, propostas=None, sub=None):
    """Avaliação de um ponto: balanço com as premissas alteradas, os TAGs pelo serviço, e os
    objetivos e violações declarados. Balanço que não converge volta como não convergido, com
    todas as violações no máximo — nunca exceção."""
    r = cfg()["restricoes"]
    tags = tags_restritas(sub)
    prem, geral, trens = decodificar(x, sub)
    propostas = mod_propostas.padrao() if propostas is None else propostas
    try:
        ctx = servico.Contexto(dados, alteracoes=prem, propostas=propostas)
        ctx.balanco
    except ValueError:
        return Avaliacao(tuple(x), {o["id"]: math.nan for o in objetivos(sub)},
                         {ident: 1.0 for ident in tags}, {ident: "" for ident in tags}, False,
                         frozenset())
    ajustes = montar_ajustes(ctx, geral, trens)
    planta = dimensionar(contexto=ctx, ajustes=Ajustes(tags=ajustes) if ajustes else None)
    estados = {ident: planta.tag(ident).status for ident in tags}
    restricoes = {ident: _violacao(planta.tag(ident), list(r["estados_neutros"])) for ident in tags}
    sem_dado = frozenset(ident for ident in tags
                         if estados[ident] in set(r["estados_sem_dado"]))
    objs = {o["id"]: _objetivo(o, planta, multiplicidade(trens)) for o in objetivos(sub)}
    return Avaliacao(tuple(x), objs, restricoes, estados, True, sem_dado)


# ------------------------------------------------------------------ validação (critério 2 do 0003)
def grade(sub, passos=None):
    """[(x, ...)] da varredura exaustiva do subproblema: produto cartesiano dos pontos de cada
    variável, com o passo declarado (inteira anda de 1 em 1). `passos` sobrescreve os passos
    declarados — os testes usam grade mais grossa, e a ferramenta usa a do TOML."""
    import itertools
    s = subproblema(sub)
    declarados = dict(s.get("grade_passo", {})) if s else {}
    declarados.update(passos or {})
    eixos = []
    for v in variaveis(sub):
        lo, hi = float(v["min"]), float(v["max"])
        if v["tipo"] == "inteiro":
            eixos.append([float(i) for i in range(int(lo), int(hi) + 1)])
            continue
        passo = float(declarados.get(v["id"], hi - lo))
        n = max(1, int(round((hi - lo) / passo)))
        eixos.append([lo + i * (hi - lo) / n for i in range(n + 1)])
    return [tuple(combo) for combo in itertools.product(*eixos)]


def varredura(dados, sub, passos=None, propostas=None):
    """[Avaliacao] de toda a grade do subproblema — a referência exaustiva da validação."""
    return [avaliar(dados, x, propostas, sub) for x in grade(sub, passos)]


def domina(a, b, ids, tol=0.0):
    """`a` domina `b` (minimização em todos os objetivos, com tolerância relativa)."""
    melhor_em_algum = False
    for i in ids:
        va, vb = a[i], b[i]
        if not (math.isfinite(va) and math.isfinite(vb)):
            return False
        folga = tol * max(1.0, abs(vb))
        if va > vb + folga:
            return False
        if va < vb - folga:
            melhor_em_algum = True
    return melhor_em_algum


def nao_dominados(pontos, ids, tol=0.0):
    """Os pontos não dominados de uma lista de dicionários de objetivos."""
    return [p for p in pontos if not any(domina(q, p, ids, tol) for q in pontos if q is not p)]
