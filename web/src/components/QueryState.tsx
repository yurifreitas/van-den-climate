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
    return <p className="muted">carregando carta...</p>;
  }
  if (isError) {
    return <p className="muted">carta indisponivel — verifique a conexao com a API.</p>;
  }
  return <>{children}</>;
}
