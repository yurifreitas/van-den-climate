"""Indices Nino 1+2 / 3 / 3.4 / 4 — NOAA PSL, formato "correlation .data".

manifests/sources.yaml declara uma unica fonte `psl_nino` com 4 variaveis
(vars: [nino12, nino3, nino34, nino4]) — cada uma e um arquivo .data
separado no dominio PSL. Um so Ingestor busca os quatro e concatena o
payload bruto (com marcadores "### <fname>") para manter uma unica entrada
de proveniencia por execucao, como o manifesto exige.

Formato de cada arquivo: 1a linha "ano_inicial ano_final", depois uma linha
por ano com 12 valores mensais, valor faltante -99.99. O rodape traz linhas
de texto livre (nome da serie, URL) que nao sao dados — descartamos tudo que
nao seja "ano + 12 floats" (13 tokens numericos).
"""
from __future__ import annotations

import pandas as pd

from src.contracts import AnchorMode, QualityFlag
from src.ingest.base import FetchResult, Ingestor
from src.ingest.registry import register

MISSING = -99.99
BASE_URL = "https://psl.noaa.gov/data/correlation/{fname}.data"

# signal_id gravado -> nome do arquivo PSL. nino34_raw= materia-prima de
# nino34_lag1 no bloco enso_state; a defasagem/derivacao acontece na Camada 3.
VARIANTS = {
    "nino12_raw": "nina1",
    "nino3_raw": "nina3",
    "nino34_raw": "nina34",
    "nino4_raw": "nina4",
}

MARKER_PREFIX = "### "


def _parse_one(text: str) -> list[tuple[int, int, float]]:
    rows = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) != 13:
            continue  # cabecalho (2 tokens) ou rodape de texto livre
        try:
            year = int(tokens[0])
            values = [float(t) for t in tokens[1:]]
        except ValueError:
            continue
        if not (1800 <= year <= 2200):
            continue
        for month, val in enumerate(values, start=1):
            rows.append((year, month, val))
    return rows


@register("psl_nino")
class PslNinoIngestor(Ingestor):
    source_id = "psl_nino"
    INGESTOR_VERSION = "1"
    file_ext = "txt"
    product_version = "psl correlation .data (nina1/nina3/nina34/nina4)"

    def fetch(self) -> FetchResult:
        chunks = []
        urls = []
        for fname in VARIANTS.values():
            url = BASE_URL.format(fname=fname)
            content = self._http_get(url)
            chunks.append(f"{MARKER_PREFIX}{fname}\n{content.decode('utf-8', errors='replace')}")
            urls.append(url)
        combined = "\n".join(chunks).encode("utf-8")
        return FetchResult(content=combined, url=";".join(urls), notes="4 arquivos PSL concatenados com marcadores ### <fname>")

    def parse(self, raw: bytes) -> pd.DataFrame:
        text = raw.decode("utf-8", errors="replace")
        # separa em blocos por marcador
        blocks: dict[str, str] = {}
        current_name = None
        current_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith(MARKER_PREFIX):
                if current_name is not None:
                    blocks[current_name] = "\n".join(current_lines)
                current_name = line[len(MARKER_PREFIX):].strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_name is not None:
            blocks[current_name] = "\n".join(current_lines)

        frames = []
        for signal_id, fname in VARIANTS.items():
            block_text = blocks.get(fname)
            if block_text is None:
                raise ValueError(f"bloco '{fname}' ausente no payload concatenado")
            rows = _parse_one(block_text)
            if not rows:
                raise ValueError(f"nenhuma linha de dados reconhecida para {fname}")
            df = pd.DataFrame(rows, columns=["year", "month", "value"])
            timestamp = pd.to_datetime({"year": df["year"], "month": df["month"], "day": 1})
            is_missing = df["value"] <= (MISSING + 1e-6)
            quality = pd.Series(int(QualityFlag.OK), index=df.index)
            quality[is_missing] = int(QualityFlag.INVALID)
            value = df["value"].where(~is_missing)
            frames.append(pd.DataFrame({
                "signal_id": signal_id,
                "timestamp": timestamp,
                "value": value,
                "source_version": f"{fname}.data",
                "quality_flag": quality,
                "anchor_mode": AnchorMode.RELATIVE,
            }))
        return pd.concat(frames, ignore_index=True)
