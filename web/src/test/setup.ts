import '@testing-library/jest-dom/vitest';
import { beforeAll, afterEach, afterAll } from 'vitest';
import { server } from '../api/mocks/server';

// MSW no ambiente de teste (node) — mesmos handlers usados em dev,
// garantindo que o teste exercite o mesmo contrato que o browser mockado.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
