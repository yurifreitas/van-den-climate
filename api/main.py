"""App FastAPI da Central de Risco Climatico RS.

Sobe com:
    uvicorn api.main:app --reload --port 8000

Prefixo /api/v1 fixo (regra §5.5 do contrato: qualquer alteracao de
contrato bumpa para /v2, nunca muda o /v1 in-place — quebraria o front que
ja fixou a versao). CORS restrito a localhost:5173 (regra §5.4) porque em
dev o front Vite roda so ali; abrir mais que isso e superficie de ataque
sem beneficio nesta fase.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import CONTRACT_VERSION
from api.models import MetaResponse
from api.routers import forecast, health, ledger, municipal, references, risk, state

app = FastAPI(
    title="Central de Risco Climatico RS — API",
    description="Camada de acesso a estado, previsao, risco e saude do dado, "
                 "conforme docs/API_CONTRACT.md.",
    version=CONTRACT_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    # Porta propria do projeto (5931), nao a default do Vite: default colide
    # com qualquer outro projeto aberto e o sintoma e enganoso.
    allow_origins=["http://localhost:5931", "http://127.0.0.1:5931"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(state.router, prefix=API_PREFIX)
app.include_router(forecast.router, prefix=API_PREFIX)
app.include_router(risk.router, prefix=API_PREFIX)
app.include_router(municipal.router, prefix=API_PREFIX)
app.include_router(ledger.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(references.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/meta", response_model=MetaResponse)
def get_meta() -> MetaResponse:
    """O front pinga isto no boot (regra §5.5) e avisa se a versao divergir
    da que ele espera — o mecanismo que permite o contrato evoluir sem
    quebrar silenciosamente um front ja publicado.
    """
    return MetaResponse(
        contract_version=CONTRACT_VERSION,
        api_prefix=API_PREFIX,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
