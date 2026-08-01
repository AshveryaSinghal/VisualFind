import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  clearHistory,
  deleteHistoryItem,
  getHistory,
  getSearchDetail,
} from "@/services/searchService";
import { queryKeys } from "@/hooks/queryKeys";
import { useAuth } from "@/context/AuthContext";
import type { SortBy } from "@/types";

export function useSearchHistory(limit = 50) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.history(limit),
    queryFn: () => getHistory(limit),
    staleTime: 15_000,
    enabled: isAuthenticated,
  });
}

export function useSearchDetail(searchId: number | null, sortBy?: SortBy | null) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.searchDetail(searchId ?? -1, sortBy),
    queryFn: () => getSearchDetail(searchId as number, sortBy),
    enabled: isAuthenticated && searchId !== null,
  });
}

export function useDeleteHistoryItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (searchId: number) => deleteHistoryItem(searchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["history"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

export function useClearHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => clearHistory(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["history"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}
