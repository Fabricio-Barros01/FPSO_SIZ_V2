"""Linha de comando `fpso-siz`. Invariante 4: não nomeia parâmetro nem grandeza; só itera
os descritores declarados em TOML (premissas, colunas, verificações), o registro de métodos
e os TAGs. Seleciona, lê, grava e delega: a orquestração de um equipamento é do serviço
por TAG (pfd/equipamento.py) e a composição das telas, de output/terminal/. Sem
argumentos, num terminal, abre o modo interativo."""
import argparse
import sys
import tomllib
from pathlib import Path

import fpso_siz.sizing  # noqa: F401  (registra os métodos de dimensionamento)
from fpso_siz import __version__
from fpso_siz.balanco import indicadores
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import carregar_casos, descritores_premissas, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.configuracao import carregar, exemplos
from fpso_siz.output import dimensionamento
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.balanco import memorial
from fpso_siz.output.latex.caso import memorial as memorial_caso
from fpso_siz.output.latex.tag import memorial as memorial_tag
from fpso_siz.output.terminal.comum import alteracoes as _alteracoes
from fpso_siz.output.terminal.comum import gravar_balanco
from fpso_siz.output.terminal.estilo import Estilo
from fpso_siz.output.terminal.relatorio import resumo_dimensionamento, verificacao_balanco
from fpso_siz.output.terminal.sessao import Sessao
from fpso_siz.pfd import ajustes as mod_ajustes
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas as mod_propostas

COLUNAS = 79  # largura dos resumos fora do modo interativo (saída pode ser arquivo)
CHAVES_BOT = ("casos_arquivo", "casos_sha256", "casos")


def _estilo(a):
    return Estilo.para(sys.stdout, ascii=getattr(a, "ascii", False))


def _mostrar(estilo, linhas):
    print("\n".join(estilo.t(li) for li in linhas).lstrip("\n"))


def cmd_balanco(a):
    dados = carregar_casos(a.casos)
    prem = premissas(dados, **_alteracoes(a.premissa))
    resultados = resolver_todos(dados, prem)
    aud = auditar(resultados, dados, prem)
    arq_json, arq_csv = gravar_balanco(dados, prem, resultados, aud, a.saida)
    e = _estilo(a)

    nao = [r for r in resultados if not r.convergiu]
    linhas = [f"{dados.origem} (sha256 {dados.sha256[:12]}…): {len(resultados)} casos, "
              f"{len(resultados) - len(nao)} convergidos"]
    for r in nao:
        linhas.append(f"  ATENÇÃO caso {r.num}: reciclo não convergiu ({r.iters + 1} iterações, "
                      f"resíduo {r.residuo_reciclo:.3e})")
    alteradas = [d for d in descritores_premissas(dados) if prem[d["nome"]] != d["valor"]]
    for d in alteradas:
        linhas.append(f"  premissa alterada {d['id']} {d['nome']} = {prem[d['nome']]} {d['unidade']} "
                      f"(base {d['valor']})")
    linhas.append("auditoria independente (maior |desvio| nos casos):")
    for v in aud:
        linhas.append(f"  {v['id']:<22} {v['max_desvio_abs']:.3e}  {v['unidade']}")
    linhas.append("verificação física (água, BSW, sal, T do FWKO):")
    linhas += verificacao_balanco(indicadores.verificacao_fisica(resultados, prem), e)
    linhas.append(f"gravados: {arq_json}, {arq_csv}")
    _mostrar(e, linhas)
    return 1 if nao else 0


def _arquivo_casos(a):
    """--casos é o arquivo do BOT; 'todos' (ou nenhum) usa o arquivo padrão da pasta corrente."""
    if a.casos in (None, memorial_caso.TODOS):
        return Path(carregar("interativo.toml")["arquivo_casos_padrao"])
    return Path(a.casos)


def cmd_memorial(a):
    por_caso = a.caso is not None or a.casos == memorial_caso.TODOS
    dados = carregar_casos(_arquivo_casos(a))
    prem = premissas(dados, **_alteracoes(a.premissa))
    saida = a.saida or Path(carregar("interativo.toml")["pasta_padrao"]) / "memorial"
    if por_caso:
        resultados = resolver_todos(dados, prem)
        nums = memorial_caso.selecionar(a.caso or memorial_caso.TODOS, [r.num for r in resultados])
        arquivos, erros = memorial_caso.exportar_lote(dados, prem, resultados, nums, saida, a.data, pdf=a.pdf)
        print("memoriais por caso: " + ", ".join(str(p) for p in arquivos))
        return _codigo_mc(erros, 0)
    resultados = resolver_todos(dados, prem)
    tex = memorial.gravar(dados, prem, resultados, saida)
    print(f"memorial: {tex}")
    if a.pdf:
        try:
            print(f"PDF: {compilacao.compilar(tex)}")
        except compilacao.ErroCompilacao as e:
            print(f"erro: {e}", file=sys.stderr)
            return 3
    return 0


def cmd_premissas(a):
    dados = carregar_casos(a.casos) if a.casos else None
    for d in descritores_premissas(dados):
        valor = d["valor"] if d["valor"] is not None else f"({d['origem']})"
        print(f"{d['id']:<5} {d['nome']:<12} {valor!s:<24} {d['unidade']:<22} {d['descricao']}")
    return 0


# ------------------------------------------------------------------ ajustes e contexto
def _ler_ajustes(caminho):
    if caminho is None:
        return mod_ajustes.Ajustes()
    return mod_ajustes.ler(tomllib.loads(Path(caminho).read_text(encoding="utf-8")))


def _verificar_contexto(aj, ctx, estados, bot=True):
    """Contexto gravado nos ajustes × execução: divergência bloqueante é erro (código 2),
    sem reaplicar ajustes; as demais vão como aviso para stderr."""
    gravado = aj.contexto if bot else {k: v for k, v in aj.contexto.items()
                                      if k not in (*CHAVES_BOT, "premissas")}
    atual = ctx.identidade()
    if not bot:
        atual = {**atual, "premissas": {}}
    divs = mod_ajustes.comparar_contexto(gravado, atual, estados)
    for d in divs:
        if not d.bloqueante:
            print(f"aviso: {d.mensagem}", file=sys.stderr)
    bloq = [d.mensagem for d in divs if d.bloqueante]
    if bloq:
        raise ValueError("erro de contexto: " + "; ".join(bloq) + ". Reconcilie no modo interativo "
                         "(Abrir / salvar ajustes) ou rode com o mesmo arquivo de casos e as mesmas --premissa.")


def _estado_do_tag(a, t, aj):
    for opcao, valor, esperado in (("--equipamento", a.equipamento, t.equipamento), ("--metodo", a.metodo, t.metodo)):
        if valor and valor != esperado:
            raise ValueError(f"{opcao} = {valor!r}, mas {t.tag} é dimensionado por {esperado!r}")
    estado = aj.tags.get(t.tag)
    origem = f" em {a.ajustes}" if a.ajustes else ""
    if a.auto_balanco:
        if estado is not None and estado.modo == mod_ajustes.MANUAL:
            raise ValueError(f"{t.tag} está salvo em modo manual{origem}; --auto-balanco não o troca "
                             "(a troca de modo é uma decisão persistida: faça-a no modo interativo)")
        return estado if estado is not None else servico.estado_inicial(t.tag)
    if estado is None:
        raise ValueError(f"{t.tag} não tem modo salvo{origem}; use --auto-balanco para o preenchimento "
                         "automático pelo balanço")
    return estado


def _dimensionar_equipamento(a):
    """`dimensionar --tag` (contexto BOT) ou `--avulso` (estado salvo nos ajustes)."""
    from fpso_siz.output import pfd
    from fpso_siz.output.terminal.pfd import tela_tag
    from fpso_siz.pfd.tags import tag

    aj = _ler_ajustes(a.ajustes)
    if a.tag:
        if a.casos is None:
            raise ValueError("--tag exige --casos (o JSON do BOT que identifica o contexto)")
        t = tag(a.tag)
        ctx = servico.Contexto(carregar_casos(a.casos), alteracoes=_alteracoes(a.premissa),
                               propostas=_propostas(a))
        estado = _estado_do_tag(a, t, aj)
        _verificar_contexto(aj, ctx, [estado])
        servico.configurar_dependencias(ctx, aj)
    else:
        if a.ajustes is None:
            raise ValueError("--avulso exige --ajustes (o arquivo onde o avulso foi salvo)")
        if a.avulso not in aj.avulsos:
            raise ValueError(f"avulso {a.avulso!r} não está em {a.ajustes}; salvos: {sorted(aj.avulsos) or '—'}")
        ctx = servico.Contexto(None, propostas=_propostas(a))
        estado = aj.avulsos[a.avulso]
        _verificar_contexto(aj, ctx, [], bot=False)
    rt = servico.executar(ctx, estado)
    e = _estilo(a)
    _mostrar(e, tela_tag(ctx, rt, e, COLUNAS))
    erros = []
    if a.saida:
        gravados = pfd.gravar_tag(ctx, rt, a.saida)
        if a.mc:
            arqs, erros = memorial_tag.exportar_lote(ctx, [rt], a.saida, a.data, pdf=a.pdf)
            gravados += arqs
        _mostrar(e, ["gravados: " + ", ".join(str(p) for p in gravados)])
    return _codigo_mc(erros, 0 if rt.concluido else 1)


def _codigo_mc(erros, codigo):
    """Falha de compilação do MC: mensagem em stderr e código 3 (como `memorial --pdf`)."""
    for erro in erros:
        print(f"erro: {erro}", file=sys.stderr)
    return 3 if erros else codigo


def _validar_mc(a):
    if a.pdf and not a.mc:
        raise ValueError("--pdf exige --mc")
    if a.mc and not a.saida:
        raise ValueError("--mc exige --saida (pasta onde o memorial é gravado)")


def cmd_dimensionar(a):
    _validar_mc(a)
    if a.mc and not (a.tag or a.avulso):
        raise ValueError("--mc vale com --tag ou --avulso (o memorial é do TAG)")
    if a.exemplo and (a.tag or a.auto_balanco or a.avulso):
        raise ValueError("--exemplo não se combina com --tag, --auto-balanco nem --avulso")
    if a.tag and a.avulso:
        raise ValueError("use --tag (TAG da planta) ou --avulso (equipamento avulso), não os dois")
    if a.auto_balanco and not a.tag:
        raise ValueError("--auto-balanco exige --tag")
    if a.tag or a.avulso:
        if a.avulso and (a.casos or a.premissa):
            raise ValueError("--avulso não usa --casos nem --premissa: o avulso está inteiro no arquivo de ajustes")
        return _dimensionar_equipamento(a)
    if a.ajustes or a.premissa:
        raise ValueError("--ajustes e --premissa valem com --tag (ou --avulso, só --ajustes)")
    if a.exemplo:
        cfg, origem = exemplos()[a.exemplo], f"exemplo:{a.exemplo}"
    elif a.casos:
        cfg, origem = tomllib.loads(a.casos.read_text(encoding="utf-8")), str(a.casos)
    else:
        raise ValueError("informe --casos, --exemplo, --tag ou --avulso")
    eq, m, casos, r = servico.dimensionar_arquivo(cfg, a.equipamento, a.metodo)
    e = _estilo(a)
    _mostrar(e, resumo_dimensionamento(eq, m, r, e, COLUNAS))
    if a.saida:
        print("gravados: " + ", ".join(str(p) for p in dimensionamento.gravar(eq, m, casos, r, a.saida, origem)))
    return 0 if r.feasible else 1


def cmd_interativo(a):
    return Sessao(casos=a.casos, ajustes=a.ajustes, ascii=a.ascii,
                  propostas=False if a.sem_propostas else a.propostas).rodar()


def cmd_pfd(a):
    from fpso_siz.output import pfd
    from fpso_siz.output.terminal.pfd import resumo
    from fpso_siz.pfd.planta import dimensionar

    ctx = servico.Contexto(carregar_casos(a.casos), alteracoes=_alteracoes(a.premissa), propostas=_propostas(a))
    aj = _ler_ajustes(a.ajustes)
    _verificar_contexto(aj, ctx, aj.todos())
    _validar_mc(a)
    planta = dimensionar(contexto=ctx, ajustes=aj)
    e = _estilo(a)
    _mostrar(e, resumo(planta, e, COLUNAS))
    erros = []
    if a.saida:
        gravados = pfd.gravar(planta, a.saida)
        if a.hysys:
            from fpso_siz.output import hysys
            gravados += hysys.gravar(planta, Path(a.saida) / "hysys")
        if a.mc:
            arqs, erros = memorial_tag.exportar_lote(ctx, planta.tags, a.saida, a.data, pdf=a.pdf)
            gravados += arqs
        _mostrar(e, ["gravados: " + ", ".join(str(p) for p in gravados)])
    return _codigo_mc(erros, 0 if planta.completa else 1)


def _propostas(a):
    """Valores propostos para as lacunas: os do pacote por padrão; --propostas ARQ usa outro
    arquivo; --sem-propostas deixa as lacunas abertas."""
    if getattr(a, "sem_propostas", False):
        if a.propostas:
            raise ValueError("use --propostas ou --sem-propostas, não os dois")
        return None
    return mod_propostas.carregar(a.propostas) if getattr(a, "propostas", None) else mod_propostas.padrao()


def _opcao_propostas(sub):
    sub.add_argument("--propostas", type=Path,
                     help="outro arquivo de valores PROPOSTOS (status = \"proposto\") para as entradas sem fonte; "
                          "padrão: o do pacote (config/pfd/pendencias_propostas.toml)")
    sub.add_argument("--sem-propostas", action="store_true", dest="sem_propostas",
                     help="não carrega valores propostos: as entradas sem fonte ficam como lacuna")


def _opcoes_mc(sub):
    sub.add_argument("--mc", action="store_true",
                     help="grava a memória de cálculo (LaTeX A4/SENAI, CSV dos gráficos e JSON) em <saida>/mc/<número>/")
    sub.add_argument("--pdf", action="store_true", help="com --mc: compila o memorial com latexmk")
    sub.add_argument("--data", help="data da folha de rosto do memorial (DD/MM/AAAA; padrão: hoje)")


def _terminal():
    return sys.stdin.isatty() and sys.stdout.isatty()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fpso-siz", description="FPSO_Siz — balanço preliminar e dimensionamento. "
                                 "Sem argumentos, num terminal, abre o modo interativo.")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="comando", required=True)

    argv = sys.argv[1:] if argv is None else list(argv)
    if argv in ([], ["--ascii"]) and _terminal():
        return Sessao(ascii=bool(argv)).rodar()

    b = sub.add_parser("balanco", help="balanço de massa e energia dos casos de projeto")
    b.add_argument("--casos", required=True, type=Path, help="arquivo de casos (JSON do BOT)")
    b.add_argument("--saida", required=True, type=Path, help="pasta de saída (JSON + CSV)")
    b.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR",
                   help="sobrescreve uma premissa (repetível); ver `fpso-siz premissas`")
    b.add_argument("--ascii", action="store_true", help="texto só em ASCII (setas, bordas, acentos)")
    b.set_defaults(func=cmd_balanco)

    m = sub.add_parser("memorial", help="memória de cálculo do balanço em LaTeX (A4); com --caso, um por caso")
    m.add_argument("--casos", help="arquivo de casos (JSON do BOT; padrão: o da pasta corrente) ou 'todos' = "
                                   "um MC_CasoNN por caso, com o arquivo padrão")
    m.add_argument("--caso", help="memorial por caso: N, lista (1,4-7) ou 'todos' → MC_CasoNN")
    m.add_argument("--saida", type=Path, help="pasta de saída (padrão: saida/memorial)")
    m.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR")
    m.add_argument("--pdf", action="store_true", help="compila com latexmk, se instalado")
    m.add_argument("--data", help="com --caso: data da folha de rosto (DD/MM/AAAA; padrão: hoje)")
    m.set_defaults(func=cmd_memorial)

    p = sub.add_parser("premissas", help="lista as premissas do balanço (id, valor, unidade, fonte)")
    p.add_argument("--casos", type=Path, help="arquivo de casos, para os valores que vêm dele")
    p.set_defaults(func=cmd_premissas)

    d = sub.add_parser("dimensionar", help="dimensiona um equipamento: TAG da planta (--tag), avulso salvo "
                       "(--avulso) ou arquivo/exemplo no contrato do Julia (--casos TOML, --exemplo)")
    d.add_argument("--casos", type=Path, help="com --tag: JSON do BOT (contexto); sem --tag: TOML com blocos [[case]]")
    d.add_argument("--exemplo", choices=sorted(exemplos()), help="arquivo de casos de exemplo embutido")
    d.add_argument("--tag", help="TAG da planta (ex.: um dos de `fpso-siz pfd`)")
    d.add_argument("--auto-balanco", action="store_true", dest="auto_balanco",
                   help="com --tag: preenchimento automático pelo balanço")
    d.add_argument("--avulso", help="equipamento avulso salvo no arquivo de ajustes")
    d.add_argument("--ajustes", type=Path, help="arquivo de ajustes da sessão (ajustes_pfd.toml)")
    d.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR",
                   help="com --tag: sobrescreve uma premissa do balanço")
    d.add_argument("--equipamento", choices=[e.method_id for e in registro.equipments()],
                   help="dispensável se o arquivo declara `equipment`")
    d.add_argument("--metodo", help="id do método (padrão: o primeiro registrado para o equipamento)")
    d.add_argument("--saida", type=Path, help="pasta de saída (JSON + CSV); sem ela, só o resumo")
    _opcoes_mc(d)
    _opcao_propostas(d)
    d.add_argument("--ascii", action="store_true", help="texto só em ASCII (setas, bordas, acentos)")
    d.set_defaults(func=cmd_dimensionar)

    f = sub.add_parser("pfd", help="dimensiona os TAGs da planta pelo mesmo serviço do TAG isolado")
    f.add_argument("--casos", required=True, type=Path, help="arquivo de casos (JSON do BOT)")
    f.add_argument("--ajustes", type=Path, help="arquivo de ajustes (esquema 2 ou legado F10b)")
    f.add_argument("--saida", type=Path, help="pasta de saída (JSON + CSV por TAG e planta.csv)")
    f.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR")
    _opcoes_mc(f)
    _opcao_propostas(f)
    f.add_argument("--hysys", action="store_true",
                   help="com --saida: grava o pacote de dados para montar o modelo no HYSYS em <saida>/hysys/ "
                        "(sem importação automática; ver docs/validacao/47)")
    f.add_argument("--ascii", action="store_true", help="texto só em ASCII (setas, bordas, acentos)")
    f.set_defaults(func=cmd_pfd)

    i = sub.add_parser("interativo", help="assistente: equipamento/TAG, planta, balanço e exportação")
    i.add_argument("--casos", type=Path, help="arquivo de casos do balanço (JSON do BOT)")
    i.add_argument("--ajustes", type=Path, help="arquivo de ajustes a retomar")
    i.add_argument("--ascii", action="store_true", help="texto só em ASCII (setas, bordas, acentos)")
    _opcao_propostas(i)
    i.set_defaults(func=cmd_interativo)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, KeyError, FileNotFoundError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e  # KeyError põe aspas no str()
        print(f"erro: {msg}", file=sys.stderr)
        return 2
