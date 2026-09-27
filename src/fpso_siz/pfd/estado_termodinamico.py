"""Fase 3 — serviço termodinâmico ATIVO: o contrato que o processo pode consumir.

    flash_tp(T, P, z, fluido) → EstadoTermodinamico

A F14 (`pfd/termodinamica.py`) é comparativa: mede o quanto o balanço preliminar se afasta de
propriedades de fonte citável, sem mudar nada. Este módulo é diferente — é a camada que o
processo poderá **chamar** para obter o estado de uma corrente.

**Nesta fase o serviço é apenas disponibilizado.** Nada do balanço, do dimensionamento ou dos
relatórios passa por ele: integrar é a Fase 5, e a fração pesada (surrogate n-C40/n-C33) é a
Fase 4. Por isso nenhum número existente muda — há teste de paridade bit a bit.

**A interface não conhece biblioteca nenhuma.** `EstadoTermodinamico` e `Fase` são dados
simples; quem fala com o ChEDL é a porta única `pfd/_chedl.py`, como sempre. Trocar de backend,
ou portar a C/Java, mexe na porta, não aqui nem em quem consome.

**Unidades: SI**, as da porta (`config/pfd/estado_termodinamico.toml` declara). A conversão para
as unidades do projeto (°C, kPa, cP) é de quem consome — hoje `pfd/fluidos.py`.

**Base de composição: declarada por fluido, e não é a mesma para todos.** Hidrocarboneto e água
recebem fração MOLAR; salmoura recebe a fração MÁSSICA de sal. O estado devolvido diz qual base
usou, para que ninguém precise adivinhar.

**Entalpia: a referência é do modelo, e não é comum entre fluidos.** Peng-Robinson conta a
partir do gás ideal a 298,15 K sem entalpia de formação; IAPWS-95 usa o líquido saturado do
ponto triplo. Só diferenças do MESMO fluido têm significado — o estado carrega
`referencia_entalpia` para que isso não se perca.

**Falta de convergência é estado, nunca exceção** (contrato do projeto): o estado volta com
`ok = False` e a mensagem do backend. Entrada inválida — fluido não declarado, T ou P não
positivos, composição que não soma 1 — é `ValueError`, porque é erro de quem chama.
"""
import math
from dataclasses import dataclass, field

from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import _chedl
from fpso_siz.pfd import caracterizacao
from fpso_siz.pfd import fluidos

NAO_APLICAVEL = math.nan   # grandeza que o modelo não fornece (lacuna declarada no TOML)


def cfg():
    return carregar("pfd/estado_termodinamico.toml")


def fluidos_declarados():
    """Ids dos fluidos que o serviço atende, na ordem do TOML."""
    return list(cfg()["fluido"])


def declaracao(fluido):
    """Bloco declarado do fluido, com modelo, base de composição, fases e fonte."""
    d = cfg()["fluido"].get(fluido)
    if d is None:
        raise ValueError(f"fluido não declarado: {fluido!r}; declarados: {fluidos_declarados()}")
    return d


def lacunas(fluido=None):
    """Lacunas declaradas — o que o serviço NÃO entrega, e por quê."""
    todas = cfg().get("lacuna", [])
    return [x for x in todas if fluido is None or x["fluido"] == fluido]


# ------------------------------------------------------------------ contrato
@dataclass(frozen=True)
class Fase:
    """Uma fase do equilíbrio, em SI. NaN = grandeza que o modelo não fornece (ver `lacunas`)."""
    nome: str                # "vapor" | "liquido" | "aquosa"
    fracao_molar: float      # da mistura total
    fracao_massica: float
    composicao: dict         # {componente: fração molar na fase} — y no vapor, x no líquido
    Z: float
    MW: float                # g/mol
    rho: float               # kg/m³
    h: float                 # J/kg (ver `referencia_entalpia` do estado)
    cp: float                # J/(kg·K)
    mu: float                # Pa·s
    k: float                 # W/(m·K)
    metodos: dict = field(default_factory=dict)   # grandeza → método efetivo do backend


@dataclass(frozen=True)
class EstadoTermodinamico:
    """O estado de uma corrente na condição (T, P), como o serviço o entrega."""
    fluido: str
    T: float                 # K
    P: float                 # Pa
    z: dict                  # composição global, na base declarada
    base_composicao: str
    fases: tuple = ()
    modelo: str = ""
    backend: str = ""
    fonte: str = ""
    referencia_entalpia: str = ""
    avisos: tuple = ()
    ok: bool = True
    mensagem: str = ""

    @property
    def fracao_vapor(self):
        """Fração MOLAR de vapor; 0 se o modelo não prevê fase vapor."""
        return sum(f.fracao_molar for f in self.fases if f.nome == "vapor")

    @property
    def fracao_vapor_massica(self):
        return sum(f.fracao_massica for f in self.fases if f.nome == "vapor")

    @property
    def monofasico(self):
        return len(self.fases) == 1

    def fase(self, nome):
        """A fase de nome dado, ou None se o equilíbrio não a prevê nesta condição."""
        return next((f for f in self.fases if f.nome == nome), None)

    @property
    def vapor(self):
        return self.fase("vapor")

    @property
    def liquido(self):
        return self.fase("liquido")

    @property
    def aquosa(self):
        return self.fase("aquosa")

    @property
    def h(self):
        """Entalpia mássica da mistura: média pelas frações MÁSSICAS das fases. NaN se alguma
        fase não tem entalpia (o modelo de Laliberté não dá)."""
        if not self.fases:
            return math.nan
        return sum(f.fracao_massica * f.h for f in self.fases)


# ------------------------------------------------------------------ validação de entrada
def _conferir(T, P, z, d):
    if not (isinstance(T, (int, float)) and math.isfinite(T) and T > 0):
        raise ValueError(f"temperatura inválida: {T!r} (esperado K > 0)")
    if not (isinstance(P, (int, float)) and math.isfinite(P) and P > 0):
        raise ValueError(f"pressão inválida: {P!r} (esperado Pa > 0)")
    if not z:
        raise ValueError("composição vazia")
    for chave, v in z.items():
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
            raise ValueError(f"fração inválida para {chave!r}: {v!r}")
    if d["base_composicao"] == "fracao_molar":
        tol = float(cfg()["servico"]["tolerancia_composicao"])
        soma = sum(z.values())
        if abs(soma - 1.0) > tol:
            # não normalizar em silêncio: normalizar esconde erro de quem chama
            raise ValueError(f"as frações molares somam {soma!r}, e não 1 (tolerância {tol})")


def _falha(fluido, T, P, z, d, mensagem):
    return EstadoTermodinamico(fluido=fluido, T=T, P=P, z=dict(z), base_composicao=d["base_composicao"],
                               modelo=d["modelo"], backend=_backend(), fonte=d["fonte"],
                               referencia_entalpia=d["referencia_entalpia"], ok=False, mensagem=mensagem)


def _backend():
    v = fluidos.versoes()
    return "thermo " + v["thermo"] + " / chemicals " + v["chemicals"]


# ------------------------------------------------------------------ o serviço
def flash_tp(T, P, z, fluido):
    """Estado de equilíbrio de `z` a (T, P). `fluido` é um id declarado no TOML, e é ele que
    escolhe o modelo — nada é inferido da composição.

    `z` é interpretado na base declarada do fluido: fração molar para hidrocarboneto e água,
    fração mássica de sal para salmoura."""
    d = declaracao(fluido)
    _conferir(T, P, z, d)
    modelo = d["modelo"]
    if modelo == "peng_robinson":
        return _hidrocarboneto(T, P, z, d, fluido)
    if modelo == "iapws95":
        return _agua(T, P, z, d, fluido)
    if modelo == "laliberte":
        return _salmoura(T, P, z, d, fluido)
    if modelo == "peng_robinson_pseudo":
        return _fluido_de_poco(T, P, z, d, fluido)
    raise ValueError(f"modelo desconhecido para {fluido!r}: {modelo!r}")


def _hidrocarboneto(T, P, z, d, fluido):
    c = fluidos.cfg()["gas"]
    comp = c["componentes"]
    faltam = sorted(set(z) - set(comp))
    if faltam:
        # caracterização ausente é entrada que falta, não estado inviável
        raise ValueError(f"componentes sem identificador em fluidos.toml [gas.componentes]: {faltam}. "
                         f"A fração pesada (C20+/C20++) é lacuna declarada — ver lacunas('hidrocarboneto')")
    chaves = list(z)
    try:
        r = _chedl.flash_vle([comp[k] for k in chaves], [z[k] for k in chaves], T, P, c["eos"], c["kij"])
    except (ArithmeticError, ValueError) as e:
        return _falha(fluido, T, P, z, d, f"o flash não convergiu a T = {T} K e P = {P} Pa: {e}")
    metodos = r["metodos"]
    fases = []
    for f in r["fases"]:
        vapor = f["nome"] == "vapor"
        fases.append(Fase(nome=f["nome"], fracao_molar=f["fracao_molar"], fracao_massica=f["fracao_massica"],
                          composicao=dict(zip(chaves, f["composicao"])), Z=f["Z"], MW=f["MW"],
                          rho=f["rho"], h=f["h"], cp=f["cp"], mu=f["mu"], k=f["k"],
                          metodos={"mu": metodos["mu_gas" if vapor else "mu_liquido"],
                                   "k": metodos["k_gas" if vapor else "k_liquido"]}))
    avisos = []
    if any(f.nome != "vapor" for f in fases):
        avisos.append(_aviso_k_liquido(metodos["k_liquido"]))
    return EstadoTermodinamico(fluido=fluido, T=T, P=P, z=dict(z), base_composicao=d["base_composicao"],
                               fases=tuple(fases), modelo=d["modelo"], backend=_backend(), fonte=d["fonte"],
                               referencia_entalpia=d["referencia_entalpia"], avisos=tuple(avisos))


def _fluido_de_poco(T, P, z, d, fluido, mws_plus=None):
    """Fluido de poço completo: componentes reais do banco + pseudo-componentes caracterizados
    por Riazi & Al-Sahhaf (1996) (cortes SCN C6–C19 e frações plus C20+/C20++).

    **A composição não é transformada**: cada componente mantém a sua fração molar. O que muda
    é a caracterização. **h e cp não são entregues** — ver `caracterizacao.bloqueios()`."""
    c = fluidos.cfg()["gas"]
    comp = c["componentes"]
    mws_plus = mws_plus if mws_plus is not None else {}
    chaves = list(z)
    reais, pseudos, faltam = [], [], []
    for pos, nome in enumerate(chaves):
        tipo = caracterizacao.classificar(nome, mws_plus or None)
        if tipo == caracterizacao.REAL:
            ident = comp.get(nome, nome)
            reais.append((pos, ident))
            continue
        if tipo == caracterizacao.PLUS and nome not in mws_plus:
            faltam.append(nome)
            continue
        p = caracterizacao.caracterizar(nome, mws_plus.get(nome))
        pseudos.append((pos, p.nome, p.MW, p.Tc, p.Pc, p.omega))
    if faltam:
        raise ValueError(f"fração plus sem MW do BOT: {sorted(faltam)}; informe `mws_plus`")
    try:
        r = _chedl.flash_pseudo(reais, pseudos, [z[k] for k in chaves], T, P, c["kij"])
    except (ArithmeticError, ValueError) as e:
        return _falha(fluido, T, P, z, d, f"o flash não convergiu a T = {T} K e P = {P} Pa: {e}")
    fases = tuple(Fase(nome=f["nome"], fracao_molar=f["fracao_molar"], fracao_massica=f["fracao_massica"],
                       composicao=dict(zip(chaves, f["composicao"])), Z=f["Z"], MW=f["MW"], rho=f["rho"],
                       h=NAO_APLICAVEL, cp=NAO_APLICAVEL, mu=NAO_APLICAVEL, k=NAO_APLICAVEL,
                       metodos={"Tc/Pc/omega dos pseudo": caracterizacao.cfg()["fonte"]["referencia"]})
                 for f in r["fases"])
    avisos = tuple(f"{b['grandeza']}: {b['situacao']}" for b in caracterizacao.bloqueios())
    return EstadoTermodinamico(fluido=fluido, T=T, P=P, z=dict(z), base_composicao=d["base_composicao"],
                               fases=fases, modelo=d["modelo"], backend=_backend(), fonte=d["fonte"],
                               referencia_entalpia=d["referencia_entalpia"], avisos=avisos)


def flash_poco(T, P, z, mws_plus):
    """Atalho do fluido de poço, que precisa dos MW das frações plus (dado do BOT)."""
    d = declaracao("poco")
    _conferir(T, P, z, d)
    return _fluido_de_poco(T, P, z, d, "poco", mws_plus)


def _aviso_k_liquido(metodo):
    """A condutividade da fase líquida é lacuna declarada: o serviço entrega o valor do backend
    com o método na mão, e avisa. Ver `lacunas('hidrocarboneto')`."""
    return (f"condutividade da fase líquida por {metodo}, extrapolada dos ajustes dos componentes "
            "leves: lacuna declarada, a validar antes de ser consumida")


def _agua(T, P, z, d, fluido):
    if len(z) != 1:
        raise ValueError(f"água pura tem um componente só; recebido: {sorted(z)}")
    c = fluidos.cfg()["agua"]
    try:
        e = _chedl.agua_iapws_completa(T, P)
    except (ArithmeticError, ValueError) as err:
        return _falha(fluido, T, P, z, d, f"IAPWS-95 não resolveu a T = {T} K e P = {P} Pa: {err}")
    fase = Fase(nome="liquido", fracao_molar=1.0, fracao_massica=1.0, composicao=dict(z),
                Z=NAO_APLICAVEL, MW=e["MW"], rho=e["rho"], h=e["h"], cp=e["cp"], mu=e["mu"], k=e["k"],
                metodos={"rho": c["fonte_densidade"], "mu": c["fonte_viscosidade"],
                         "k": c["fonte_condutividade"]})
    return EstadoTermodinamico(fluido=fluido, T=T, P=P, z=dict(z), base_composicao=d["base_composicao"],
                               fases=(fase,), modelo=d["modelo"], backend=_backend(), fonte=d["fonte"],
                               referencia_entalpia=d["referencia_entalpia"])


def _salmoura(T, P, z, d, fluido):
    if len(z) != 1:
        raise ValueError(f"a salmoura é declarada por um sal só; recebido: {sorted(z)}")
    c = fluidos.cfg()["salmoura"]
    w = float(next(iter(z.values())))
    try:
        valores, faixas = _chedl.salmoura_laliberte(T, w, c["sal"])
    except (ArithmeticError, ValueError) as err:
        return _falha(fluido, T, P, z, d, f"Laliberté não resolveu a T = {T} K e w = {w}: {err}")
    avisos = tuple(_fora_da_faixa(p, T, w, faixas[p]) for p in sorted(faixas) if _fora_da_faixa(p, T, w, faixas[p]))
    fase = Fase(nome="aquosa", fracao_molar=1.0, fracao_massica=1.0, composicao=dict(z),
                Z=NAO_APLICAVEL, MW=NAO_APLICAVEL, rho=valores["rho"], h=NAO_APLICAVEL,
                cp=valores["cp"], mu=valores["mu"], k=NAO_APLICAVEL,
                metodos={"rho": c["rotulo"], "mu": c["rotulo"], "cp": c["rotulo"],
                         "k": c["rotulo_lacuna_k"]})
    return EstadoTermodinamico(fluido=fluido, T=T, P=P, z=dict(z), base_composicao=d["base_composicao"],
                               fases=(fase,), modelo=d["modelo"], backend=_backend(), fonte=d["fonte"],
                               referencia_entalpia=d["referencia_entalpia"], avisos=avisos)


def _fora_da_faixa(grandeza, T, w, faixa):
    """Condição fora da faixa de validade não bloqueia: vira aviso (a regra de `fluidos.py`).
    A faixa vem do próprio banco de Laliberté, em °C."""
    from fpso_siz.core.unidades import k_para_c

    t_min, t_max, w_max = faixa
    t = k_para_c(T)
    if t < t_min or t > t_max:
        return f"{grandeza}: T = {t:.1f} °C fora da faixa de Laliberté ({t_min:.0f}–{t_max:.0f} °C)"
    if w > w_max:
        return f"{grandeza}: w = {w:.4f} acima do máximo de Laliberté ({w_max:.4f})"
    return ""
