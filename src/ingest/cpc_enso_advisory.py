"""Boletim ENSO do CPC — a unica camada PROSPECTIVA desta central.

Por que existe, e por que so agora
==================================

Tudo o mais nesta engine olha para tras: ONI medido ate a temporada passada,
impacto municipal do evento de 26/04/2024, deficit de prevencao declarado em
2024. Um instrumento de prevencao que so olha para tras responde "onde doeu",
nunca "o que vem".

O que ele NAO e (ADR-012, mantida)
==================================

Isto e CONTEXTO, nunca feature. O boletim do CPC nao entra em nenhum bloco de
`feature_blocks.yaml`, nao alimenta a Camada 3 e nao toca o alvo. A razao da
ADR-012 continua valendo integralmente: previsao de modelo dinamico como
preditor introduz vazamento de informacao futura e dependencia operacional
irreproduzivel no hindcast. Consumi-lo como CONTEXTO — mostrar ao usuario o
que a autoridade oficial diz sobre os proximos meses — nao viola nada disso,
e omiti-lo faz a central parecer cega quando a informacao existe e e publica.

Fronteira epistemica que o payload carrega
==========================================

O boletim e `basis: modeled` e a autoria e do CPC/NOAA, nao nossa. A interface
tem de deixar claro que a previsao prospectiva vem de fora: a engine local
continua sem previsao aceita (nenhum modelo passou a ADR-007), e confundir
"o CPC preve" com "nossa engine preve" seria o erro mais caro possivel numa
central que existe para separar o que sabe do que supoe.

Parse
=====

O produto e texto livre em HTML — nao ha arquivo tabular publico equivalente.
O parser extrai campos com ancoras estaveis (rotulos que o CPC usa ha anos) e
FALHA ALTO quando nao encontra: um boletim silenciosamente meio-parseado
mostraria uma previsao desatualizada com cara de atual, que e pior que nao
mostrar nada. O bruto fica em disco, entao um parser quebrado se conserta
sem rede.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.ingest.ibge_rs import IngestError, Source, _payload, _stamp_rows

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_INTERIM = REPO_ROOT / "data" / "interim"

ADVISORY = Source(
    source_id="cpc_enso_advisory",
    url="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
    file_ext="html",
    notes=(
        "ENSO Diagnostic Discussion, CPC/NCEP/NWS. Emitido mensalmente. "
        "CONTEXTO conforme ADR-012 — nunca feature."
    ),
)

# Estados possiveis do sistema de alerta do CPC, do mais ao menos especifico
# (a ordem importa: "El Nino Advisory" contem "Advisory").
ALERT_STATES = [
    "El Nino Advisory",
    "La Nina Advisory",
    "El Nino Watch",
    "La Nina Watch",
    "Final El Nino Advisory",
    "Final La Nina Advisory",
    "Not Active",
]


@dataclass
class Advisory:
    """Boletim estruturado. Todo campo textual e citacao curta e atribuida."""

    issued: str | None
    alert_status: str | None
    synopsis: str
    probabilities: list[dict[str, Any]]
    next_update: str | None
    source_url: str


def _texto(raw: bytes) -> str:
    """HTML -> texto plano normalizado, com entidades resolvidas."""
    doc = raw.decode("utf-8", errors="replace")
    doc = re.sub(r"(?s)<script.*?</script>", " ", doc)
    doc = re.sub(r"(?s)<style.*?</style>", " ", doc)
    doc = re.sub(r"<[^>]+>", " ", doc)
    doc = html.unescape(doc)
    # normaliza acentuacao espanhola do "Niño" para casar com ALERT_STATES
    doc = doc.replace("ñ", "n").replace("Ñ", "N")
    return re.sub(r"\s+", " ", doc).strip()


def _data_iso(texto: str) -> str | None:
    """'9 July 2026' -> '2026-07-09'. None se o formato mudar."""
    m = re.search(r"\b(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})\b", texto)
    if not m:
        return None
    try:
        return pd.Timestamp(f"{m.group(1)} {m.group(2)} {m.group(3)}").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse(raw: bytes) -> Advisory:
    texto = _texto(raw)

    alert = next((s for s in ALERT_STATES if f"ENSO Alert System Status: {s}" in texto), None)
    if alert is None:
        m = re.search(r"ENSO Alert System Status:\s*([A-Za-z ]{3,40}?)\s+Synopsis", texto)
        alert = m.group(1).strip() if m else None
    if alert is None:
        raise IngestError(
            f"{ADVISORY.source_id}: 'ENSO Alert System Status' nao encontrado — "
            "o CPC mudou o formato do boletim; parser precisa ser revisto"
        )

    m_syn = re.search(r"Synopsis:\s*(.+?)(?=\s[A-Z][a-z]+ (?:strengthened|weakened|continued)|$)", texto)
    synopsis = m_syn.group(1).strip() if m_syn else ""
    # A sinopse do CPC e uma frase. Se vier um paragrafo inteiro, o corte
    # falhou e e melhor truncar do que republicar meia pagina do boletim.
    synopsis = synopsis.split(". ")[0].strip().rstrip(".") + "." if synopsis else ""
    if not synopsis:
        raise IngestError(f"{ADVISORY.source_id}: 'Synopsis:' ausente — formato mudou")

    # Probabilidades: toda ocorrencia de "NN% chance" com a oracao ao redor.
    # Guardamos a frase inteira, nao so o numero: "97% de chance" sem o
    # "de persistir ate o inicio da primavera de 2027" e um numero sem
    # referente, que numa central de risco e ruido com cara de precisao.
    probabilities: list[dict[str, Any]] = []
    # O CPC repete a sinopse em "In summary, ..." no fim do boletim. Sem este
    # corte cada probabilidade aparece duas vezes, e uma lista com "97%" duas
    # vezes parece duas afirmacoes independentes se reforcando — exatamente a
    # leitura errada.
    corpo = texto.split("In summary,")[0]
    for m in re.finditer(r"(?:There is an?\s+)?(\d{1,3})%\s+chance\s+(?:that\s+)?(.{0,180}?)(?=\s*[.\[]|$)", corpo):
        frase = re.sub(r"\s+", " ", m.group(2)).strip()
        if not frase:
            continue
        probabilities.append({"percent": int(m.group(1)), "claim": frase})

    m_next = re.search(r"next ENSO Diagnostics? Discussion is scheduled for\s+(.{0,30}?\d{4})", texto)
    next_update = _data_iso(m_next.group(1)) if m_next else None

    m_issued = re.search(r"CLIMATE PREDICTION CENTER/NCEP/NWS\s+(.{0,30}?\d{4})", texto)
    issued = _data_iso(m_issued.group(1)) if m_issued else None
    if issued is None:
        raise IngestError(
            f"{ADVISORY.source_id}: data de emissao nao encontrada — sem ela nao da para "
            "saber se o boletim esta velho, e boletim velho com cara de atual e pior que nenhum"
        )

    return Advisory(
        issued=issued,
        alert_status=alert,
        synopsis=synopsis,
        probabilities=probabilities,
        next_update=next_update,
        source_url=ADVISORY.url,
    )


def run() -> Advisory:
    raw, raw_dir = _payload(ADVISORY)
    try:
        adv = parse(raw)
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(f"{ADVISORY.source_id}: falha na etapa parse ({raw_dir}): {exc}") from exc
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    (DATA_INTERIM / f"{ADVISORY.source_id}.json").write_text(
        json.dumps(asdict(adv), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _stamp_rows(raw_dir, len(adv.probabilities))
    return adv


def load() -> Advisory | None:
    """Boletim ingerido, ou None se nunca rodou."""
    path = DATA_INTERIM / f"{ADVISORY.source_id}.json"
    if not path.exists():
        return None
    return Advisory(**json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    a = run()
    print(f"[OK] {a.issued} · {a.alert_status} · {len(a.probabilities)} probabilidades")
    print(f"     {a.synopsis}")
    for p in a.probabilities:
        print(f"     {p['percent']}% — {p['claim'][:90]}")
