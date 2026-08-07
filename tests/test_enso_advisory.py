"""Parser do boletim ENSO do CPC.

O produto e texto livre em HTML e nao ha equivalente tabular publico. Um
parser de texto livre falha de dois jeitos, e so um deles e aceitavel:

  - falhar ALTO quando o CPC muda o formato  -> aceitavel, conserta-se;
  - devolver um boletim meio-parseado        -> inaceitavel, porque a tela
    mostraria uma previsao desatualizada com cara de atual.

Estes testes travam o primeiro comportamento.
"""
from __future__ import annotations

import pytest

from src.ingest import cpc_enso_advisory as adv
from src.ingest.ibge_rs import IngestError

BOLETIM = """
<html><body>
ENSO DIAGNOSTIC DISCUSSION issued by CLIMATE PREDICTION CENTER/NCEP/NWS
9 July 2026
ENSO Alert System Status: El Ni&ntilde;o Advisory
Synopsis: El Ni&ntilde;o continues and will strengthen through the end of the year,
with a 97&#37; chance it will persist through early spring 2027.
El Ni&ntilde;o strengthened over the past month, with a large area of anomalies.
There is an 81&#37; chance of a very strong El Ni&ntilde;o during October-December [Fig. 8].
In summary, El Ni&ntilde;o continues, with a 97&#37; chance it will last through early spring 2027.
The next ENSO Diagnostics Discussion is scheduled for 13 August 2026.
</body></html>
"""


@pytest.fixture(scope="module")
def parsed():
    return adv.parse(BOLETIM.encode("utf-8"))


def test_extrai_status_data_e_sinopse(parsed):
    assert parsed.alert_status == "El Nino Advisory"
    assert parsed.issued == "2026-07-09"
    assert parsed.synopsis.startswith("El Nino continues")
    assert parsed.next_update == "2026-08-13"


def test_nao_duplica_probabilidade_repetida_no_resumo(parsed):
    """O CPC repete a sinopse em 'In summary'. Duas vezes '97%' pareceria
    duas afirmacoes independentes se reforcando."""
    assert len(parsed.probabilities) == 2
    assert [p["percent"] for p in parsed.probabilities] == [97, 81]


def test_probabilidade_carrega_o_referente(parsed):
    """Numero sem a oracao que ele qualifica e ruido com cara de precisao."""
    for p in parsed.probabilities:
        assert p["claim"].strip()
    assert "October-December" in parsed.probabilities[1]["claim"]


def test_falha_alto_sem_status_de_alerta():
    quebrado = BOLETIM.replace("ENSO Alert System Status: El Ni&ntilde;o Advisory", "")
    with pytest.raises(IngestError, match="Alert System Status"):
        adv.parse(quebrado.encode("utf-8"))


def test_falha_alto_sem_data_de_emissao():
    """Boletim sem data e pior que boletim ausente: nao da para saber se venceu."""
    quebrado = BOLETIM.replace("CLIMATE PREDICTION CENTER/NCEP/NWS\n9 July 2026", "CPC")
    with pytest.raises(IngestError, match="data de emissao"):
        adv.parse(quebrado.encode("utf-8"))


def test_falha_alto_sem_sinopse():
    quebrado = BOLETIM.replace("Synopsis:", "Resumo:")
    with pytest.raises(IngestError, match="Synopsis"):
        adv.parse(quebrado.encode("utf-8"))
