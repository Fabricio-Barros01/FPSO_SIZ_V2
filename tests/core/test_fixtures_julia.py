"""F5 — as fixtures do Julia são rastreáveis (commit) e continuam sendo o oráculo dos equipamentos.

**Decisão do usuário em 2026-09-27: a suíte não executa mais o Julia.** O código amadureceu e
segue em outra direção, então o teste que reexecutava o FPSO_Siz Julia para regenerar estas
fixtures e comparar bytes (marcador `julia`) foi retirado, junto com o marcador.

O que NÃO mudou: os arquivos de `tests/fixtures/julia/` seguem versionados e seguem sendo o
oráculo numérico dos equipamentos — sete arquivos de teste comparam o Python contra eles, e é
deles que vem a garantia de que refatoração não muda número. A proveniência está registrada em
`manifesto.json` (commit `ab58fc6` do repositório Julia) e o script que os gerou continua no
repositório (`tools/exportar_fixtures_julia.sh`), para quem precisar refazer a exportação à mão.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FJ = RAIZ / "tests" / "fixtures" / "julia"
MANIFESTO = json.loads((FJ / "manifesto.json").read_text(encoding="utf-8"))


def test_manifesto_registra_commit_e_arquivos():
    assert MANIFESTO["commit"] == "ab58fc631749aa81fdf7db566aa14a0cecd777c4"
    assert MANIFESTO["julia"] and all((FJ / a).exists() for a in MANIFESTO["arquivos"])
    boxes = {json.loads((FJ / a).read_text(encoding="utf-8"))["box"] for a in MANIFESTO["arquivos"] if a != "formatos_julia.json"}
    assert boxes == {"separador-3f", "knockout-2f", "vaso-eletrostatico", "bomba-centrifuga", "trocador-calor",
                     "analise-pinch", "controle-separador"}


def test_caso_de_referencia_alves_komesu():
    e = json.loads((FJ / "separador-3f.json").read_text(encoding="utf-8"))["envelope"]
    assert e["feasible"] and e["x"] == 6300.0 and round(e["y"], 2) == 18.59 and e["driver_case"] == "Fim de vida"
    assert len(e["case_names"]) == 10
