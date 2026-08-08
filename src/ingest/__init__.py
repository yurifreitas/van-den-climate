"""Camada 1 — ingestao com proveniencia (§6/§8.3).

DUAS FAMILIAS DE INGESTOR, E POR QUE ELAS NAO SE JUNTAM
=======================================================

**Serie temporal** (cpc_oni, cpc_soi, cpc_aao, psl_nino). Herdam
`base.Ingestor`, sao registradas via @register e rodam por
`python -m src.ingest.cli --all`. O contrato delas termina em
`validate_series`, isto e, no esquema (timestamp, value, quality_flag).

**Transversal** (ibge_rs, jrc_gsw, cnes_rs, osm_emergencia, ghcn_rs,
cpc_enso_advisory). NAO herdam `Ingestor` e NAO estao no registro: um retrato
municipal, um raster de agua ou um cadastro de estabelecimento nao tem
(timestamp, value) por linha, e forcar o esquema exigiria inventar um
timestamp — o tipo de metadado falso que a proveniencia existe para impedir.
Cada uma tem `python -m src.ingest.<modulo>` proprio.

O que as duas familias COMPARTILHAM, porque e o que importa: bruto imutavel em
`data/raw/<fonte>/<ts>/` com `provenance.json`, cache por janela, respeito a
`CLIMATE_OFFLINE=1`, e so entao o parse para `data/interim/`.

Consequencia pratica que precisa estar dita aqui: `cli --all` roda as QUATRO
series, nao "tudo". A ordem completa esta no README, e ha dependencia entre
elas — `ghcn_rs` e `risk.aguas` precisam da malha do `ibge_rs`.

Importar este pacote registra os ingestores de SERIE via @register (efeito
colateral do import, ver registry.py). cli.py e os testes dependem disso.
"""
from src.ingest import cpc_aao, cpc_oni, cpc_soi, psl_nino  # noqa: F401  (registro por import)

__all__ = ["cpc_oni", "psl_nino", "cpc_soi", "cpc_aao"]
