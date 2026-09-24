"""Entradas dos equipamentos: adaptador automático (F10b) e adaptador manual (F10c).

Para cada TAG (config/pfd/tags/) e cada caso, cada entrada do método de dimensionamento
sai de UMA origem, nesta precedência:

    automático: usuário (caso > geral) > regra do TAG (balanço/propriedades) > recomendada
                do TAG > default do método com fonte (config/pfd/metodos.toml) > LACUNA
    manual:     usuário (caso > geral) > arquivo importado (caso > geral) > recomendada do
                TAG > default do método com fonte > LACUNA

e carrega a origem, a fonte e o estado de revisão (JSON, terminal e MC). O manual não
consulta o balanço nem o ChEDL. As propriedades na condição do equipamento vêm de
pfd/fluidos.py e vão para o rastro do caso (bloco "propriedades"); cada entrada resolvida
vai para o bloco "entradas". Lacuna é NaN e deixa o TAG "aguardando entrada": pela regra
das fontes, nada sem fonte citável é suposto.
"""
import math
from dataclasses import dataclass, field, replace

from fpso_siz.balanco.dados import descritores_premissas, pocos
from fpso_siz.balanco.indicadores import criterios
from fpso_siz.balanco.propriedades import poco_do_fluido
from fpso_siz.core.casos import Case, CaseSet
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.formato_julia import jl
from fpso_siz.core.ieee import div
from fpso_siz.core.trace import Rastro
from fpso_siz.core.unidades import HORAS_POR_DIA, SEGUNDOS_POR_HORA, kj_para_j, kw_para_w, mm_para_m
from fpso_siz.pfd import fluidos
from fpso_siz.pfd.ajustes import MANUAL, estado_legado

BLOCO = "entradas"
LACUNA = "lacuna"
USUARIO = "usuario"
ARQUIVO = "arquivo"
# estados de revisão de um valor (o cálculo não depende deles; só o destaque)
PENDENTE, CONFIRMADA, DESATUALIZADA = "pendente", "confirmada", "desatualizada"
REVISAO_ABERTA = (PENDENTE, DESATUALIZADA)


def cfg():
    return carregar("pfd/pfd.toml")


def metodos():
    return carregar("pfd/metodos.toml")


def rotulo_origem(origem):
    return cfg()["origens"][origem]


@dataclass(frozen=True)
class Valor:
    valor: float
    origem: str            # balanco | propriedade | premissa | recomendada | metodo | usuario | arquivo | lacuna
    fonte: str = ""
    tipo: str = ""         # só para origem "metodo": fonte | escolha | nao_usado | grade
    pendente: tuple = ()   # lacunas de que o valor depende (chaves do método ou insumos do TAG)
    faixa: tuple = ()      # (mín, máx) quando a entrada é uma faixa (arquivo/manual); valor = NaN
    revisao: str = ""      # "" | pendente | confirmada | desatualizada
    anterior: dict = None  # o que a entrada do usuário substituiu: {origem, fonte, valor}

    @property
    def lacuna(self):
        return self.origem == LACUNA

    @property
    def numero(self):
        """O que foi informado/calculado: float, ou a tupla (mín, máx) de uma faixa."""
        return self.faixa if self.faixa else self.valor

    @property
    def requer_revisao(self):
        """Recomendações e defaults com fonte precisam de confirmação explícita; o cálculo
        preliminar pode usá-los, mas eles seguem destacados até lá."""
        return self.origem == "recomendada" or (self.origem == "metodo" and self.tipo in ("fonte", "escolha"))


@dataclass(frozen=True)
class Lacuna:
    chave: str
    rotulo: str
    unidade: str
    faixa: tuple            # (mín, máx) do descritor, ou () para insumo do TAG
    dica: str
    casos: tuple            # números dos casos ativos que dependem dela
    dependentes: tuple = ()  # outras entradas que só se calculam com ela


@dataclass(frozen=True)
class Revisao:
    """Recomendação/default (ou revisão desatualizada) ainda sem confirmação, agrupada
    pelos casos ativos em que tem o mesmo valor e a mesma fonte."""
    chave: str
    valor: object           # float ou (mín, máx)
    fonte: str
    origem: str
    tipo: str
    estado: str             # pendente | desatualizada
    casos: tuple


@dataclass
class CasoTAG:
    num: int
    nome: str
    ativo: bool
    motivo: str             # por que o caso não entra neste TAG
    valores: dict           # chave → Valor
    rastro: Rastro
    avisos: list
    insumos: dict = field(default_factory=dict)


@dataclass
class EntradasTAG:
    tag: object
    equipamento: object
    metodo: object
    specs: dict             # chave → ParameterSpec, na ordem do método
    casos: list
    lacunas: list = field(default_factory=list)
    modo: str = "automatico"
    avulso: bool = False

    @property
    def pronto(self):
        return not self.lacunas

    def case_set(self):
        return CaseSet([Case(c.nome, {k: list(v.faixa) if v.faixa else v.valor for k, v in c.valores.items()},
                             c.ativo) for c in self.casos])

    def caso(self, num):
        return next(c for c in self.casos if c.num == num)

    def revisoes(self):
        """[Revisao] em aberto nos casos ativos, na ordem do método."""
        grupos = {}
        for c in self.casos:
            if not c.ativo:
                continue
            for k, v in c.valores.items():
                if v.revisao in REVISAO_ABERTA:
                    grupos.setdefault((k, v.numero, v.fonte, v.origem, v.tipo, v.revisao), []).append(c.num)
        return [Revisao(k, n, f, o, t, r, tuple(nums)) for (k, n, f, o, t, r), nums in grupos.items()]

    @property
    def preliminar(self):
        """Há recomendação/default sem revisão entre as entradas dos casos ativos."""
        return bool(self.revisoes())

    def avisos(self):
        """[(aviso, [casos])] na ordem em que aparecem."""
        vistos = {}
        for c in self.casos:
            for a in c.avisos:
                vistos.setdefault(a, []).append(c.num)
        return list(vistos.items())


class _Pendente(Exception):
    def __init__(self, chaves):
        super().__init__(", ".join(chaves))
        self.chaves = tuple(chaves)


# ------------------------------------------------------------------ contexto de um caso
class _Caso:
    def __init__(self, tag, metodo, specs, r, dados, prem, ajustes, importados=None, arquivo=""):
        self.tag, self.metodo, self.specs = tag, metodo, specs
        self.r, self.dados, self.prem, self.aj = r, dados, prem, ajustes
        self.manual = importados is not None     # manual: não consulta balanço nem ChEDL
        self.imp, self.arquivo = importados or {}, arquivo
        self.padroes = metodos().get(metodo.method_id, {})
        self.rastro = Rastro()
        self.avisos = []
        self._memo, self._props, self._pilha = {}, {}, []
        self.insumos = {}

    def aviso(self, texto):
        if texto not in self.avisos:
            self.avisos.append(texto)

    def valor(self, chave):
        if chave not in self._memo:
            if chave in self._pilha:
                raise ValueError(f"{self.tag.tag}: dependência circular na entrada {chave!r}")
            self._pilha.append(chave)
            try:
                self._memo[chave] = self._resolver(chave)
            finally:
                self._pilha.pop()
        return self._memo[chave]

    def _resolver(self, chave):
        if chave in self.aj:
            return _informado(self.aj[chave], USUARIO, "ajustes do usuário")
        if self.manual and chave in self.imp:
            return _informado(self.imp[chave], ARQUIVO, self.arquivo)
        regra = None if self.manual else self.tag.entradas.get(chave)
        if regra is None and chave in self.tag.recomendadas:
            rec = self.tag.recomendadas[chave]
            return Valor(float(rec["valor"]), "recomendada", rec["fonte"])
        if regra is None:
            padrao = self.padroes.get(chave)
            if padrao is None:
                return Valor(math.nan, LACUNA, pendente=(chave,))
            if "regra" not in padrao:
                return Valor(self.specs[chave].default, "metodo", padrao["fonte"], padrao["tipo"])
            regra = padrao
        try:
            v = REGRAS[regra["regra"]](self, chave, **{k: v for k, v in regra.items() if k != "regra"})
        except _Pendente as p:
            return Valor(math.nan, LACUNA, pendente=p.chaves)
        except ArithmeticError as erro:
            return Valor(math.nan, LACUNA, f"não foi possível calcular: {erro}", pendente=(chave,))
        if not math.isfinite(v.valor):
            return Valor(math.nan, LACUNA, v.fonte + "; resultado não finito", pendente=(chave,))
        return v

    def num(self, chave):
        """Valor de outra entrada do mesmo caso; lacuna propaga."""
        v = self.valor(chave)
        if v.lacuna:
            raise _Pendente(v.pendente)
        return v.valor

    def insumo(self, chave):
        """(valor, origem) de uma entrada do TAG que não é do método."""
        ins = self.tag.insumos[chave]
        if chave in self.aj:
            v, origem = float(self.aj[chave]), "usuario"
        elif "valor" in ins:
            v, origem = float(ins["valor"]), "recomendada"
        else:
            raise _Pendente((chave,))
        if chave not in self.insumos:
            fonte = ins.get("fonte", "ajustes do usuário")
            self.insumos[chave] = Valor(v, origem, fonte)
            self.rastro.trace(BLOCO, rotulo_origem(origem), chave, fonte, v, ins["unidade"])
        if "limite_max" in ins and v > ins["limite_max"]:
            self.aviso(f"{ins['rotulo']} = {jl(v)} {ins['unidade']} acima do limite de {jl(ins['limite_max'])} "
                       f"{ins['unidade']} ({ins['fonte_limite']})")
        return v, origem

    def anexar(self, rastro, contexto, avisos=()):
        """Copia um rastro de propriedades, identificando a corrente/condição de cada item."""
        for e in rastro:
            self.rastro.trace(e.block, e.eq, f"{e.var} ({contexto})", e.formula, e.value, e.unit)
        for a in avisos:
            self.aviso(f"{contexto}: {a}")

    def temperatura(self, t):
        """T para avaliar propriedades: a da condição do TAG, a de uma corrente ou a média de
        duas (temperatura média de mistura, Saari Eq. 6.21)."""
        t = t or self.tag.condicao
        if isinstance(t, str):
            return self.r.T[t], t
        a, b = t
        return (self.r.T[a] + self.r.T[b]) / 2, f"{a}→{b}"


def _informado(v, origem, fonte):
    if isinstance(v, tuple):
        return Valor(math.nan, origem, fonte, faixa=v)
    return Valor(float(v), origem, fonte)


# ------------------------------------------------------------------ propriedades (memo por caso)
def _oleo(ctx, T, rotulo):
    chave = ("oleo", rotulo)
    if chave not in ctx._props:
        tr = Rastro()
        poco = pocos()[poco_do_fluido(ctx.dados, ctx.r.fluid)]
        o = fluidos.oleo(poco, ctx.r.rho["O"], T, tr)
        ctx.anexar(tr, rotulo)
        ctx._props[chave] = o
    return ctx._props[chave]


def _fracao_sal(ctx, corrente):
    """Fração mássica de NaCl da fase aquosa da corrente: sal de cada água / massa aquosa.
    Sem água na corrente, a da água produzida (propriedade da fase que estaria ali)."""
    s = ctx.r.streams[corrente]
    sal = cfg()["sal"]
    massa = {c: s[c] for c in cfg()["fases"]["agua"]}
    w = {c: fluidos.fracao_sal(ctx.prem[sal[c][0]], ctx.prem[sal[c][1]]) for c in massa}
    total = sum(massa.values())
    if total > 0:
        return sum(massa[c] * w[c] for c in massa) / total
    return w[cfg()["fases"]["agua"][0]]


def _aquosa(ctx, corrente, T, rotulo):
    chave = ("agua", corrente, rotulo)
    if chave not in ctx._props:
        tr = Rastro()
        a = fluidos.salmoura_fracao(T, _fracao_sal(ctx, corrente), tr)
        ctx.anexar(tr, f"{corrente}, {rotulo}" if corrente != rotulo else corrente, a.avisos)
        ctx._props[chave] = a
    return ctx._props[chave]


def _gas(ctx, corrente):
    chave = ("gas", corrente)
    if chave not in ctx._props:
        tr = Rastro()
        g = fluidos.gas(ctx.r.gp["y"], ctx.r.gp["MW"], ctx.r.T[corrente], ctx.r.P[corrente], tr)
        ctx.anexar(tr, corrente, g.avisos)
        ctx._props[chave] = g
    return ctx._props[chave]


def _subfases(fase):
    f = cfg()["fases"][fase]
    return f if all(x in cfg()["fases"] for x in f) else [fase]


def _fase(ctx, corrente, fase, t):
    """{subfase: (massa kg/s, propriedades a T)} das subfases (óleo, aquosa) da fase pedida."""
    T, rotulo = ctx.temperatura(t)
    s = ctx.r.streams[corrente]
    out = {}
    for sub in _subfases(fase):
        massa = sum(s[c] for c in cfg()["fases"][sub])
        props = _oleo(ctx, T, rotulo) if sub == "oleo" else _aquosa(ctx, corrente, T, rotulo)
        out[sub] = (massa, props)
    return out


# ------------------------------------------------------------------ regras
def _balanco(valor, fonte):
    return Valor(valor, "balanco", fonte)


def r_temperatura(ctx, alvo, corrente):
    return _balanco(ctx.r.T[corrente], f"{corrente}: T")


def r_pressao(ctx, alvo, corrente):
    return _balanco(ctx.r.P[corrente], f"{corrente}: P")


def r_vazao_massica(ctx, alvo, corrente):
    return _balanco(sum(ctx.r.streams[corrente].values()), f"{corrente}: ṁ total")


def r_cp_corrente(ctx, alvo, corrente):
    s = ctx.r.streams[corrente]
    return _balanco(kj_para_j(ctx.r.C(s) / sum(s.values())), f"{corrente}: C/ṁ (cp do balanço)")


def r_vazao_gas_padrao(ctx, alvo, corrente):
    """Vazão de gás na condição PADRÃO (Sm³/h): a Eq. 3.8b de Stewart & Arnold usa Qg em
    'MMscfd (scmh)'; T, Z e P da própria equação levam à condição de operação."""
    return _balanco(ctx.r.vol(ctx.r.streams[corrente], "G") / HORAS_POR_DIA,
                    f"{corrente}: gás na condição padrão (S&A Eq. 3.8b: Qg em scm/h)")


def r_vazao_fase(ctx, alvo, corrente, fase, t=None):
    subs = _fase(ctx, corrente, fase, t)
    # Óleo morto: mesma densidade padrão e mesma ordem de operações do oráculo.
    q = (ctx.r.vol(ctx.r.streams[corrente], "O") / HORAS_POR_DIA if fase == "oleo"
         else sum(m / p.rho for m, p in subs.values()) * SEGUNDOS_POR_HORA)
    return Valor(q, "propriedade", f"{corrente}: Σ ṁ/ρ(T) da fase {fase}")


def r_densidade_fase(ctx, alvo, corrente, fase, t=None):
    subs = _fase(ctx, corrente, fase, t)
    massa = sum(m for m, _ in subs.values())
    if len(subs) == 1 or massa == 0:
        rho = next(iter(subs.values()))[1].rho if len(subs) == 1 else math.nan
    else:
        rho = massa / sum(m / p.rho for m, p in subs.values())
    return Valor(rho, "propriedade", f"{corrente}: ρ da fase {fase} (volumes aditivos)")


def r_viscosidade_fase(ctx, alvo, corrente, fase, t=None, continua=None):
    subs = _fase(ctx, corrente, fase, t)
    for sub, (massa, p) in subs.items():
        if sub == "oleo" and (massa > 0 or len(subs) == 1):
            for aviso in p.avisos:
                ctx.aviso(f"{corrente}: {aviso}")
    if len(subs) == 1:
        return Valor(next(iter(subs.values()))[1].mu, "propriedade", f"{corrente}: μ da fase {fase}")
    (sub_c, (m_c, p_c)), = [(k, v) for k, v in subs.items() if k == continua]
    (sub_d, (m_d, p_d)), = [(k, v) for k, v in subs.items() if k != continua]
    v_c, v_d = m_c / p_c.rho, m_d / p_d.rho
    if v_d == 0:
        return Valor(p_c.mu, "propriedade", f"{corrente}: μ da fase contínua ({sub_c}), sem fase dispersa")
    if v_c == 0:
        ctx.aviso(f"{corrente}: fase contínua ({sub_c}) ausente; usada a μ da fase {sub_d}")
        return Valor(p_d.mu, "propriedade", f"{corrente}: μ da fase {sub_d}")
    tr = Rastro()
    mu, avisos = fluidos.emulsao(p_c.mu, p_d.mu, v_d / (v_c + v_d), tr)
    _, rotulo = ctx.temperatura(t)
    ctx.anexar(tr, f"{corrente}, {rotulo}" if corrente != rotulo else corrente, avisos)
    return Valor(mu, "propriedade", f"{corrente}: emulsão, {sub_c} contínuo (Branan eq. 27-4)")


def r_densidade_gas(ctx, alvo, corrente):
    return Valor(_gas(ctx, corrente).rho, "propriedade", f"{corrente}: ρ do gás na condição (EOS)")


def r_viscosidade_gas(ctx, alvo, corrente):
    return Valor(_gas(ctx, corrente).mu, "propriedade", f"{corrente}: μ do gás na condição")


def r_compressibilidade_gas(ctx, alvo, corrente):
    return Valor(_gas(ctx, corrente).Z, "propriedade", f"{corrente}: Z do gás na condição (EOS)")


def r_pressao_vapor_saturado(ctx, alvo, corrente):
    tr = Rastro()
    pv = fluidos.pressao_vapor_saturado(ctx.r.P[corrente], tr)
    ctx.anexar(tr, corrente)
    return Valor(pv, "propriedade", f"{corrente}: líquido no ponto de bolha, Pv = P ({tr.entries[0].eq})")


def r_premissa(ctx, alvo, nome):
    ident = next(d["id"] for d in descritores_premissas(ctx.dados) if d["nome"] == nome)
    return Valor(float(ctx.prem[nome]), "premissa", f"{ident} {nome}")


def r_insumo(ctx, alvo, chave):
    v, origem = ctx.insumo(chave)
    return Valor(v, origem, ctx.tag.insumos[chave]["rotulo"])


def _utilidade(ctx, entrada, saida):
    faltam = [k for k in (entrada, saida) if k not in ctx.aj and "valor" not in ctx.tag.insumos[k]]
    if faltam:
        raise _Pendente(faltam)
    t_in, _ = ctx.insumo(entrada)
    t_out, _ = ctx.insumo(saida)
    chave = ("utilidade", entrada, saida)
    if chave not in ctx._props:
        tr = Rastro()
        ctx._props[chave] = fluidos.agua_saturada((t_in + t_out) / 2, tr)
        ctx.anexar(tr, "utilidade")
    return t_in, t_out, ctx._props[chave]


def r_vazao_utilidade(ctx, alvo, carga, entrada, saida):
    t_in, t_out, a = _utilidade(ctx, entrada, saida)
    delta_processo = ctx.num("t_tubo_out") - ctx.num("t_tubo_in")
    if ctx.r.duties[carga] > 0 and delta_processo * (t_in - t_out) <= 0:
        raise ValueError(f"{ctx.tag.tag}, caso {ctx.r.num}: temperaturas da utilidade incompatíveis "
                         "com o sentido da troca térmica (inclui ΔT nulo)")
    m = div(kw_para_w(ctx.r.duties[carga]), a.cp * abs(t_in - t_out))
    return Valor(m, "propriedade", f"carga {carga} do balanço / (cp·ΔT) da utilidade")


def r_cp_utilidade(ctx, alvo, entrada, saida):
    return Valor(_utilidade(ctx, entrada, saida)[2].cp, "propriedade", "utilidade: cp da água (IAPWS-95)")


def r_viscosidade_utilidade(ctx, alvo, entrada, saida):
    return Valor(_utilidade(ctx, entrada, saida)[2].mu, "propriedade", "utilidade: μ da água (IAPWS 2008)")


def r_condutividade_utilidade(ctx, alvo, entrada, saida):
    return Valor(_utilidade(ctx, entrada, saida)[2].k, "propriedade", "utilidade: k da água (IAPWS 2011)")


def r_grade_descritor(ctx, alvo, limite):
    s = ctx.specs[alvo]
    return Valor(s.min if limite == "min" else s.max, "metodo", "domínio de busca: faixa do descritor do método",
                 "grade")


def r_grade_velocidade(ctx, alvo, limite):
    """Grade de tubos por passe que a banda de velocidade admite: n = ṁ/(ρ·v·A_i), com v_max
    no início e v_min no fim (a velocidade no tubo cai com n)."""
    d_i = mm_para_m(ctx.num("d_externo") - 2 * ctx.num("espessura"))
    area = math.pi * d_i * d_i / 4
    v = ctx.num("v_max") if limite == "min" else ctx.num("v_min")
    n = ctx.num("m_tubo") / (ctx.num("rho_tubo") * v * area)
    n = max(1, math.floor(n)) if limite == "min" else math.ceil(n)
    return Valor(float(n), "metodo", "domínio de busca: banda de velocidade no tubo, n = ṁ/(ρ·v·A_i)", "grade")


REGRAS = {
    "temperatura": r_temperatura, "pressao": r_pressao, "vazao_massica": r_vazao_massica,
    "cp_corrente": r_cp_corrente, "vazao_gas_padrao": r_vazao_gas_padrao, "vazao_fase": r_vazao_fase,
    "densidade_fase": r_densidade_fase, "viscosidade_fase": r_viscosidade_fase,
    "densidade_gas": r_densidade_gas, "viscosidade_gas": r_viscosidade_gas,
    "compressibilidade_gas": r_compressibilidade_gas, "pressao_vapor_saturado": r_pressao_vapor_saturado,
    "premissa": r_premissa, "insumo": r_insumo, "vazao_utilidade": r_vazao_utilidade,
    "cp_utilidade": r_cp_utilidade, "viscosidade_utilidade": r_viscosidade_utilidade,
    "condutividade_utilidade": r_condutividade_utilidade, "grade_descritor": r_grade_descritor,
    "grade_velocidade": r_grade_velocidade,
}


# ------------------------------------------------------------------ montagem de um TAG
def _validar_estado(tag, estado, specs, nums, insumos=True):
    """Entradas do usuário/arquivo conferidas: chave do método (ou insumo do TAG, no
    automático), número finito (ou faixa, no manual) e caso existente."""
    validas = set(specs) | (set(tag.insumos) if insumos else set())
    faixa = estado.modo == MANUAL

    def conferir(d, onde):
        if not isinstance(d, dict):
            raise ValueError(f"ajustes de {tag.tag}{onde}: esperada tabela de entradas")
        for k, v in d.items():
            if k not in validas:
                raise ValueError(f"ajustes de {tag.tag}{onde}: entrada desconhecida {k!r}")
            ok = (faixa and isinstance(v, tuple)) or (
                not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v))
            if not ok:
                raise ValueError(f"ajustes de {tag.tag}{onde}: {k} = {v!r} não é número finito")

    conferir(estado.geral, "")
    conferir(estado.importado_geral, " (importados)")
    for grupo, rotulo in ((estado.por_caso, ""), (estado.importado_caso, " (importados)")):
        for n, d in grupo.items():
            if n not in nums:
                raise ValueError(f"ajustes de {tag.tag}: caso {str(n)!r} não existe no arquivo de casos")
            conferir(d, f", caso {n}{rotulo}")
    for n in [*estado.inativos, *(n for _, n in estado.revisoes), *(n for _, n in estado.substituidos)]:
        if n not in nums:
            raise ValueError(f"ajustes de {tag.tag}: caso {str(n)!r} não existe no arquivo de casos")


def _atividade(tag, ctx, valores, specs):
    crit = criterios()
    if "vazoes_nulas" in tag.inativo_se:
        vazoes = [valores[k].valor * HORAS_POR_DIA for k in tag.inativo_se["vazoes_nulas"]]
        if all(0 <= q < crit["vazao_nula_m3_d"] for q in vazoes):
            return False, "sem vazão em todas as fases neste caso"
    if "vazao_nula" in tag.inativo_se:
        k = tag.inativo_se["vazao_nula"]
        if 0 <= valores[k].valor * HORAS_POR_DIA < crit["vazao_nula_m3_d"]:
            return False, f"sem vazão ({specs[k].label.lower()}) neste caso"
    if "carga_nula" in tag.inativo_se and not ctx.manual:
        c = tag.inativo_se["carga_nula"]
        if not ctx.r.duties[c] >= crit["carga_nula_kW"]:
            return False, f"carga térmica {c} nula neste caso"
    return True, ""


def _avisos_de_faixa(ctx, valores, specs):
    for k, v in valores.items():
        s = specs[k]
        numeros = v.faixa if v.faixa else (v.valor,)
        fora = [x for x in numeros if math.isfinite(x) and not s.min <= x <= s.max]
        if not v.lacuna and fora:
            ctx.aviso(f"{s.label} = {jl(fora[0])} {s.unit} fora da faixa do descritor do método "
                      f"({jl(s.min)}–{jl(s.max)}); origem: {rotulo_origem(v.origem)}")


def _lacunas(tag, metodo, specs, casos):
    dicas = metodos().get(metodo.method_id, {}).get("dicas", {})
    pendentes, dependentes = {}, {}
    for c in casos:
        if c.ativo:
            for k, v in c.valores.items():
                for p in v.pendente:
                    pendentes.setdefault(p, set()).add(c.num)
                    if p != k:
                        dependentes.setdefault(p, []).append(k)
    out = []
    for k in [*specs, *tag.insumos]:
        if k not in pendentes:
            continue
        dep = tuple(d for d in specs if d in dependentes.get(k, ()))
        if k in specs:
            s = specs[k]
            out.append(Lacuna(k, s.label, s.unit, (s.min, s.max), dicas.get(k, ""), tuple(sorted(pendentes[k])), dep))
        else:
            ins = tag.insumos[k]
            out.append(Lacuna(k, ins["rotulo"], ins["unidade"], (), ins.get("dica", ""), tuple(sorted(pendentes[k])),
                              dep))
    return out


def _auditar(valores, estado, num):
    """Estado de revisão e valor substituído de cada entrada do caso."""
    out = {}
    for k, v in valores.items():
        rev = estado.revisoes.get((k, num)) if estado is not None else None
        if rev is not None:
            status = CONFIRMADA if (rev[0] == v.numero and rev[1] == v.fonte) else DESATUALIZADA
        else:
            status = PENDENTE if v.requer_revisao else ""
        ant = estado.substituidos.get((k, num)) if estado is not None and v.origem == USUARIO else None
        anterior = None if ant is None else {"origem": ant[0], "fonte": ant[1] or "", "valor": ant[2]}
        out[k] = replace(v, revisao=status, anterior=anterior)
    return out


def _rastrear(ctx, valores, specs):
    for k, v in valores.items():
        fonte = v.fonte
        if v.anterior is not None:
            fonte += (f"; substitui {rotulo_origem(v.anterior['origem'])}"
                      + (f" ({v.anterior['fonte']})" if v.anterior["fonte"] else "")
                      + (" sem alterar o balanço" if v.anterior["origem"] in ("balanco", "propriedade", "premissa")
                         else ""))
        valor = v.valor if not v.faixa else v.faixa[0]
        ctx.rastro.trace(BLOCO, rotulo_origem(v.origem), k, fonte, valor, specs[k].unit)
        if v.faixa:
            ctx.rastro.trace(BLOCO, rotulo_origem(v.origem), k, fonte + " (máximo da faixa)", v.faixa[1],
                             specs[k].unit)


def conferir_tag(tag, specs):
    """Erros de configuração do TAG: chave que o método não tem, regra desconhecida."""
    for grupo in ("entradas", "recomendadas"):
        desconhecidas = sorted(set(getattr(tag, grupo)) - set(specs))
        if desconhecidas:
            raise ValueError(f"{tag.tag}: [{grupo}] cita entradas que o método não tem: {desconhecidas}")
    fases = cfg()["fases"]
    for k, regra in tag.entradas.items():
        if regra.get("regra") not in REGRAS:
            raise ValueError(f"{tag.tag}: regra desconhecida {regra.get('regra')!r} para {k}")
        if "fase" in regra and regra["fase"] not in fases:
            raise ValueError(f"{tag.tag}: fase desconhecida {regra['fase']!r} para {k}")
        if regra["regra"] == "viscosidade_fase" and len(_subfases(regra["fase"])) > 1 and \
                regra.get("continua") not in _subfases(regra["fase"]):
            raise ValueError(f"{tag.tag}: {k} é emulsão e precisa de 'continua' ({_subfases(regra['fase'])})")


def especificacoes(tag, pfd=True):
    """(equipamento, método, {chave: ParameterSpec}) do TAG; `pfd` aplica as faixas de
    apresentação do PFD (salmoura), que não mudam o método."""
    eq, m = tag.resolver()
    specs = {s.key: s for s in [*m.parameters(), *m.stream_parameters()]}
    if pfd:
        for k, ajuste in cfg().get("faixas", {}).get(m.method_id, {}).items():
            specs[k] = replace(specs[k], max=ajuste["max"], note=specs[k].note + " " + ajuste["fonte"])
    return eq, m, specs


def montar(tag, balanco, dados, prem, ajustes=None, estado=None):
    """Adaptador automático: entradas do TAG nos casos do balanço (`balanco`: ResultadoCaso
    de cada caso). `estado` (EstadoTAG) ou `ajustes` (formato F10b) trazem o que o usuário
    informou e revisou."""
    eq, m, specs = especificacoes(tag)
    conferir_tag(tag, specs)
    if estado is None:
        estado = estado_legado(tag, {} if ajustes is None else ajustes)
    _validar_estado(tag, estado, specs, {r.num for r in balanco})
    casos = []
    for r in balanco:
        ctx = _Caso(tag, m, specs, r, dados, prem, estado.ajustes_do_caso(r.num))
        valores = _auditar({k: ctx.valor(k) for k in specs}, estado, r.num)
        _rastrear(ctx, valores, specs)
        ativo, motivo = _atividade(tag, ctx, valores, specs)
        if ativo:
            _avisos_de_faixa(ctx, valores, specs)
        nome = cfg()["nome_caso"].format(num=r.num, nome=r.caso.get("name", r.fluid))
        casos.append(CasoTAG(r.num, nome, ativo, motivo, valores, ctx.rastro, ctx.avisos if ativo else [], ctx.insumos))
    return EntradasTAG(tag, eq, m, specs, casos, _lacunas(tag, m, specs, casos))


def montar_manual(tag, casos, estado, pfd=True):
    """Adaptador manual: `casos` = [(num, nome)]; valores do usuário e do arquivo importado,
    recomendações do TAG e defaults com fonte; o resto é lacuna. Não consulta o balanço.
    Atividade: a informada pelo usuário e as regras de vazão do TAG sobre os valores
    informados (a de carga térmica depende do balanço e não se aplica)."""
    eq, m, specs = especificacoes(tag, pfd)
    conferir_tag(tag, specs)
    nums = [n for n, _ in casos]
    if len(set(nums)) != len(nums) or len({nome for _, nome in casos}) != len(casos):
        raise ValueError(f"{tag.tag}: casos com número ou nome repetido")
    _validar_estado(tag, estado, specs, set(nums), insumos=False)
    out = []
    for n, nome in casos:
        ctx = _Caso(tag, m, specs, None, None, None, estado.ajustes_do_caso(n), estado.importados_do_caso(n),
                    estado.arquivo)
        valores = _auditar({k: ctx.valor(k) for k in specs}, estado, n)
        _rastrear(ctx, valores, specs)
        if n in estado.inativos:
            ativo, motivo = False, estado.inativos[n]
        else:
            ativo, motivo = _atividade(tag, ctx, valores, specs)
        if ativo:
            _avisos_de_faixa(ctx, valores, specs)
        out.append(CasoTAG(n, nome, ativo, motivo, valores, ctx.rastro, ctx.avisos if ativo else [], {}))
    return EntradasTAG(tag, eq, m, specs, out, _lacunas(tag, m, specs, out), MANUAL, estado.avulso)
