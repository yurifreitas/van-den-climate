// Worker MSW para desenvolvimento sem a API rodando (a API pode nao estar pronta).
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
