"""AAO/SAM mensal — NOAA CPC (indice antartico anular / modo anular sul).

Formato: "YYYY MM valor", um registro por linha, sem cabecalho, sem
sentinela de faltante documentada (a serie e continua desde 1979 na pratica).
anchor_mode=fixed_1951_1990: o bloco `sam` em feature_blocks.yaml ancora
fixo, nao relativo — a tendencia forcada por ozonio/GEE e isolada no bloco
`trend`, entao SAM em si nao deve ser renormalizado a cada 30 anos (ADR-005
trata SAM como excecao a regra geral de teleconexao).

Nota: so existe a versao mensal publicamente estavel neste endpoint; a
variante diaria (usada para sam_days_pos_frac e sam_persistence no bloco
`sam`) tem outro endpoint CPC que muda de path com frequencia — deixado
como TODO para quando o bloco `sam` for implementado na Camada 3/4, dado
que o mensal ja destrava sam_cpc_son.
"""
from __future__ import annotations

import pandas as pd

from src.contracts import AnchorMode, QualityFlag
from src.ingest.base import FetchResult, Ingestor
from src.ingest.registry import register

URL = "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/aao/monthly.aao.index.b79.current.ascii"


@register("cpc_aao")
class CpcAaoIngestor(Ingestor):
    source_id = "cpc_aao"
    INGESTOR_VERSION = "1"
    file_ext = "txt"
    product_version = "monthly.aao.index.b79.current.ascii"

    def fetch(self) -> FetchResult:
        content = self._http_get(URL)
        return FetchResult(content=content, url=URL, notes="AAO/SAM mensal, YYYY MM valor")

    def parse(self, raw: bytes) -> pd.DataFrame:
        text = raw.decode("utf-8", errors="replace")
        rows = []
        for line in text.splitlines():
            tokens = line.split()
            if len(tokens) != 3:
                continue
            try:
                year, month, val = int(tokens[0]), int(tokens[1]), float(tokens[2])
            except ValueError:
                continue
            rows.append((year, month, val))

        if not rows:
            raise ValueError("nenhuma linha de dados reconhecida no formato AAO mensal")

        df = pd.DataFrame(rows, columns=["year", "month", "value"])
        timestamp = pd.to_datetime({"year": df["year"], "month": df["month"], "day": 1})

        return pd.DataFrame({
            "signal_id": "sam_cpc_monthly",
            "timestamp": timestamp,
            "value": df["value"],
            "source_version": self.product_version,
            "quality_flag": int(QualityFlag.OK),
            "anchor_mode": AnchorMode.FIXED,
        })
