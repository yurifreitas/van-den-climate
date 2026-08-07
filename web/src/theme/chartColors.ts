/**
 * Compatibilidade — a paleta completa mora em `theme/palette.ts`.
 *
 * Este arquivo existia quando a regra era "so FRIO/QUENTE tem cor". A regra
 * mudou (DESIGN.md §1): agora ha escala sequencial, categorica e de estado.
 * Mantido como reexport para nao quebrar imports existentes; codigo novo deve
 * importar de `theme/palette`.
 */
export {
  FRIO,
  QUENTE,
  ABISSAL,
  CARTA,
  CARTA_ALTA,
  GIZ,
  BRUMA,
  BRUMA_FRACA,
  GRID,
  LINHA,
  CATEGORICO,
  ESTADO,
  NIVEL,
  NIVEL_LABEL,
  NIVEL_FRACAO,
  alpha,
  diverging,
  divergingValue,
  sequencial,
  rampaSequencial,
  categorico,
} from './palette';
