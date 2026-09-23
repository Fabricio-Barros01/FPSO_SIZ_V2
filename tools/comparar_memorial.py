#!/usr/bin/env python3
"""Compara o memorial gerado (layout original) com o main.tex de referência, por template."""
import sys
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.output.latex.balanco import memorial

RAIZ = Path(__file__).resolve().parent.parent
FIX = RAIZ / "tests" / "fixtures" / "python_ref"


def main():
    dados = carregar_casos(FIX / "design_cases_bot.json")
    prem = premissas(dados)
    R = resolver_todos(dados, prem)
    ref = (FIX / "main_ref.tex").read_text(encoding="utf-8")
    env, ctx = memorial.preparar(dados, prem, R)
    pos, ruins = 0, 0
    for nome in memorial.LAYOUTS["original"] + memorial.CORPO:
        txt = env.get_template(f"{nome}.tex.j2").render(ctx)
        alvo = ref[pos:pos + len(txt)]
        if txt != alvo:
            ruins += 1
            i = next(k for k, (a, b) in enumerate(zip(txt, alvo)) if a != b) if any(a != b for a, b in zip(txt, alvo)) else min(len(txt), len(alvo))
            linha = txt[:i].count("\n") + 1
            print(f"DIFERE {nome}: linha {linha} do template-renderizado")
            print("   gerado:", repr(txt[max(0, i - 60):i + 80]))
            print("   ref   :", repr(alvo[max(0, i - 60):i + 80]))
            if "-v" not in sys.argv:
                return 1
        pos += len(txt)
    total = memorial.gerar(dados, prem, R)
    print("IDÊNTICO" if total == ref and not ruins else f"diferente ({ruins} templates); tamanho {len(total)} vs {len(ref)}")
    return 0 if total == ref else 1


if __name__ == "__main__":
    raise SystemExit(main())
