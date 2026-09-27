"""Análise Pinch no contrato de varredura — Kemp, Problem Table (F8).

Port de `src/analysis/pinch_method.jl`. A física está em `analysis/pinch.py`, que é puro e não
conhece contrato nenhum; aqui só se encaixa a rede no motor de envelope.

O eixo varrido é o **ΔTmin** e a exigência é o **QHmin**, que é não-decrescente em ΔTmin — a
condição para o motor tomar o máximo entre casos e chamar o resultado de exigência.

**Este método não dimensiona equipamento.** Não há casco, diâmetro nem comprimento a escolher:
ele cascateia calor pelos intervalos de temperatura e devolve as METAS da rede. Por isso o
rótulo da ação é "Analisar".

**Não há troca energia × capital, logo não há ótimo.** O programa não modela área nem custo,
então não existe a curva de custo total de §3.7 (Fig. 3.25, p. 82) e não há ótimo a procurar: o
`objective` é a distância ao ΔTmin declarado — **seleção por declaração**. `admissible` é
sempre verdadeiro, e isso é uma afirmação, não uma omissão: todo ΔTmin da grade descreve uma
rede possível.
"""
import math

from fpso_siz.analysis import pinch as pa
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.contrato import Equipamento, ResultField, SweepAxis, SweepColumn, der
from fpso_siz.core.formato_julia import jl, jl_round
from fpso_siz.core.grade import faixa_julia
from fpso_siz.core.parametros import group_specs, in_group, instance_key
from fpso_siz.core.trace import Rastro
from fpso_siz.sizing.base import MetodoTOML, driver_case


def _k():
    return carregar("equipment/comum/pinch.toml")


class PinchTarget(Equipamento):
    """A rede de correntes, não um equipamento: é o que a Análise Pinch recebe."""
    method_id, label = "pinch", "Rede térmica de processo"


class PinchConstraints:
    """A rede, já validada, e as duas somas que não dependem de ΔTmin nenhum.

    `q_hot` e `q_cold` existem para a conferência cruzada da p. 24: QCmin − QHmin tem de igualar
    ΣQ_quente − ΣQ_frio, em QUALQUER ΔTmin. É invariante barato que pega erro de dado e erro de
    cascata, e é o que o memorial mostra no fecho.

    `_computed` conserva a tabela e as curvas de cada ΔTmin durante esta execução: exigência,
    derivados, rastro e figuras leem o mesmo cálculo, e uma nova execução cria novas restrições."""

    def __init__(self, streams, q_hot, q_cold, n_hot, n_cold):
        self.streams = streams
        self.q_hot, self.q_cold = q_hot, q_cold
        self.n_hot, self.n_cold = n_hot, n_cold
        self._computed = {}

    def computed(self, dt_min):
        chave = float(dt_min)
        if chave not in self._computed:
            r = pa.problem_table(self.streams, chave)
            self._computed[chave] = (r, pa.composite_curves(self.streams, r))
        return self._computed[chave]

    def tabela(self, dt_min):
        return self.computed(dt_min)[0]


class PinchKemp(MetodoTOML):
    method_id = "pinch_kemp"
    config = "equipment/pinch/kemp.toml"
    rotulo_padrao = "Kemp — Problem Table (alvos de energia)"

    def applies_to(self):
        return PinchTarget()

    def stream_keys(self):
        """A rede não é uma corrente de processo: nenhuma chave do StreamState se aplica. O
        formulário inteiro vem de `parameters`, pelo grupo repetível."""
        return ()

    def global_keys(self):
        """As três da grade de ΔTmin e o alvo — decisão de projeto, não dado de corrente."""
        return ["dt_min_min", "dt_min_max", "dt_min_step", "dt_min_alvo"]

    def parameter_groups(self):
        return group_specs(self.method_config())

    def _grupo(self):
        gs = self.parameter_groups()
        if not gs:
            raise ValueError("kemp.toml não declara nenhum bloco [[group]]")
        return gs[0]

    def _campos(self, g):
        return [s for s in self.parameters() if in_group(s) and s.group == g["key"]]

    # --- fronteira de tradução: o dicionário do caso vira correntes
    def case_input(self, vals):
        """As correntes que o caso descreve, pelas chaves sintetizadas de `instance_key`
        (`corrente_1_t_in`, `corrente_1_t_out`, `corrente_1_mcp`, e assim por diante).

        **Este é o único ponto deste arquivo que levanta**, e é o idioma correto: `case_input` é
        fronteira de tradução, e o motor a envolve convertendo a exceção em inviabilidade com o
        nome do caso.

        O nome da corrente é sintetizado do índice, e não pedido ao usuário: um ParameterSpec
        descreve grandeza numérica, e um campo de texto obrigaria as estruturas, o arquivo de
        casos e a validação a carregar não-números para servir a um rótulo.

        Uma instância PELA METADE é recusada em vez de completada com defaults: uma corrente com
        `t_in` e sem `mcp` é um dado que o usuário começou a escrever, e preenchê-la com o
        default do descritor poria no alvo de energia uma corrente que ninguém informou."""
        g = self._grupo()
        campos = self._campos(g)
        correntes = []
        for i in range(1, int(g["max"]) + 1):
            chaves = [instance_key(g["key"], i, s.key) for s in campos]
            presentes = [c for c in chaves if c in vals]
            if not presentes:
                continue
            if len(presentes) != len(chaves):
                faltam = ", ".join(c for c in chaves if c not in presentes)
                raise ValueError(f"{g['label']} {i} está pela metade: falta {faltam}. Uma corrente incompleta não é "
                                 "completada com valores de fábrica.")
            v = {s.key: float(vals[instance_key(g["key"], i, s.key)]) for s in campos}
            correntes.append(pa.corrente(f"{g['label']} {i}", v["t_in"], v["t_out"], v["mcp"]))
        if not correntes:
            raise ValueError(f"o caso não descreve nenhuma {g['label'].lower()}: não há rede a integrar.")
        return correntes

    # --- restrições: o que não depende do ΔTmin
    def sizing_constraints(self, e, p, k):
        """Valida a rede e soma as cargas. Nada aqui depende do ΔTmin, que é justamente o eixo.
        A validação usa `validate_streams`, que devolve mensagens e não levanta."""
        tr = Rastro()
        queixas = pa.validate_streams(e, p["dt_min_alvo"])
        if queixas:
            return False, " ".join(queixas), tr
        q_hot, q_cold = pa.heat_loads(e)
        quentes = sum(1 for s in e if pa.stream_type(s) == "hot")
        frias = len(e) - quentes
        for s in e:
            seg = s.segments[0]
            tr.trace("correntes", "Tab. 2.2", f"{s.name} ({'quente' if pa.stream_type(s) == 'hot' else 'fria'})",
                     f"{jl(seg.t_in)} → {jl(seg.t_out)} °C, CP = {jl(seg.mcp)} kW/°C", pa.heat_load(s), "kW")
        tr.trace("correntes", "§2.1.4", "ΣQ quente", "soma das cargas que cedem calor", q_hot, "kW")
        tr.trace("correntes", "§2.1.4", "ΣQ frio", "soma das cargas que recebem calor", q_cold, "kW")
        return True, PinchConstraints(e, q_hot, q_cold, quentes, frias), tr

    # --- o contrato do motor
    def sweep_axis(self, p):
        """A grade de ΔTmin; os limites do descritor saem de §3.7.2, p. 82 — a faixa em que Kemp
        declara o custo total dentro de ~10 % do ótimo."""
        return SweepAxis("dt_min", "ΔT mínimo de aproximação", "°C",
                         faixa_julia(p["dt_min_min"], p["dt_min_step"], p["dt_min_max"]))

    def requirement(self, x, c):
        """QHmin — a utilidade quente que a rede exige, no mínimo, com esta aproximação."""
        return c.tabela(x).q_h_min

    def presentation_data(self, x, cons, k, p):
        return cons.computed(x)

    def governing_of(self, x, c):
        """Uma rede tem UMA exigência, e o símbolo existe porque o motor carimba um."""
        return "utilidade_quente"

    def governing_label(self, g):
        return "utilidade quente (QHmin)" if g == "utilidade_quente" else str(g)

    def requirement_spec(self):
        return ("utilidade quente mínima QHmin", "kW")

    def action_label(self):
        return "Analisar"

    def derived(self, x, y, gov, c, k, p):
        """Tudo o que a Problem Table entrega além do QHmin.

        As temperaturas de pinch saem do núcleo como LISTAS (passo 9: "the point(s)…", no
        plural). Um dicionário de números não guarda lista, então a convenção é: reporta-se o
        mais quente (as fronteiras vêm em ordem decrescente, logo é o primeiro) e diz-se quantos
        são em `n_pinch`. Lista vazia vira NaN, e `threshold` diz por quê."""
        r = c.tabela(x)
        primeiro = lambda v: float(v[0]) if v else math.nan
        return {"qhmin": r.q_h_min, "qcmin": r.q_c_min,
                "t_pinch_deslocada": primeiro(r.t_pinch_shifted), "t_pinch_quente": primeiro(r.t_pinch_hot),
                "t_pinch_fria": primeiro(r.t_pinch_cold), "n_pinch": float(len(r.t_pinch_shifted)),
                "threshold": 1.0 if r.threshold else 0.0, "q_hot": c.q_hot, "q_cold": c.q_cold,
                "n_correntes": float(len(c.streams)), "n_quentes": float(c.n_hot), "n_frias": float(c.n_cold),
                "n_intervalos": float(len(r.intervals)),
                # O calor que a rede troca consigo mesma, e o que ele significa em fração da carga
                # quente disponível — o número que o relatório de fato cita.
                "recuperacao": c.q_hot - r.q_c_min,
                "fracao_recuperada": (c.q_hot - r.q_c_min) / c.q_hot if c.q_hot > 0 else math.nan}

    def admissible(self, x, der_, p):
        """Sempre verdadeiro, e é afirmação, não omissão: todo ΔTmin da grade descreve uma rede
        possível. O que separa um do outro é troca energia × capital, que não é modelada."""
        return True

    def objective(self, x, der_, p):
        """Distância ao ΔTmin declarado — seleção por declaração, não otimização."""
        return abs(x - p["dt_min_alvo"])

    def envelope_params(self, params):
        """Uma grade e um alvo para os N cenários: a rede é uma só. A grade é UNIÃO (menor
        mínimo, maior máximo, menor passo) — ampliar onde se procura não perde solução, e não há
        banda a interseccionar porque nenhum ΔTmin é inadmissível. O alvo é a média presa à
        grade: é preferência, não restrição, e nenhum cenário veta o gosto dos outros."""
        lo = min(p["dt_min_min"] for p in params)
        hi = max(p["dt_min_max"] for p in params)
        passo = min(p["dt_min_step"] for p in params)
        alvo = sum(p["dt_min_alvo"] for p in params) / len(params)
        return True, {"dt_min_min": lo, "dt_min_max": hi, "dt_min_step": passo,
                      "dt_min_alvo": min(max(alvo, lo), hi)}

    def selection_message(self, rows, teto, p, mechanism="none"):
        """Só é alcançada com a grade vazia: como nenhum ΔTmin é inadmissível, o conjunto
        admissível só fica vazio quando não há ponto nenhum a admitir."""
        if not rows:
            return (f"A grade de ΔTmin ficou vazia: confira mínimo ({jl(p['dt_min_min'])} °C), máximo "
                    f"({jl(p['dt_min_max'])} °C) e passo ({jl(p['dt_min_step'])} °C).")
        return ("Nenhum ΔTmin da grade foi admitido. Como a Análise Pinch não recusa aproximação nenhuma — todo "
                "ΔTmin descreve uma rede possível —, isto indica grade mal formada e não um limite físico.")

    def grid_hint(self, p):
        return (f"Verifique ΔTmin mínimo ({jl(p['dt_min_min'])} °C), máximo ({jl(p['dt_min_max'])} °C) e passo "
                f"({jl(p['dt_min_step'])} °C).")

    # --- apresentação
    def result_fields(self, r):
        """O cartão. O primeiro campo é o aviso de escopo, e vem daqui e não da interface: a
        regra do projeto é que a interface não escreve texto de domínio, e "isto não dimensiona
        um trocador" é texto de domínio."""
        tem = r.feasible and math.isfinite(r.x)
        n_pinch = der(r, "n_pinch")
        limiar = der(r, "threshold") == 1.0
        # O que o pinch é, e onde ele não está. Um problema-limiar não tem pinch interior, e
        # mostrar um travessão sem dizer isso deixaria o leitor procurando um defeito.
        if not tem:
            pinch_txt = "—"
        elif limiar and not math.isfinite(der(r, "t_pinch_deslocada")):
            pinch_txt = "sem pinch (problema-limiar)"
        elif math.isfinite(n_pinch) and n_pinch > 1:
            pinch_txt = f"{round(n_pinch)} pinches — mostrado o mais quente"
        else:
            pinch_txt = "um pinch"
        residuo = self._residuo_balanco(r)
        return [
            ResultField("O que esta tela entrega",
                        "Metas de energia da rede (QHmin, QCmin) e a temperatura de pinch. NÃO dimensiona "
                        "casco-e-tubos e NÃO sintetiza a rede de trocadores."),
            ResultField("ΔTmin adotado", r.x if tem else math.nan, unit="°C", highlight=True),
            ResultField("Utilidade quente mínima QHmin", r.y if tem else math.nan, unit="kW", digits=1,
                        highlight=True),
            ResultField("Utilidade fria mínima QCmin", der(r, "qcmin"), unit="kW", digits=1, highlight=True),
            ResultField("Calor recuperado na rede", der(r, "recuperacao"), unit="kW", digits=1),
            ResultField("Fração da carga quente recuperada", der(r, "fracao_recuperada"), digits=3),
            ResultField("Situação do pinch", pinch_txt),
            ResultField("T de pinch (deslocada)", der(r, "t_pinch_deslocada"), unit="°C"),
            ResultField("T de pinch, lado quente", der(r, "t_pinch_quente"), unit="°C"),
            ResultField("T de pinch, lado frio", der(r, "t_pinch_fria"), unit="°C"),
            ResultField("Correntes na rede", der(r, "n_correntes"), digits=0),
            ResultField("Quentes / frias",
                        f"{round(der(r, 'n_quentes'))} / {round(der(r, 'n_frias'))}" if tem else "—"),
            ResultField("Intervalos de temperatura", der(r, "n_intervalos"), digits=0),
            ResultField("Carga quente disponível ΣQ", der(r, "q_hot"), unit="kW", digits=1),
            ResultField("Carga fria requerida ΣQ", der(r, "q_cold"), unit="kW", digits=1),
            ResultField("Resíduo do balanço de entalpia", residuo, unit="kW", digits=3,
                        status=self._balanco_fecha(r, tem)),
            ResultField("Cenário governante", driver_case(r) if tem else "—"),
        ]

    def _residuo_balanco(self, r):
        """(QCmin − QHmin) − (ΣQ_quente − ΣQ_frio), que tem de ser NULO em qualquer ΔTmin.

        É a conferência cruzada da p. 24, e é genuína: os dois lados vêm por rotas independentes
        — QHmin e QCmin saem da cascata de calor, e as somas saem de somar as cargas corrente a
        corrente. Um erro de dado, ou um erro na montagem da cascata, quebra a igualdade."""
        if not (r.feasible and math.isfinite(r.x)):
            return math.nan
        return (der(r, "qcmin") - r.y) - (der(r, "q_hot") - der(r, "q_cold"))

    def _balanco_fecha(self, r, tem):
        """O ✓/✗ do resíduo: a tolerância é relativa à escala das cargas da rede, não absoluta."""
        if not tem:
            return "neutro"
        res = self._residuo_balanco(r)
        if not math.isfinite(res):
            return "neutro"
        escala = max(1.0, abs(der(r, "q_hot")) + abs(der(r, "q_cold")))
        return "ok" if abs(res) <= _k()["balanco"]["tol_residuo"] * escala else "erro"

    def sweep_columns(self):
        return [SweepColumn("ΔTmin (°C)", "x", digits=1), SweepColumn("QHmin (kW)", "y", digits=1),
                SweepColumn("QCmin (kW)", "qcmin", digits=1),
                SweepColumn("recuperado (kW)", "recuperacao", digits=1),
                SweepColumn("T pinch (°C)", "t_pinch_deslocada", digits=1)]

    def trace_blocks(self):
        return [("correntes", "Bloco A — as correntes e as cargas (Tabela 2.2, p. 21)"),
                ("selection", "Seleção do ΔTmin")]

    def trace_selection(self, tr, best, p):
        """Carimba no memorial POR QUE este ponto foi escolhido, e a conferência cruzada da
        p. 24: QCmin − QHmin tem de dar ΣQ_quente − ΣQ_frio em qualquer ΔTmin."""
        d = best.derivados
        tr.trace("selection", "§3.7.3", "ΔTmin",
                 f"declarado pelo projetista ({jl(p['dt_min_alvo'])} °C); não há troca energia × capital modelada, "
                 "logo não há ótimo a procurar", best.x, "°C")
        tr.trace("selection", "§3.9.1", "QHmin", "(p. 8) o fluxo mais negativo da cascata, levado a zero no topo",
                 best.y, "kW")
        tr.trace("selection", "§3.9.1", "QCmin", "(p. 9) o que sobra no pé da cascata factível",
                 d.get("qcmin", math.nan), "kW")
        diferenca = d.get("q_hot", math.nan) - d.get("q_cold", math.nan)
        casas = int(_k()["memorial"]["casas_conferencia"])
        tr.trace("selection", "p. 24", "QCmin − QHmin",
                 f"balanço de entalpia: tem de igualar ΣQ_quente − ΣQ_frio (= {jl(jl_round(diferenca, casas))} kW), em "
                 "qualquer ΔTmin", d.get("qcmin", math.nan) - best.y, "kW")
        limiar = d.get("threshold", 0.0) == 1.0 and not math.isfinite(d.get("t_pinch_deslocada", math.nan))
        tr.trace("selection", "§3.9.1", "T de pinch (deslocada)",
                 "problema-limiar (§3.3.2, p. 54): uma das utilidades zerou e não há pinch interior" if limiar
                 else "(p. 9) fronteira em que o fluxo líquido é nulo",
                 d.get("t_pinch_deslocada", math.nan), "°C")
