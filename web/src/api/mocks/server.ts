// Servidor MSW para testes (Vitest, node environment).
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
