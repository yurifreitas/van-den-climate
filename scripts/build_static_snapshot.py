"""Congela a API inteira em arquivos JSON, para a demo estatica do GitHub Pages.

Por que existe
==============

GitHub Pages serve arquivo estatico e nada mais — nao ha FastAPI, DuckDB nem
parquet do outro lado. Para que a demo publica mostre a central COMPLETA, e
nao uma casca com estado de carregamento eterno, a resposta de cada endpoint
e gravada em disco no momento do build e o front passa a le-las.

Por que via TestClient e nao via HTTP
=====================================

`TestClient` monta o app em processo: o snapshot sai da MESMA pilha de
routers, modelos e serializacao que a API real usa. Bater em `localhost:8437`
exigiria um servidor no ar durante o build (frágil no CI) e ainda deixaria a
duvida de estar capturando uma versao antiga que ficou rodando.

A regra que este script nao pode violar
=======================================

Snapshot e uma FOTOGRAFIA, com data. Um numero congelado que se apresenta
como atual e a falha mais cara possivel numa central de risco — pior que a
tela vazia que ele substitui. Por isso todo arquivo gerado carrega
`_snapshot`, com o instante da captura e o aviso de que os dados nao se
atualizam sozinhos; o front mostra isso numa faixa fixa.

Uso:
    python -m scripts.build_static_snapshot
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SAIDA = REPO_ROOT / "web" / "public" / "static-api"


def slug(path: str, params: dict[str, Any] | None = None) -> str:
    """Chave de arquivo para (rota, parametros).

    ESTA FUNCAO TEM UMA GEMEA em `web/src/api/client.ts`. As duas precisam
    concordar caractere a caractere — se divergirem, o front pede um arquivo
    que o build nao gerou e a demo quebra so em producao, que e o pior lugar
    para descobrir. Qualquer mudanca aqui exige mudanca la, e o teste
    `tests/test_static_snapshot.py` compara as duas implementacoes.
    """
    base = path.lstrip("/").replace("/", "_")
    if params:
        for chave in sorted(params):
            valor = params[chave]
            if valor is None:
                continue
            limpo = re.sub(r"[^A-Za-z0-9]+", "-", str(valor))
            base += f"~{chave}-{limpo}"
    return base


# Rotas a congelar. Enumeradas a mao, e nao descobertas do OpenAPI, porque o
# que importa nao e "toda rota existente" e sim "toda rota que o front chama,
# com os parametros que a interface realmente oferece". Um select com duas
# temporadas precisa das duas — descobrir isso do schema seria adivinhacao.
ROTAS: list[tuple[str, dict[str, Any] | None]] = [
    ("/meta", None),
    ("/state", None),
    ("/state/ruler", None),
    # sinais que EstadoView e o seletor de serie oferecem
    *[(f"/series/{s}", None) for s in ("oni", "sam", "soi", "nino34", "satl")],
    # temporadas do select de PrevisaoView e EvidenciaView
    *[
        (f"/forecast/{s}{sufixo}", None)
        for s in ("OND2026", "JFM2027")
        for sufixo in ("", "/attribution", "/analogs")
    ],
    ("/risk/hazards", None),
    ("/risk/current", None),
    ("/ledger", None),
    ("/ledger/skill", None),
    ("/health/sources", None),
    ("/health/coverage", None),
    ("/health/breaks", None),
    ("/references", None),
    ("/outlook/enso", None),
    ("/geo/municipios", None),
    ("/geo/aguas/meta", None),
    # os tres horizontes do seletor de cenario
    *[("/risk/municipal", {"cenario": c}) for c in ("atual", "ond2026", "estrutural")],
    ("/risk/municipal/cruzamento/aguas", {"limit": 30}),
    ("/resposta/municipios", None),
    ("/historico/chuva", None),
    *[("/plano", {"cenario": c}) for c in ("atual", "ond2026", "estrutural")],
    ("/recursos", None),
    ("/pessoal", None),
]

# Binarios servidos pela API que viram asset estatico.
BINARIOS: list[tuple[str, str]] = [("/geo/aguas.png", "geo_aguas.png")]


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from fastapi.testclient import TestClient

    from api.main import API_PREFIX, app

    capturado_em = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = TestClient(app)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir(parents=True, exist_ok=True)

    manifesto: dict[str, Any] = {
        "capturado_em": capturado_em,
        "aviso": (
            "Demo estatica: os dados sao uma fotografia tirada na data acima e NAO se "
            "atualizam sozinhos. Para dados vivos, rode a API local (.\\run.ps1)."
        ),
        "rotas": [],
    }
    falhas: list[str] = []

    for path, params in ROTAS:
        r = client.get(f"{API_PREFIX}{path}", params=params)
        nome = slug(path, params)
        if r.status_code != 200:
            falhas.append(f"{path} {params or ''} -> {r.status_code}")
            continue
        corpo = r.json()
        # Carimbo em TODA resposta: nenhum consumidor deve conseguir ler um
        # numero deste snapshot sem topar com a data em que ele parou.
        if isinstance(corpo, dict):
            corpo["_snapshot"] = {"capturado_em": capturado_em, "estatico": True}
        (SAIDA / f"{nome}.json").write_text(
            json.dumps(corpo, ensure_ascii=False), encoding="utf-8"
        )
        manifesto["rotas"].append({"path": path, "params": params, "arquivo": f"{nome}.json"})

    for path, destino in BINARIOS:
        r = client.get(f"{API_PREFIX}{path}")
        if r.status_code != 200:
            falhas.append(f"{path} -> {r.status_code}")
            continue
        (SAIDA / destino).write_bytes(r.content)
        manifesto["rotas"].append({"path": path, "params": None, "arquivo": destino})

    (SAIDA / "_manifest.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total = sum(f.stat().st_size for f in SAIDA.iterdir())
    print(f"[OK] {len(manifesto['rotas'])} rotas congeladas em {SAIDA}")
    print(f"     {total / 1024 / 1024:.1f} MB · capturado em {capturado_em}")

    if falhas:
        # Falha ALTA: um snapshot com buracos gera uma demo que quebra so em
        # producao. Melhor nao publicar do que publicar pela metade.
        print("\n[FALHA] rotas que nao responderam 200:", file=sys.stderr)
        for f in falhas:
            print(f"  {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
