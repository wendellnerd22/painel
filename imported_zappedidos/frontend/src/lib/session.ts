import { useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface SessionUser {
  id: string;
  email: string;
  nome: string;
  role: string;
  store_id: string | null;
}

export const ME_KEY = ["me"];

export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: () => apiGet<SessionUser>("/auth/me"),
    retry: false,
    staleTime: 60_000,
  });
}

/** Chame após um login bem-sucedido: recarrega quem sou eu e limpa cache antigo. */
export async function beginSession() {
  queryClient.clear();
  await queryClient.invalidateQueries({ queryKey: ME_KEY });
}

/** Único caminho de logout: encerra a sessão no servidor E limpa o cache local. */
export async function endSession(redirectTo = "/login") {
  try {
    await apiPost<void>("/auth/logout");
  } catch {
    // sessão já expirada no servidor — segue limpando o cliente
  } finally {
    queryClient.clear();
    window.location.href = redirectTo; // reset duro de todo o estado em memória
  }
}
