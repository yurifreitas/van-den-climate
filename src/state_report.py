"""Estado do sistema — DERIVADO do dado, nunca escrito a mao.

Motivo de existir: o §2 do documento mestre foi escrito a mao e registrava
"Nino 3.4 ~ +0.7 e subindo". O ONI real, baixado em 2026-08-07, trazia +1.39
em MJJ/2026. Prosa sobre o estado do sistema envelhece em silencio e depois e
citada como se fosse medicao — exatamente a fronteira medido/prior que a
engine existe para tornar visivel.

    python -m src.state_report
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"

# Limiares operacionais da CPC para o ONI.
def _classify(v: float) -> str:
    a = abs(v)
    if a < 0.5:
        return "neutro"
    tier = "fraco" if a < 1.0 else "moderado" if a < 1.5 else "forte" if a < 2.0 else "muito forte"
    return f"El Nino {tier}" if v > 0 else f"La Nina {tier}"


def series(source_id: str, signal_id: str | None = None) -> pd.DataFrame:
    path = INTERIM / f"{source_id}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} ausente — rode `python -m src.ingest.cli --all`")
    df = pd.read_parquet(path)
    if signal_id:
        df = df[df["signal_id"] == signal_id]
    return df.dropna(subset=["value"]).sort_values("timestamp")


def report() -> str:
    oni = series("cpc_oni", "oni")
    last = oni.iloc[-1]
    # Tendencia sobre 3 temporadas: a taxa importa tanto quanto o nivel, porque
    # e ela que alimenta o operador de surpresa do bloco `enso_dynamics`.
    tail = oni.tail(4)["value"].to_numpy()
    rate = (tail[-1] - tail[0]) / (len(tail) - 1)

    lines = [
        "ESTADO DO SISTEMA — derivado, nao redigido",
        f"gerado de data/interim/ · ultima observacao {last['timestamp']:%Y-%m}",
        "",
        f"ONI            {last['value']:+.2f}  ({_classify(last['value'])})",
        f"tendencia      {rate:+.2f} C por temporada, ultimas 3",
        f"cobertura ONI  {oni['timestamp'].min():%Y-%m} .. {oni['timestamp'].max():%Y-%m}"
        f"  (n={len(oni)})",
    ]

    try:
        sam = series("cpc_aao", "sam_cpc_monthly")
        s = sam.iloc[-1]
        lines.append(f"SAM            {s['value']:+.3f}  ({s['timestamp']:%Y-%m})")
    except FileNotFoundError:
        lines.append("SAM            ausente")

    lines += [
        "",
        "Leitura: o nivel diz onde o sistema esta; a taxa diz se ele esta fora",
        "do envelope historico. Nenhum dos dois e previsao — sao medicao.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
