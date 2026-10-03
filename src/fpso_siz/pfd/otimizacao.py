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

O P-001 integrado (ADR 0005, notas 45/46) não tem envelope DESIGN: o resultado dele é a
geometria instalada avaliada por rating (`ResultadoTAG.operacao`). Por isso nada aqui lê
`rt.resultado` direto: as áreas vêm de `equipamento.areas_troca` e os derivados de
`equipamento.derivado` — a mesma regra do JSON, do terminal e do memorial. O ponto separa
**violação** de requisito obrigatório (g > 0), **decisão de projeto pendente**, **verificação
incompleta** e **limitação aceita**: só o ponto sem nenhuma das três primeiras é `viavel`.

O **subproblema de pressão** (`pressao`, docs/validacao/42) usa a mesma cadeia: P_D1 e P_D2 são
premissas do balanço; os objetivos (perda de óleo estabilizado, carga de vapor da VRU) e a
restrição de TVP são grandezas do `EstadoProcesso` agregadas como o TOML declara — aritmética
sobre o estado, nenhuma física aqui —, e a relação P_D2 < P_D1 é restrição entre variáveis.

Um TAG **replicado** (`fator_vazao`: a vazão é dividida por N unidades iguais) é dimensionado
como UMA unidade, então o objetivo que soma um derivado extensivo dele soma N vezes o valor
unitário — a multiplicidade sai da própria decodificação, sem o código citar TAG nenhum.
"""
import math
from dataclasses import dataclass, field

from fpso_siz.balanco.dados import premissas
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.ajustes import Ajustes
from fpso_siz.pfd.planta import dimensionar
from fpso_siz.pfd.tags import tag


def cfg():
    return carregar("pfd/otimizacao.toml")


def subproblema(ident):
    """Declaração do subproblema; para o problema completo (None), a declaração `[completo]`."""
    if ident is None:
        return cfg()["completo"]
    s = next((s for s in cfg().get("subproblema", []) if s["id"] == ident), None)
    if s is None:
        conhecidos = [x["id"] for x in cfg().get("subproblema", [])]
        raise ValueError(f"subproblema desconhecido {ident!r}; declarados: {conhecidos}")
    return s


def variaveis(sub=None):
    ids = subproblema(sub)["variaveis"]
    return [v for v in cfg()["variavel"] if v["id"] in ids]


def objetivos(sub=None):
    ids = subproblema(sub)["objetivos"]
    return [o for o in cfg()["objetivo"] if o["id"] in ids]


def tags_restritas(sub=None):
    return list(cfg()["restricoes"]["tags"] if sub is None else subproblema(sub)["tags"])


def restricoes_balanco(sub=None):
    ids = subproblema(sub).get("restricoes_balanco", [])
    return [r for r in cfg().get("restricao_balanco", []) if r["id"] in ids]


def restricoes_variavel(sub=None):
    ids = subproblema(sub).get("restricoes_variavel", [])
    return [r for r in cfg().get("restricao_variavel", []) if r["id"] in ids]


def ids_restricoes(sub=None):
    """Ids das restrições na ordem em que o algoritmo as recebe: os TAGs restringidos, as
    restrições entre variáveis e as do balanço."""
    return (tags_restritas(sub) + [r["id"] for r in restricoes_variavel(sub)]
            + [r["id"] for r in restricoes_balanco(sub)])


@dataclass(frozen=True)
class Avaliacao:
    """Um ponto do espaço de decisão avaliado pelo serviço por TAG."""
    x: tuple                 # vetor de decisão, na ordem de `variaveis()`
    objetivos: dict          # id → valor (NaN se algum TAG que ele soma não está dimensionado)
    restricoes: dict         # id do TAG ou da restrição → violação g (≤ 0 atende; < 0 é folga)
    estados: dict            # id do TAG → status
    convergiu: bool
    sem_dado: frozenset = frozenset()   # TAGs que aguardam entrada ou restrições sem grandeza (lacuna)
    # TAG → critérios. `violados`: requisito obrigatório não atendido de um TAG dimensionado (já
    # contado em `restricoes`); `pendencias`: decisão de projeto não tomada; `incompletas`:
    # verificação sem conclusão; `limitacoes`: premissa aceita que limita o resultado (informativo)
    violados: dict = field(default_factory=dict)
    pendencias: dict = field(default_factory=dict)
    incompletas: dict = field(default_factory=dict)
    limitacoes: dict = field(default_factory=dict)

    @property
    def avaliavel(self):
        """O ponto pôde ser julgado: o balanço convergiu e nenhum TAG restringido ficou
        esperando entrada. Lacuna não é violação de projeto — mas também não é projeto: sem o
        dado não se sabe se o TAG atende, e um ponto assim NÃO pode sair como viável."""
        return self.convergiu and not self.sem_dado

    @property
    def admissivel(self):
        """Avaliável e sem violação de requisito obrigatório — o que o algoritmo enxerga. Pode
        ainda depender de decisão pendente ou de verificação incompleta."""
        return self.avaliavel and all(g <= 0 for g in self.restricoes.values())

    @property
    def viavel(self):
        """Admissível, sem decisão pendente e com as verificações concluídas: o único ponto que
        pode ser apresentado como atendendo aos critérios."""
        return self.admissivel and not self.pendencias and not self.incompletas

    @property
    def situacao(self):
        """Classificação do PONTO, distinta do status de cada TAG (que está em `estados`), na
        ordem de precedência: `nao_convergiu`, `nao_avaliavel` (falta dado), `inviavel`,
        `decisao_pendente`, `verificacao_incompleta` ou `viavel`."""
        if not self.convergiu:
            return "nao_convergiu"
        if self.sem_dado:
            return "nao_avaliavel"
        if not self.admissivel:
            return "inviavel"
        if self.pendencias:
            return "decisao_pendente"
        return "verificacao_incompleta" if self.incompletas else "viavel"

    def motivos(self):
        """[{tipo, id, criterios}] do que impede o ponto de ser `viavel`, na precedência da
        situação — dado estruturado; quem escreve a frase é a saída."""
        out = [] if self.convergiu else [{"tipo": "nao_convergiu", "id": "", "criterios": []}]
        out += [{"tipo": "sem_dado", "id": i, "criterios": []} for i in sorted(self.sem_dado)]
        out += [{"tipo": "violacao", "id": i, "criterios": list(self.violados.get(i, [])) or [self.estados.get(i, "")]}
                for i, g in self.restricoes.items() if g > 0]
        out += [{"tipo": "decisao_pendente", "id": i, "criterios": list(c)} for i, c in self.pendencias.items()]
        out += [{"tipo": "verificacao_incompleta", "id": i, "criterios": list(c)} for i, c in self.incompletas.items()]
        return out

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
        # dimensionado com requisito obrigatório não atendido (o P-001 instalado classifica os
        # dele): um por critério violado. Decisão pendente não é violação (`Avaliacao.pendencias`)
        return float(len(rt.restricoes))
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


def _casos(balanco, classe):
    """Os casos da classe declarada: "avaliaveis" (trem produtivo) ou todos (None)."""
    if classe is None:
        return list(balanco)
    if classe == "avaliaveis":
        return [r for r in balanco if r.avaliavel]
    raise ValueError(f"classe de caso desconhecida {classe!r}")


def limite(r):
    """Valor do limite de uma restrição do balanço, lido do TOML que o declara (uma declaração só)."""
    ref = r["limite"]
    return float(carregar(ref["arquivo"])[ref["secao"]][ref["chave"]])


def restricao_balanco(r, balanco):
    """(g, caso governante) de uma restrição do balanço: g = máx_casos(grandeza)/limite − 1.
    Grandeza ausente (NaN) em algum caso da classe → (NaN, caso): o ponto não é avaliável."""
    valores = [(getattr(e, r["grandeza"]), e.num) for e in _casos(balanco, r.get("casos"))]
    faltando = [num for v, num in valores if not math.isfinite(v)]
    if faltando or not valores:
        return math.nan, (faltando or [None])[0]
    v, num = max(valores)
    return v / limite(r) - 1, num


def _restricao_variavel(r, valores):
    """Violação da relação x_menor < x_maior entre duas variáveis (0 quando atende)."""
    menor, maior = valores[r["menor"]], valores[r["maior"]]
    return 0.0 if menor < maior else 1 + (menor - maior) / maior


def _estados(planta, o):
    """Estados de que o objetivo lê: o balanço preliminar (padrão) ou, com `etapa =
    "apos_rating"`, o estado operacional depois do rating do P-001 — o das utilidades que P-002 e
    P-003 de fato recebem. Declarado no TOML para que o preliminar não seja lido por omissão."""
    etapa = o.get("etapa", "preliminar")
    if etapa == "apos_rating":
        return planta.balanco_operacional
    if etapa != "preliminar":
        raise ValueError(f"objetivo {o['id']!r}: etapa desconhecida {etapa!r}")
    return planta.balanco


def _objetivo(o, planta, mult=None):
    mult = mult or {}
    if o["tipo"] == "soma_derivado":
        return sum(int(mult.get(ident, 1)) * servico.derivado(planta.tag(ident), o["derivado"])
                   for ident in o["tags"])
    if o["tipo"] == "soma_area_troca":
        # `base`: "instalada_m2" (indicador de investimento: inclui a reserva) ou "em_operacao_m2"
        # (a área que troca calor). A multiplicidade própria do TAG já está nas áreas; replicar
        # por `fator_vazao` um TAG que já a tem contaria as unidades duas vezes.
        total = 0.0
        for ident in o["tags"]:
            a = servico.areas_troca(planta.tag(ident))
            if a is None:
                return math.nan
            n = int(mult.get(ident, 1))
            if n > 1 and a["origem"] != "envelope_design":
                raise ValueError(f"objetivo {o['id']!r}: {ident} já tem multiplicidade própria; "
                                 "replicá-lo por fator_vazao contaria as unidades duas vezes")
            total += n * float(a[o["base"]])
        return total
    if o["tipo"] == "razao_componente":
        casos = _casos(planta.balanco, o.get("casos"))
        entra = sum(float(r.streams[o["referencia"]][o["componente"]]) for r in casos)
        if not casos or entra <= 0:
            return math.nan
        razao = sum(float(r.streams[o["corrente"]][o["componente"]]) for r in casos) / entra
        return 1 - razao if o.get("complemento") else razao
    if o["tipo"] == "carga_balanco":
        campo = o.get("campo", "duties")
        cargas = [sum(float(getattr(r, campo)[c]) for c in o["cargas"])
                  for r in _casos(_estados(planta, o), o.get("casos"))]
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
    nan_objs = {o["id"]: math.nan for o in objetivos(sub)}
    # relação entre variáveis violada: o processo não existe no ponto, e ele não é avaliado
    valores = {v["id"]: float(xi) for v, xi in zip(variaveis(sub), x)}
    topo = {rv["id"]: _restricao_variavel(rv, valores) for rv in restricoes_variavel(sub)}
    if any(g > 0 for g in topo.values()):
        zeros = {i: 0.0 for i in ids_restricoes(sub)}
        return Avaliacao(tuple(x), nan_objs, {**zeros, **topo}, {ident: "" for ident in tags}, True)
    propostas = mod_propostas.padrao() if propostas is None else propostas
    try:
        ctx = servico.Contexto(dados, alteracoes=prem, propostas=propostas)
        ctx.balanco
    except ValueError:
        return Avaliacao(tuple(x), nan_objs, {i: 1.0 for i in ids_restricoes(sub)},
                         {ident: "" for ident in tags}, False, frozenset())
    ajustes = montar_ajustes(ctx, geral, trens)
    somente = None
    if sub is not None and subproblema(sub).get("dimensiona_so_tags"):
        somente = set(tags) | {t for o in objetivos(sub) for t in o.get("tags", [])}
    planta = dimensionar(contexto=ctx, ajustes=Ajustes(tags=ajustes) if ajustes else None, somente=somente)
    estados = {ident: planta.tag(ident).status for ident in tags}
    restricoes = {ident: _violacao(planta.tag(ident), list(r["estados_neutros"])) for ident in tags}
    classes = {nome: {ident: list(getattr(planta.tag(ident), nome)) for ident in tags
                      if getattr(planta.tag(ident), nome)}
               for nome in ("restricoes", "decisoes_pendentes", "verificacoes_incompletas", "limitacoes_aceitas")}
    restricoes.update(topo)
    sem_dado = {ident for ident in tags if estados[ident] in set(r["estados_sem_dado"])}
    for rb in restricoes_balanco(sub):
        g, _ = restricao_balanco(rb, planta.balanco)
        if math.isfinite(g):
            restricoes[rb["id"]] = g
        else:
            restricoes[rb["id"]] = 0.0
            sem_dado.add(rb["id"])
    objs = {o["id"]: _objetivo(o, planta, multiplicidade(trens)) for o in objetivos(sub)}
    return Avaliacao(tuple(x), objs, restricoes, estados, True, frozenset(sem_dado),
                     classes["restricoes"], classes["decisoes_pendentes"],
                     classes["verificacoes_incompletas"], classes["limitacoes_aceitas"])


# ------------------------------------------------------------------ validação (critério 2 do 0003)
def grade(sub, passos=None):
    """[(x, ...)] da varredura exaustiva do subproblema: produto cartesiano dos pontos de cada
    variável, com o passo declarado (inteira anda de 1 em 1). `passos` sobrescreve os passos
    declarados — os testes usam grade mais grossa, e a ferramenta usa a do TOML."""
    import itertools
    declarados = dict(subproblema(sub).get("grade_passo", {}))
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


def ponto_referencia(dados, sub=None):
    """O vetor de decisão da configuração atual: premissa no valor de base, um trem, e a
    recomendação com fonte de cada entrada de TAG (o que o `pfd` dimensiona hoje)."""
    base = premissas(dados)
    x = []
    for v in variaveis(sub):
        if v["destino"] == "premissa":
            x.append(float(base[v["chave"]]))
        elif v["destino"] == "fator_vazao":
            x.append(1.0)
        else:
            rec = tag(v["tag"]).recomendadas.get(v["chave"])
            x.append(float(rec["valor"]) if rec else float(v["min"]))
    return tuple(x)


@dataclass(frozen=True)
class Comparacao:
    """Avaliação finita e rastreável de candidatos: o domínio inteiro declarado (a referência
    primeiro), as avaliações feitas na ordem do domínio até o limite, e o que ficou de fora.
    Comparar é só dominância nos objetivos declarados — sem peso, sem somar unidades diferentes."""
    sub: str
    dominio: tuple            # pontos x, a referência primeiro
    avaliacoes: tuple         # Avaliacao, na ordem do domínio (no máximo `limite`)
    limite: int

    @property
    def referencia(self):
        return self.avaliacoes[0] if self.avaliacoes else None

    @property
    def limite_atingido(self):
        return len(self.avaliacoes) < len(self.dominio)

    @property
    def nao_avaliados(self):
        return self.dominio[len(self.avaliacoes):]

    def com_situacao(self, *situacoes):
        return [a for a in self.avaliacoes if a.situacao in situacoes]

    def frente(self):
        """Candidatos ADMISSÍVEIS (sem violação) não dominados nos objetivos do subproblema.
        Admissível com decisão pendente ou verificação incompleta entra condicionado — a
        situação de cada um continua dizendo por que não está aprovado."""
        ids = [o["id"] for o in objetivos(self.sub)]
        adm = [a for a in self.avaliacoes if a.admissivel]
        objs = nao_dominados([a.objetivos for a in adm], ids)
        return [a for a in adm if a.objetivos in objs]


def comparar(dados, sub, limite=None, propostas=None, avaliar_pontos=None):
    """Avalia o domínio declarado do subproblema (`grade`), com a configuração de referência
    primeiro, até `limite` avaliações (padrão: `[subproblema.comparacao] max_avaliacoes`). Termina
    normalmente se nenhum candidato atender: a classificação de cada um é o resultado. Atingido o
    limite, devolve o parcial com os pontos que ficaram sem avaliar. `avaliar_pontos(pontos)` troca
    a avaliação sequencial por outra equivalente (ex.: `_otim.avaliar_pontos`, em processos)."""
    limite = int(subproblema(sub)["comparacao"]["max_avaliacoes"] if limite is None else limite)
    if limite < 1:
        raise ValueError("a comparação exige ao menos uma avaliação (a da referência)")
    ref = ponto_referencia(dados, sub)
    dominio = (ref, *(x for x in grade(sub) if x != ref))
    pontos = list(dominio[:limite])
    avaliacoes = (avaliar_pontos(pontos) if avaliar_pontos is not None
                  else [avaliar(dados, x, propostas, sub) for x in pontos])
    return Comparacao(sub, dominio, tuple(avaliacoes), limite)


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


# ------------------------------------------------------------------ conferência da frente
def vizinhos(pontos, sub):
    """Pares de pontos da grade que diferem em UM passo de UMA variável (os demais iguais)."""
    eixos = [sorted({p[i] for p in pontos}) for i in range(len(variaveis(sub)))]
    posicao = [{v: k for k, v in enumerate(e)} for e in eixos]
    indice = {tuple(pos[v] for pos, v in zip(posicao, p)): p for p in pontos}
    pares = []
    for chave, p in indice.items():
        for i in range(len(chave)):
            outro = chave[:i] + (chave[i] + 1,) + chave[i + 1:]
            if outro in indice:
                pares.append((p, indice[outro]))
    return pares


def resolucao(avaliacoes, sub):
    """{objetivo: ε} — a resolução da grade no espaço dos objetivos: a maior diferença do objetivo
    entre dois pontos VIÁVEIS vizinhos da grade. Abaixo dela a grade não distingue nada, e é com
    ela que a frente do algoritmo (que anda no contínuo) é conferida. Critério da validação, lido
    da própria grade antes de rodar o algoritmo."""
    por_x = {a.x: a for a in avaliacoes if a.viavel}
    ids = [o["id"] for o in objetivos(sub)]
    eps = {i: 0.0 for i in ids}
    for p, q in vizinhos(list(por_x), sub):
        for i in ids:
            eps[i] = max(eps[i], abs(por_x[p].objetivos[i] - por_x[q].objetivos[i]))
    return eps


def cobre(a, b, eps):
    """`a` cobre `b` dentro da resolução: a_i ≤ b_i + ε_i em todo objetivo (indicador ε aditivo)."""
    return all(math.isfinite(a[i]) and a[i] <= b[i] + e for i, e in eps.items())


def conferir_frente(frente, referencia, eps):
    """(pontos da frente do algoritmo que a referência supera por mais que ε em todo objetivo,
    pontos da frente de referência que a do algoritmo não cobre dentro de ε). As duas listas
    vazias = a frente do algoritmo reproduz a de referência na resolução declarada."""
    superados = [p for p in frente if any(all(q[i] < p[i] - e for i, e in eps.items()) for q in referencia)]
    descobertos = [q for q in referencia if not any(cobre(p, q, eps) for p in frente)]
    return superados, descobertos
