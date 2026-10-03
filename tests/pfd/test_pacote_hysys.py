"""Pacote de dados para o HYSYS (`output/hysys.py`, config/pfd/hysys.toml, docs/validacao/47).

O pacote só consolida o que já foi calculado: os 16 casos rastreáveis, o estado operacional
depois do rating do P-001, a geometria e a multiplicidade de cada TAG pela mesma regra de área
da otimização, a classificação (restrição, decisão pendente, verificação incompleta, limitação
aceita) e os dados que faltam. Nada é preenchido por suposição."""
import csv
import json

import pytest

from fpso_siz.balanco.exportacao import cargas as cargas_balanco
from fpso_siz.output import hysys
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import otimizacao as ot


@pytest.fixture(scope="module")
def pacote(planta_propostas, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("hysys")
    a = ot.Avaliacao((1.0, 1.0, 1.0), {"volume_vasos": 1.0, "area_trocadores": 2.0, "carga_aquecimento": 3.0},
                     {"P-001": 0.0}, {"P-001": "dimensionado"}, True, pendencias={"P-001": ["comprimento_tubo"]})
    b = ot.Avaliacao((2.0, 1.0, 1.0), {"volume_vasos": 1.0, "area_trocadores": 2.0, "carga_aquecimento": 3.0},
                     {"P-001": 1.0}, {"P-001": "inviavel"}, True)
    comp = ot.Comparacao("configuracao", ((1.0, 1.0, 1.0), (2.0, 1.0, 1.0), (3.0, 1.0, 1.0)), (a, b), 2)
    arquivos = hysys.gravar(planta_propostas, pasta, comp)
    return pasta, json.loads((pasta / "hysys.json").read_text(encoding="utf-8")), arquivos


def _csv(caminho):
    with caminho.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_os_16_casos_e_as_correntes_ficam_rastreaveis(pacote, planta_propostas):
    pasta, d, arquivos = pacote
    assert {p.name for p in arquivos} == {"hysys.json", "hysys_correntes.csv", "hysys_cargas.csv",
                                          "hysys_equipamentos.csv"}
    assert [c["num"] for c in d["casos"]] == list(range(1, 17))
    assert d["proveniencia"]["sha256"] == planta_propostas.dados.sha256
    assert d["proveniencia"]["etapa_dos_estados"] == ["apos_rating_P-001"]
    correntes = _csv(pasta / "hysys_correntes.csv")
    n = len(d["topologia"]["correntes"])
    assert len(correntes) == 16 * n and {int(r["caso"]) for r in correntes} == set(range(1, 17))
    # composição: só onde existe (casos avaliáveis); onde falta, None — nunca inventada
    for c in d["casos"]:
        t = c["termodinamica"]
        assert (t["z_caso"] is not None) == t["avaliavel"]
    assert "composicao_gas_lift" in {f["id"] for f in d["dados_faltantes"]}


def test_estado_operacional_e_cargas_pos_rating(pacote, planta_propostas):
    """As correntes e as cargas do pacote são as do estado operacional (o que P-002/P-003
    recebem); o preliminar aparece ao lado, por etapa, para a continuidade."""
    pasta, _, _ = pacote
    op = {r.num: r for r in planta_propostas.balanco_operacional}
    correntes = {(int(r["caso"]), r["corrente"]): r for r in _csv(pasta / "hysys_correntes.csv")}
    for c in planta_propostas.tag("P-001").operacao.casos:
        assert float(correntes[(c.num, "C-07")]["T_C"]) == pytest.approx(c.t_fria_out, rel=1e-12)
        assert float(correntes[(c.num, "C-23")]["T_C"]) == pytest.approx(c.t_quente_out, rel=1e-12)
    cargas = {(int(r["caso"]), r["etapa"]): r for r in _csv(pasta / "hysys_cargas.csv")}
    assert len(cargas) == 32
    pre = {r.num: r for r in planta_propostas.balanco}
    for num, r in op.items():
        # mesma função do balanco.json (Q_H = Σ Q_in dos blocos), em cada etapa
        for etapa, estado in ((r.etapa, r), ("preliminar", pre[num])):
            for k, v in cargas_balanco(estado).items():
                assert float(cargas[(num, etapa)][k]) == pytest.approx(v, rel=1e-12), (num, etapa, k)
    assert any(float(cargas[(n, op[n].etapa)]["Q_H"]) > float(cargas[(n, "preliminar")]["Q_H"]) for n in op)


def test_geometria_multiplicidade_e_classificacao_pela_regra_central(pacote, planta_propostas):
    pasta, d, _ = pacote
    linhas = {r["tag"]: r for r in _csv(pasta / "hysys_equipamentos.csv")}
    eqs = {e["tag"]: e for e in d["equipamentos"]}
    assert set(linhas) == set(eqs) == {rt.tag.tag for rt in planta_propostas.tags}
    for rt in planta_propostas.tags:
        assert eqs[rt.tag.tag]["areas"] == servico.areas_troca(rt)
        assert eqs[rt.tag.tag]["classificacao"]["decisoes_pendentes"] == rt.decisoes_pendentes
    p1 = eqs["P-001"]
    assert p1["geometria"]["origem"] == "geometria_instalada" and p1["operacao"] is not None
    assert p1["classificacao"]["decisoes_pendentes"] == ["comprimento_tubo"]
    assert p1["classificacao"]["verificacoes_incompletas"]
    assert float(linhas["P-001"]["area_instalada_m2"]) == pytest.approx(p1["areas"]["instalada_m2"], rel=1e-12)
    assert int(linhas["P-001"]["unidades_reserva"]) == p1["geometria"]["standby"]
    assert eqs["P-002"]["etapa_balanco"] == "apos_rating_P-001"


def test_comparacao_registra_candidatos_motivos_e_o_que_ficou_de_fora(pacote):
    _, d, _ = pacote
    c = d["comparacao"]
    assert c["limite_atingido"] and len(c["nao_avaliados"]) == 1 and len(c["dominio"]) == 3
    ref, inv = c["candidatos"]
    assert ref["referencia"] and ref["situacao"] == "decisao_pendente" and ref["admissivel"]
    assert ref["motivos"] == [{"tipo": "decisao_pendente", "id": "P-001", "criterios": ["comprimento_tubo"]}]
    assert inv["situacao"] == "inviavel" and not inv["nao_dominado"] and inv["violacoes"] == {"P-001": 1.0}
    assert "sem pesos" in c["criterio"]


def test_avisos_nao_prometem_convergencia_nem_importacao(pacote):
    _, d, _ = pacote
    texto = " ".join(d["avisos"])
    assert "não garante convergência" in texto and "Nenhuma importação automática" in texto
    assert all(f["descricao"] and f["referencia"] for f in d["dados_faltantes"])
