import type { ReactNode } from 'react';

/**
 * Wrapper generico de loading/erro. Erro de rede vira mensagem no
 * vernaculo do instrumento ("carta indisponivel"), nunca um stack trace —
 * mas tambem nunca escondido (regra 3 do contrato nao vale para o front:
 * a API garante 200 com basis:null, mas a REDE pode falhar antes disso).
 */
export function QueryState({
  isLoading,
  isError,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  children: ReactNode;
}) {
  if (isLoading) {
    return (
      <div className="query-skeleton" role="status" aria-label="carregando carta">
        <span className="skeleton query-skeleton__line query-skeleton__line--wide" />
        <span className="skeleton query-skeleton__line" />
        <span className="skeleton query-skeleton__line query-skeleton__line--short" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="query-error t-small" role="alert">
        carta indisponivel — falha ao consultar a API. Os demais paineis desta pagina
        continuam validos; tente recarregar em instantes.
      </p>
    );
  }
  return <>{children}</>;
}
