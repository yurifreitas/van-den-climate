"""API FastAPI da Central de Risco Climatico RS (ADR-013/014).

Fronteira estavel = docs/API_CONTRACT.md, nao o layout de Parquet. Este
pacote so pode falar com data/{raw,interim,features} e ledger/ via
`api/deps.py` — nenhum router le parquet diretamente, para que a troca de
storage nunca vaze para fora de `deps.py`.
"""
