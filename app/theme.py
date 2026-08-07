"""Direcao visual (§9.2).

Regra que nao se negocia: `FRIO` e `QUENTE` sao exclusivos do dado. Nenhum
elemento de interface usa essas duas cores. Assim, cor no front significa
sempre anomalia — nunca decoracao.
"""
from __future__ import annotations

ABISSAL = "#0F1518"  # fundo, grafite frio
CARTA = "#1B2429"    # superficie elevada
GIZ = "#D8DEE0"      # texto primario
BRUMA = "#7C8A90"    # texto secundario, eixos
FRIO = "#3E7FA8"     # anomalia negativa   — SOMENTE dado
QUENTE = "#C1553A"   # anomalia positiva   — SOMENTE dado

UI_COLORS = (ABISSAL, CARTA, GIZ, BRUMA)
DATA_COLORS = (FRIO, QUENTE)

FONT_DISPLAY = "Archivo Expanded"
FONT_BODY = "Inter Tight"
FONT_MONO = "IBM Plex Mono"  # numerais tabulares obrigatorios em tabela e eixo


def diverging(pct: float) -> str:
    """Percentil causal [0,1] -> cor da escala divergente, centrada em 0.5."""
    t = max(0.0, min(1.0, pct))
    base = FRIO if t < 0.5 else QUENTE
    alpha = abs(t - 0.5) * 2.0
    r, g, b = (int(base[i:i + 2], 16) for i in (1, 3, 5))
    br, bg, bb = (int(CARTA[i:i + 2], 16) for i in (1, 3, 5))
    mix = lambda c, bc: int(bc + (c - bc) * (0.25 + 0.75 * alpha))
    return f"#{mix(r, br):02X}{mix(g, bg):02X}{mix(b, bb):02X}"


CSS = f"""
<style>
  .stApp {{ background:{ABISSAL}; color:{GIZ}; }}
  h1,h2,h3 {{ font-family:"{FONT_DISPLAY}",system-ui; font-weight:700;
              letter-spacing:.02em; text-transform:uppercase; }}
  .stApp, p, li {{ font-family:"{FONT_BODY}",system-ui; }}
  code, .mono, table {{ font-family:"{FONT_MONO}",monospace;
                        font-variant-numeric:tabular-nums; }}
  .panel {{ background:{CARTA}; border:1px solid #253036; padding:1rem;
            border-radius:2px; }}
  .muted {{ color:{BRUMA}; font-size:.85rem; }}
  /* movimento apenas entre estados temporais, nunca ambiental */
  @media (prefers-reduced-motion: reduce) {{ * {{ animation:none!important;
                                                  transition:none!important; }} }}
</style>
"""
