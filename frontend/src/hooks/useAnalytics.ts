import { useQuery } from "@tanstack/react-query";
import { getAnalyticsSummary, getTrustedPlatforms } from "@/services/searchService";
import { queryKeys } from "@/hooks/queryKeys";
import { useAuth } from "@/context/AuthContext";

export function useAnalytics() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.analytics,
    queryFn: getAnalyticsSummary,
    staleTime: 30_000,
    enabled: isAuthenticated,
  });
}

export function useTrustedPlatforms() {
  return useQuery({
    queryKey: queryKeys.platforms,
    queryFn: getTrustedPlatforms,
    staleTime: 5 * 60_000,
  });
}
