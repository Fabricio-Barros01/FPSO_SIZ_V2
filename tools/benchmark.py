"""F-perf — baseline de desempenho medido (docs/validacao/performance-baseline.md).

Mede o estado ATUAL, já com as correções da Fase 1. **Não otimiza nada**: o objetivo é saber
onde o tempo está antes de mexer em qualquer coisa, e o relatório separa o que foi medido do
que é candidato a otimização.

Três cuidados que o relatório depende:

- **inicialização não é regime.** Importar `thermo` e montar as constantes do gás custa uma vez
  por processo; os TOML ficam em `functools.cache`. Cada medida diz se é a primeira chamada
  (fria) ou a de regime (quente).
- **a máquina é registrada, não assumida.** O benchmark anota os recursos VISÍVEIS ao processo
  (afinidade, não `cpu_count`) e a memória; nenhuma conclusão do relatório pode depender deste
  laptop, que entra como máquina de referência.
- **o paralelismo é só medido.** Esta fase varre número de workers e registra vazão, speedup,
  eficiência e memória. Autotuning, cache e variáveis mistas são fases seguintes.

    uv run python tools/benchmark.py --etapas camadas,perfil --dados a.json [--rotulo camadas]
    uv run python tools/benchmark.py --merge a.json b.json c.json \
                                     --dados docs/validacao/performance-baseline.json

A ferramenta emite **JSON**; `docs/validacao/performance-baseline.md` é escrito a partir dele e
não é gerado automaticamente — a leitura dos números é análise, não formatação.
"""
import argparse
import cProfile
import io
import json
import os
import platform
import pstats
import subprocess
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
SUB_PEQUENO = "sg_001"
# Folga de RAM que a varredura de workers NÃO consome: abaixo disto a máquina vai a swap e a
# medida deixa de medir o programa. Valor deste benchmark, não premissa do projeto.
MARGEM_RAM_GIB = 0.8


# ----------------------------------------------------------------------------- máquina
def _meminfo():
    try:
        linhas = Path("/proc/meminfo").read_text().splitlines()
    except OSError:
        return {}
    out = {}
    for linha in linhas:
        chave, _, resto = linha.partition(":")
        partes = resto.split()
        if partes and partes[0].isdigit():
            out[chave] = int(partes[0]) / 1024 / 1024   # kB → GiB
    return out


def _nucleos_fisicos():
    """Núcleos físicos pelo /proc/cpuinfo (pares (physical id, core id) distintos). None quando
    o arquivo não existe — o relatório então só fala de CPUs lógicas."""
    try:
        texto = Path("/proc/cpuinfo").read_text()
    except OSError:
        return None
    pares, atual = set(), {}
    for linha in texto.splitlines():
        chave, _, valor = linha.partition(":")
        chave, valor = chave.strip(), valor.strip()
        if chave in ("physical id", "core id"):
            atual[chave] = valor
        elif not linha.strip() and len(atual) == 2:
            pares.add((atual["physical id"], atual["core id"]))
            atual = {}
    if len(atual) == 2:
        pares.add((atual["physical id"], atual["core id"]))
    return len(pares) or None


def recursos():
    """O que o processo REALMENTE enxerga. `sched_getaffinity` é o número que vale sob cpuset,
    container ou `taskset`; `cpu_count` é o da máquina e pode estar acima do permitido."""
    mem = _meminfo()
    disponiveis = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    return {"plataforma": platform.platform(), "processador": platform.processor() or "—",
            "python": platform.python_version(),
            "cpus_logicas": os.cpu_count(), "cpus_na_afinidade": disponiveis,
            "nucleos_fisicos": _nucleos_fisicos(),
            "ram_total_gib": mem.get("MemTotal"), "ram_disponivel_gib": mem.get("MemAvailable"),
            "swap_total_gib": mem.get("SwapTotal")}


# ----------------------------------------------------------------------------- cronômetro
def medir(fn, repeticoes=3):
    """{frio, quente_min, quente_media, n} de `fn`. A primeira chamada entra separada: é ela
    que paga import, cache de TOML e constantes do ChEDL."""
    t = time.perf_counter()
    fn()
    frio = time.perf_counter() - t
    quentes = []
    for _ in range(max(0, repeticoes - 1)):
        t = time.perf_counter()
        fn()
        quentes.append(time.perf_counter() - t)
    return {"frio_s": frio, "quente_min_s": min(quentes) if quentes else None,
            "quente_media_s": (sum(quentes) / len(quentes)) if quentes else None,
            "repeticoes_quentes": len(quentes)}


def custo_de_importacao():
    """Import medido em processo NOVO, que é a única forma honesta: no processo atual o módulo
    já está em `sys.modules`. É o custo que cada worker do pool paga ao nascer."""
    alvos = {"fpso_siz": "import fpso_siz",
             "fpso_siz.pfd.planta": "import fpso_siz.pfd.planta",
             "fpso_siz.pfd.otimizacao": "import fpso_siz.pfd.otimizacao",
             "thermo+chemicals (porta _chedl)": "from fpso_siz.pfd import _chedl; _chedl.versoes()",
             "pymoo (porta _otim)": "from fpso_siz import _otim; _otim.versao()"}
    out = {}
    for nome, codigo in alvos.items():
        prog = f"import time;t=time.perf_counter();{codigo};print(time.perf_counter()-t)"
        r = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, cwd=RAIZ)
        out[nome] = float(r.stdout.strip()) if r.returncode == 0 else None
    return out


def todos_os_toml():
    """Nomes de todos os TOML do pacote, relativos a `fpso_siz/config/` — é o acervo que um
    processo novo lê ao longo de um trabalho completo."""
    from importlib.resources import files
    raiz = Path(str(files("fpso_siz.config")))
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*.toml"))


# ----------------------------------------------------------------------------- camadas
def camadas(dados):
    from fpso_siz.balanco.dados import premissas
    from fpso_siz.balanco.modelo import resolver_caso, resolver_todos
    from fpso_siz.core.configuracao import carregar
    from fpso_siz.pfd import equipamento as servico
    from fpso_siz.pfd import fluidos
    from fpso_siz.pfd import otimizacao as ot
    from fpso_siz.pfd import propostas as mp
    from fpso_siz.pfd.planta import dimensionar
    from fpso_siz.pfd.tags import tags

    prem = premissas(dados)
    out = {"importacao_s": custo_de_importacao()}

    # --- configuração (functools.cache): o custo é da PRIMEIRA leitura de cada arquivo. Mede-se
    # o acervo inteiro, porque é isso que um processo novo paga ao começar a trabalhar.
    nomes = todos_os_toml()

    def ler_tudo():
        for nome in nomes:
            carregar(nome)

    carregar.cache_clear()
    out["config_toml"] = medir(ler_tudo, repeticoes=3)
    out["config_toml"]["arquivos"] = len(nomes)

    # --- balanço
    out["resolver_caso"] = medir(lambda: resolver_caso(dados.casos[0], dados, prem), repeticoes=5)
    out["resolver_caso_por_caso_s"] = {}
    for c in dados.casos:
        t = time.perf_counter()
        resolver_caso(c, dados, prem)
        out["resolver_caso_por_caso_s"][str(c["num"])] = time.perf_counter() - t
    out["resolver_todos"] = medir(lambda: resolver_todos(dados, prem), repeticoes=3)
    out["n_casos"] = len(dados.casos)

    # --- termodinâmica em uso hoje (as portas que o PFD chama)
    fluidos.versoes()   # paga o import do thermo antes de cronometrar o regime
    r0 = resolver_todos(dados, prem)[0]
    T = float(r0.T[next(iter(r0.T))])
    P = float(r0.P[next(iter(r0.P))])
    out["termodinamica"] = {
        "condicao": {"T_C": T, "P_kPa": P},
        "fluidos.agua": medir(lambda: fluidos.agua(T, P), repeticoes=20),
        "fluidos.agua_saturada": medir(lambda: fluidos.agua_saturada(T), repeticoes=20),
        "fluidos.salmoura_fracao": medir(lambda: fluidos.salmoura_fracao(T, 0.035), repeticoes=20),
    }

    # --- TAG a TAG, com um contexto quente (o balanço já resolvido)
    ctx = servico.Contexto(dados, propostas=mp.padrao())
    ctx.balanco
    por_tag = {}
    for t in tags():
        e = servico.estado_inicial(t.tag)
        t0 = time.perf_counter()
        entradas = servico.preparar(ctx, e)
        t1 = time.perf_counter()
        rt = servico.dimensionar(entradas, e)
        t2 = time.perf_counter()
        por_tag[t.tag] = {"preparar_s": t1 - t0, "dimensionar_s": t2 - t1, "total_s": t2 - t0,
                          "status": rt.status}
    out["por_tag"] = por_tag

    # --- planta inteira, do zero (contexto novo: paga o balanço)
    def planta_do_zero():
        c = servico.Contexto(dados, propostas=mp.padrao())
        return dimensionar(contexto=c)
    out["planta_completa"] = medir(planta_do_zero, repeticoes=2)

    # --- avaliar(dados, x): total e decomposto nas mesmas etapas que ele executa
    x = ponto_do_projeto(dados, None)
    out["avaliar_total"] = medir(lambda: ot.avaliar(dados, x), repeticoes=2)
    out["avaliar_decomposto_s"] = decompor_avaliar(dados, x, None)
    xs = ponto_do_projeto(dados, SUB_PEQUENO)
    out["avaliar_total_sub"] = medir(lambda: ot.avaliar(dados, xs, sub=SUB_PEQUENO), repeticoes=2)
    out["avaliar_decomposto_sub_s"] = decompor_avaliar(dados, xs, SUB_PEQUENO)
    out["populacao"] = custo_de_populacao(out["avaliar_total"]["quente_min_s"])
    return out


def ponto_do_projeto(dados, sub):
    """O mesmo vetor que `tools/otimizar.py` chama de ponto do projeto atual."""
    from fpso_siz.balanco.dados import premissas
    from fpso_siz.pfd import otimizacao as ot
    from fpso_siz.pfd.tags import tag
    base = premissas(dados)
    x = []
    for v in ot.variaveis(sub):
        if v["destino"] == "premissa":
            x.append(float(base[v["chave"]]))
        elif v["destino"] == "fator_vazao":
            x.append(1.0)
        else:
            rec = tag(v["tag"]).recomendadas.get(v["chave"])
            x.append(float(rec["valor"]) if rec else float(v["min"]))
    return tuple(x)


def decompor_avaliar(dados, x, sub):
    """As etapas de `otimizacao.avaliar`, cronometradas uma a uma e comparadas com o total. O
    que sobra é o overhead da própria otimização (decodificar, violações, objetivos)."""
    from fpso_siz.pfd import equipamento as servico
    from fpso_siz.pfd import otimizacao as ot
    from fpso_siz.pfd import propostas as mp
    from fpso_siz.pfd.ajustes import Ajustes
    from fpso_siz.pfd.planta import dimensionar

    t0 = time.perf_counter()
    prem, geral, trens = ot.decodificar(x, sub)
    propostas = mp.padrao()
    t1 = time.perf_counter()
    ctx = servico.Contexto(dados, alteracoes=prem, propostas=propostas)
    ctx.balanco
    t2 = time.perf_counter()
    ajustes = ot.montar_ajustes(ctx, geral, trens)
    t3 = time.perf_counter()
    planta = dimensionar(contexto=ctx, ajustes=Ajustes(tags=ajustes) if ajustes else None)
    t4 = time.perf_counter()
    tags = ot.tags_restritas(sub)
    r = ot.cfg()["restricoes"]
    {ident: planta.tag(ident).status for ident in tags}
    {ident: ot._violacao(planta.tag(ident), list(r["estados_neutros"])) for ident in tags}
    {o["id"]: ot._objetivo(o, planta, ot.multiplicidade(trens)) for o in ot.objetivos(sub)}
    t5 = time.perf_counter()
    return {"decodificar_e_propostas_s": t1 - t0, "contexto_e_balanco_s": t2 - t1,
            "montar_ajustes_s": t3 - t2, "dimensionar_planta_s": t4 - t3,
            "estados_violacoes_objetivos_s": t5 - t4, "soma_das_etapas_s": t5 - t0}


def custo_de_populacao(segundos_por_avaliacao):
    """Projeção do custo de uma geração e de uma rodada com os parâmetros DECLARADOS no TOML.
    É projeção, e o relatório diz isso: rodar a F15 completa é a Fase 13."""
    from fpso_siz.pfd import otimizacao as ot
    k = ot.cfg()["algoritmo"]
    pop, ger = int(k["populacao"]), int(k["geracoes"])
    if segundos_por_avaliacao is None:
        return {"populacao": pop, "geracoes": ger}
    return {"populacao": pop, "geracoes": ger, "s_por_avaliacao": segundos_por_avaliacao,
            "geracao_sequencial_s": pop * segundos_por_avaliacao,
            "rodada_sequencial_s": pop * ger * segundos_por_avaliacao,
            "avaliacoes_da_rodada": pop * ger}


# ----------------------------------------------------------------------------- perfil
def perfil(dados, topo=25):
    """cProfile de UMA avaliação completa. Responde "onde está o tempo" por medição, e não por
    hipótese — é a razão de esta etapa existir antes de qualquer otimização."""
    from fpso_siz.pfd import otimizacao as ot
    x = ponto_do_projeto(dados, None)
    ot.avaliar(dados, x)            # aquece: import do thermo, TOML, constantes do gás
    pr = cProfile.Profile()
    pr.enable()
    ot.avaliar(dados, x)
    pr.disable()
    out = {}
    for ordem in ("cumulative", "tottime"):
        buf = io.StringIO()
        pstats.Stats(pr, stream=buf).sort_stats(ordem).print_stats(topo)
        out[ordem] = buf.getvalue()
    st = pstats.Stats(pr)
    out["total_s"] = st.total_tt
    out["chamadas"] = st.total_calls
    return out


# ----------------------------------------------------------------------------- workers
def _memoria_descendentes_gib():
    """Memória deste processo e de todos os seus descendentes, pelo /proc.

    Usa **PSS** (`smaps_rollup`), não a soma de `VmRSS`. Os filhos do `forkserver` nascem de um
    servidor comum e compartilham páginas copy-on-write (código, TOML já lidos, tabelas do
    thermo); somar RSS contaria cada página compartilhada uma vez por worker e inflaria o custo
    por worker. O PSS divide a página compartilhada entre quem a usa, que é o que se quer para
    dizer quanta memória UM worker acrescenta. Cai para `VmRSS` onde o `smaps_rollup` não
    existe, e o resultado diz qual das duas foi usada."""
    try:
        pids = [int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit()]
    except OSError:
        return None
    filhos, meu = {}, os.getpid()
    for pid in pids:
        try:
            st = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
            filhos.setdefault(int(st[1]), []).append(pid)
        except (OSError, IndexError, ValueError):
            continue
    fila, total, metrica = [meu], 0.0, "pss"
    while fila:
        pid = fila.pop()
        fila.extend(filhos.get(pid, []))
        valor = None
        try:
            for linha in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
                if linha.startswith("Pss:"):
                    valor = int(linha.split()[1]) / 1024 / 1024
                    break
        except OSError:
            valor = None
        if valor is None:
            metrica = "rss"
            try:
                for linha in Path(f"/proc/{pid}/status").read_text().splitlines():
                    if linha.startswith("VmRSS:"):
                        valor = int(linha.split()[1]) / 1024 / 1024
                        break
            except OSError:
                continue
        total += valor or 0.0
    return total, metrica


class Amostrador(threading.Thread):
    """Amostra a RSS da árvore de processos durante a medida, para registrar o pico."""

    def __init__(self, intervalo=2.0):
        # 2 s: ler /proc segura a GIL por alguns milissegundos, e em W = 1 o trabalho roda no
        # PRÓPRIO processo. A 2 s o amostrador custa menos de 0,1 % da medida mais longa.
        super().__init__(daemon=True)
        self.intervalo, self.pico, self.metrica = intervalo, 0.0, None
        self._parar = threading.Event()

    def run(self):
        while not self._parar.is_set():
            v, metrica = _memoria_descendentes_gib()
            if v:
                self.pico, self.metrica = max(self.pico, v), metrica
            self._parar.wait(self.intervalo)

    def parar(self):
        self._parar.set()
        self.join(timeout=self.intervalo * 4)
        return self.pico, self.metrica


def candidatos_de_workers(maximo):
    """1, 2, … até o máximo visível, sem repetir. Varredura só MEDE: escolher automaticamente é
    a fase seguinte, e nenhum número de núcleos está fixado aqui."""
    n = max(1, int(maximo))
    base = sorted({*range(1, min(n, 6) + 1), n, max(1, n // 2), max(1, n // 4), max(1, (n * 3) // 4)})
    return [w for w in base if 1 <= w <= n]


def workers(dados, n_pontos=None, lista=None):
    """Varredura de paralelismo sobre um LOTE FIXO de pontos: todo W faz exatamente o mesmo
    trabalho, então vazão, speedup e eficiência são comparáveis entre si."""
    from fpso_siz import _otim
    from fpso_siz.pfd import otimizacao as ot

    visiveis = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    cands = [w for w in lista if 1 <= w <= visiveis] if lista else candidatos_de_workers(visiveis)
    lote = ot.grade(SUB_PEQUENO, {"eta_F": 0.025})
    tamanho = n_pontos or max(cands)
    lote = [lote[i % len(lote)] for i in range(tamanho)]

    # Aquece o processo PAI antes da varredura. Sem isto, W = 1 (que roda no pai) pagaria o
    # import do thermo e as constantes do gás dentro da própria medida, e o speedup sairia
    # inflado. Os filhos continuam nascendo frios: esse custo é real e o relatório o separa.
    t = time.perf_counter()
    _otim.avaliar_pontos(dados, lote[:1], sub=SUB_PEQUENO)
    aquecimento = time.perf_counter() - t

    # Freio de memória: cada worker carrega um modelo de planta. Medido o custo por worker, um W
    # cuja projeção não cabe na memória DISPONÍVEL não é medido — levar a máquina a swap
    # falsearia a medida e castigaria o usuário. O ponto não medido entra no relatório como tal.
    margem = float(MARGEM_RAM_GIB)
    base_mem, metrica = _memoria_descendentes_gib()
    base_mem = base_mem or 0.0
    por_worker = None

    linhas = []
    tempo_de_um = None
    for w in cands:
        livre = (_meminfo().get("MemAvailable") or 0.0)
        orcamento = max(0.0, livre - margem)
        if por_worker is not None and w > 1 and por_worker * w > orcamento:
            linhas.append({"workers": w, "tempo_s": None, "avaliacoes": len(lote),
                           "vazao_aval_por_s": None, "speedup": None, "eficiencia": None,
                           "pico_memoria_gib": None,
                           "nao_medido": f"projeção de {n(por_worker * w)} GiB acima do orçamento "
                                         f"de {n(orcamento)} GiB ({n(livre)} GiB disponíveis menos "
                                         f"a margem de {n(margem)} GiB)"})
            continue
        am = Amostrador()
        am.start()
        t = time.perf_counter()
        _otim.avaliar_pontos(dados, lote, sub=SUB_PEQUENO, processos=w)
        dt = time.perf_counter() - t
        pico, metrica_amostra = am.parar()
        metrica = metrica_amostra or metrica
        if w == 1:
            tempo_de_um = dt
        if w > 1 and pico:
            por_worker = max(por_worker or 0.0, (pico - base_mem) / w)
        # Speedup e eficiência só existem contra W = 1. Se W = 1 não foi medido nesta varredura
        # (lista explícita), ficam None: inventar uma base seria comparar com outra coisa.
        linhas.append({"workers": w, "tempo_s": dt, "avaliacoes": len(lote),
                       "vazao_aval_por_s": len(lote) / dt,
                       "speedup": (tempo_de_um / dt) if tempo_de_um else None,
                       "eficiencia": (tempo_de_um / dt / w) if tempo_de_um else None,
                       "pico_memoria_gib": pico})
    medidas = [d for d in linhas if d["vazao_aval_por_s"]]
    melhor = max(medidas, key=lambda d: d["vazao_aval_por_s"]) if medidas else {}
    return {"visiveis": visiveis, "lote": len(lote), "sub": SUB_PEQUENO, "linhas": linhas,
            "aquecimento_pai_s": aquecimento, "memoria_base_gib": base_mem,
            "metrica_memoria": metrica, "memoria_por_worker_gib": por_worker,
            "margem_ram_gib": margem, "tem_base_w1": tempo_de_um is not None,
            "melhor_workers": melhor.get("workers"), "melhor_vazao": melhor.get("vazao_aval_por_s")}


def pontos_do_recorte(quantos, sub=SUB_PEQUENO):
    """`quantos` pontos do recorte, varrendo a primeira variável REAL dentro dos limites
    declarados e deixando as demais no mínimo declarado. Os valores saem do TOML: digitar a
    faixa aqui duplicaria a declaração e quebraria em silêncio se uma variável fosse acrescentada
    (a decodificação faz `zip`, que trunca)."""
    from fpso_siz.pfd import otimizacao as ot
    vs = ot.variaveis(sub)
    i = next((k for k, v in enumerate(vs) if v["tipo"] == "real"), 0)
    lo, hi = float(vs[i]["min"]), float(vs[i]["max"])
    pontos = []
    for k in range(quantos):
        x = [float(v["min"]) for v in vs]
        x[i] = lo + (hi - lo) * (k / max(1, quantos - 1))
        pontos.append(tuple(x))
    return pontos


# ----------------------------------------------------------------------------- recomputação
class Censo:
    """Conta chamadas e ARGUMENTOS REPETIDOS das camadas caras. Repetição idêntica é candidata a
    cache; o censo só registra — implementar cache é a Fase 9."""

    def __init__(self):
        self.dados = {}
        self._originais = []

    def envolver(self, modulo, nome, rotulo=None):
        original = getattr(modulo, nome)
        rotulo = rotulo or f"{modulo.__name__}.{nome}"
        reg = self.dados.setdefault(rotulo, {"chamadas": 0, "chaves": set(), "tempo_s": 0.0})

        def espiao(*a, **k):
            reg["chamadas"] += 1
            try:
                reg["chaves"].add(repr((a, sorted(k.items()))))
            except Exception:                                    # noqa: BLE001
                reg["chaves"].add(f"<irrepresentável #{reg['chamadas']}>")
            t = time.perf_counter()
            try:
                return original(*a, **k)
            finally:
                reg["tempo_s"] += time.perf_counter() - t

        setattr(modulo, nome, espiao)
        self._originais.append((modulo, nome, original))
        return self

    def restaurar(self):
        for modulo, nome, original in reversed(self._originais):
            setattr(modulo, nome, original)
        self._originais.clear()

    def resumo(self):
        return {r: {"chamadas": d["chamadas"], "distintas": len(d["chaves"]),
                    "repetidas": d["chamadas"] - len(d["chaves"]), "tempo_s": d["tempo_s"]}
                for r, d in sorted(self.dados.items()) if d["chamadas"]}


def _censo_novo():
    from fpso_siz.balanco import modelo
    from fpso_siz.pfd import _chedl, equipamento, fluidos
    c = Censo()
    for nome in ("resolver_caso",):
        c.envolver(modelo, nome)
    for nome in ("agua", "agua_saturada", "salmoura", "salmoura_fracao", "oleo", "oleo_vivo", "gas",
                 "gas_cp", "emulsao"):
        c.envolver(fluidos, nome)
    for nome in ("estado_gas", "agua_iapws", "agua_saturada_iapws", "salmoura_laliberte"):
        c.envolver(_chedl, nome)
    c.envolver(equipamento, "size_envelope")
    return c


def repeticoes(dados, individuos=4):
    """Duas medidas: dentro de UMA avaliação, e entre indivíduos de uma mini-população. A
    segunda é a que interessa à F15 — mostra o que se repete de um indivíduo para o outro."""
    from fpso_siz.pfd import otimizacao as ot
    x = ponto_do_projeto(dados, None)
    ot.avaliar(dados, x)   # aquece

    c = _censo_novo()
    ot.avaliar(dados, x)
    uma = c.resumo()
    c.restaurar()

    pontos = pontos_do_recorte(individuos)
    c = _censo_novo()
    for p in pontos:
        ot.avaliar(dados, p, sub=SUB_PEQUENO)
    varios = c.resumo()
    c.restaurar()
    return {"uma_avaliacao": uma, "mini_populacao": varios, "individuos": individuos,
            "pontos": [list(p) for p in pontos]}


def por_tag_entre_individuos(dados, individuos=4):
    """Por TAG, entre indivíduos: quantas vezes o envelope foi calculado, com quantas entradas
    DISTINTAS, e quanto custou. É a medida que diz se há recomputação idêntica de um indivíduo
    para o outro — e qual TAG paga a conta.

    Registra também se o TAG é usado pelo recorte (entra em alguma restrição ou objetivo).
    Dimensionar um TAG que o recorte não usa é trabalho inteiro jogado fora, e isso é candidato
    a otimização, não otimização: esta fase só mede."""
    from fpso_siz.pfd import equipamento, otimizacao as ot

    registro, atual = {}, {"tag": None}
    original_exec, original_env = equipamento.executar, equipamento.size_envelope

    def executar(ctx, estado):
        anterior, atual["tag"] = atual["tag"], estado.id
        try:
            return original_exec(ctx, estado)
        finally:
            atual["tag"] = anterior

    def envelope(*a, **k):
        d = registro.setdefault(atual["tag"] or "?", {"chamadas": 0, "chaves": set(), "tempo_s": 0.0})
        d["chamadas"] += 1
        try:
            d["chaves"].add(repr((a, sorted(k.items()))))
        except Exception:                                        # noqa: BLE001
            d["chaves"].add(f"<irrepresentável #{d['chamadas']}>")
        t = time.perf_counter()
        try:
            return original_env(*a, **k)
        finally:
            d["tempo_s"] += time.perf_counter() - t

    pontos = pontos_do_recorte(individuos)
    ot.avaliar(dados, pontos[0], sub=SUB_PEQUENO)      # aquece
    equipamento.executar, equipamento.size_envelope = executar, envelope
    try:
        for ponto in pontos:
            ot.avaliar(dados, ponto, sub=SUB_PEQUENO)
    finally:
        equipamento.executar, equipamento.size_envelope = original_exec, original_env

    usados = set(ot.tags_restritas(SUB_PEQUENO))
    for o in ot.objetivos(SUB_PEQUENO):
        usados |= set(o.get("tags", []))
    return {"individuos": individuos, "sub": SUB_PEQUENO, "pontos": [list(x) for x in pontos],
            "por_tag": {t: {"chamadas": d["chamadas"], "distintas": len(d["chaves"]),
                            "repetidas": d["chamadas"] - len(d["chaves"]), "tempo_s": d["tempo_s"],
                            "usado_pelo_recorte": t in usados}
                        for t, d in sorted(registro.items())}}


def nucleo_quente(dados):
    """O ponto que o `perfil` apontou: `sizing/trocador._tubo(c, n)`, o feixe com n tubos por
    passe. O motor o chama por vários caminhos no mesmo ponto da varredura (`requirement`,
    `derived`, `case_admissible`, `admissible`, `presentation_data`), e ele não é memoizado.

    Mede-se quantas chamadas há e quantos pares (caso, n) DISTINTOS elas cobrem. A razão entre
    os dois é o fator de recomputação idêntica — candidato a otimização, medido, não implementado."""
    from fpso_siz.pfd import otimizacao as ot
    from fpso_siz.sizing import trocador

    x = ponto_do_projeto(dados, None)
    ot.avaliar(dados, x)                                  # aquece
    original = trocador._tubo
    # `vivos` guarda uma referência a cada objeto de caso visto. Sem isso, um caso liberado pelo
    # GC devolve o endereço ao alocador, outro objeto reaparece com o MESMO id, e pares
    # diferentes colidiriam numa chave só — inflando o fator de recomputação.
    reg = {"chamadas": 0, "pares": set(), "vivos": [], "tempo_s": 0.0}
    conhecidos = {}

    def espiao(c, n):
        reg["chamadas"] += 1
        marca = conhecidos.get(id(c))
        if marca is None:
            marca = len(conhecidos)
            conhecidos[id(c)] = marca
            reg["vivos"].append(c)
        reg["pares"].add((marca, n))
        t = time.perf_counter()
        try:
            return original(c, n)
        finally:
            reg["tempo_s"] += time.perf_counter() - t

    trocador._tubo = espiao
    try:
        t = time.perf_counter()
        ot.avaliar(dados, x)
        total = time.perf_counter() - t
    finally:
        trocador._tubo = original
    distintas = len(reg["pares"])
    return {"funcao": "fpso_siz.sizing.trocador._tubo", "chamadas": reg["chamadas"],
            "pares_distintos": distintas, "casos_distintos": len(conhecidos),
            "fator_recomputacao": reg["chamadas"] / distintas if distintas else None,
            "tempo_na_funcao_s": reg["tempo_s"], "tempo_da_avaliacao_s": total}


def so_geometria(dados, individuos=4):
    """Pontos que mudam APENAS uma variável de equipamento (passes no tubo), com a premissa do
    balanço e o arranjo fixos. Mede quais TAGs recebem entradas idênticas nesse caso — é a
    medida que diz se separar `x_processo` de `x_equipamento` tem o que economizar.

    Só mede. Implementar a separação é a Fase 8, e o cache, a Fase 9."""
    from fpso_siz.pfd import equipamento, otimizacao as ot

    variaveis = ot.variaveis(None)
    geometricas = [i for i, v in enumerate(variaveis) if v["destino"] == "tag_geral"]
    if not geometricas:
        return {"aviso": "nenhuma variável de destino tag_geral declarada"}
    i = geometricas[0]
    base = list(ponto_do_projeto(dados, None))
    lo, hi = float(variaveis[i]["min"]), float(variaveis[i]["max"])
    pontos = []
    for k in range(individuos):
        x = list(base)
        x[i] = lo + (hi - lo) * (k % 2)       # alterna entre os dois extremos declarados
        pontos.append(tuple(x))

    registro, atual = {}, {"tag": None}
    original_exec, original_env = equipamento.executar, equipamento.size_envelope

    def executar(ctx, estado):
        anterior, atual["tag"] = atual["tag"], estado.id
        try:
            return original_exec(ctx, estado)
        finally:
            atual["tag"] = anterior

    def envelope(*a, **k):
        d = registro.setdefault(atual["tag"] or "?", {"chamadas": 0, "chaves": set(), "tempo_s": 0.0})
        d["chamadas"] += 1
        try:
            d["chaves"].add(repr((a, sorted(k.items()))))
        except Exception:                                        # noqa: BLE001
            d["chaves"].add(f"<irrepresentável #{d['chamadas']}>")
        t = time.perf_counter()
        try:
            return original_env(*a, **k)
        finally:
            d["tempo_s"] += time.perf_counter() - t

    ot.avaliar(dados, pontos[0])                                  # aquece
    equipamento.executar, equipamento.size_envelope = executar, envelope
    try:
        for ponto in pontos:
            ot.avaliar(dados, ponto)
    finally:
        equipamento.executar, equipamento.size_envelope = original_exec, original_env
    return {"variavel_variada": variaveis[i]["id"], "tag_da_variavel": variaveis[i]["tag"],
            "individuos": individuos, "pontos": [list(x) for x in pontos],
            "por_tag": {t: {"chamadas": d["chamadas"], "distintas": len(d["chaves"]),
                            "repetidas": d["chamadas"] - len(d["chaves"]), "tempo_s": d["tempo_s"]}
                        for t, d in sorted(registro.items())}}


# ----------------------------------------------------------------------------- relatório
def n(x, casas=2):
    if x is None:
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def caminho_legivel(p):
    """Caminho relativo à raiz quando está dentro dela; absoluto quando não está. `relative_to`
    sozinho estoura para qualquer arquivo fora da árvore, inclusive o `--casos` do dia a dia."""
    try:
        return str(Path(p).resolve().relative_to(RAIZ))
    except ValueError:
        return str(Path(p).resolve())


def juntar(arquivos, destino):
    """Junta rodadas num JSON só, com os recursos da máquina uma vez e as medidas por rótulo.
    É o que torna `performance-baseline.json` REGENERÁVEL a partir das rodadas."""
    rodadas, recursos_, casos = {}, None, None
    for caminho in arquivos:
        d = json.loads(Path(caminho).read_text(encoding="utf-8"))
        rotulo = d.get("rotulo") or Path(caminho).stem
        recursos_ = recursos_ or d.get("recursos")
        casos = casos or d.get("casos")
        rodadas[rotulo] = {k: v for k, v in d.items() if k not in ("recursos", "casos")}
    saida = {"recursos": recursos_, "casos": casos, "rodadas": rodadas}
    Path(destino).write_text(json.dumps(saida, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
                             encoding="utf-8")
    return destino


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--etapas", default="camadas,perfil,workers,repeticoes,portag,nucleo,geometria")
    ap.add_argument("--pontos", type=int, default=None, help="tamanho do lote da varredura de workers")
    ap.add_argument("--workers-lista", default=None,
                    help="lista explícita de workers a medir (ex.: 6,7,8); o padrão varre 1..N")
    ap.add_argument("--dados", type=Path, required=True,
                    help="JSON desta rodada (o relatório .md é escrito a partir dele, à mão)")
    ap.add_argument("--merge", type=Path, nargs="+", default=None,
                    help="JSONs de rodadas a juntar no canônico (com --dados como destino); sai depois")
    ap.add_argument("--rotulo", default=None, help="nome desta rodada dentro do JSON canônico")
    a = ap.parse_args()

    if a.merge:
        print(juntar(a.merge, a.dados))
        return

    from fpso_siz.balanco.dados import carregar_casos
    dados = carregar_casos(a.casos)
    etapas = [e.strip() for e in a.etapas.split(",") if e.strip()]
    medidas = {"recursos": recursos(), "casos": caminho_legivel(a.casos), "etapas": etapas,
               "rotulo": a.rotulo or ",".join(etapas),
               "quando": time.strftime("%Y-%m-%d %H:%M:%S%z")}
    if "camadas" in etapas:
        medidas["camadas"] = camadas(dados)
    if "perfil" in etapas:
        medidas["perfil"] = perfil(dados)
    if "workers" in etapas:
        lista = [int(w) for w in a.workers_lista.split(",")] if a.workers_lista else None
        medidas["workers"] = workers(dados, a.pontos, lista)
    if "repeticoes" in etapas:
        medidas["repeticoes"] = repeticoes(dados)
    if "portag" in etapas:
        medidas["por_tag_entre_individuos"] = por_tag_entre_individuos(dados)
    if "nucleo" in etapas:
        medidas["nucleo_quente"] = nucleo_quente(dados)
    if "geometria" in etapas:
        medidas["so_geometria"] = so_geometria(dados)
    a.dados.write_text(json.dumps(medidas, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
                       encoding="utf-8")
    print(a.dados)


if __name__ == "__main__":
    main()
