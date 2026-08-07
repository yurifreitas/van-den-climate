"""Camada 1 — ingestao escalavel com proveniencia (§6/§8.3).

Importar este pacote registra todos os ingestores concretos via
@register (efeito colateral do import, ver registry.py). cli.py e os
testes dependem disso.
"""
from src.ingest import cpc_aao, cpc_oni, cpc_soi, psl_nino  # noqa: F401  (registro por import)

__all__ = ["cpc_oni", "psl_nino", "cpc_soi", "cpc_aao"]
