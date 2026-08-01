import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { queryKeys } from "@/hooks/queryKeys";
import * as personalizationService from "@/services/personalizationService";
import type { PreferencesUpdatePayload, PriceAlertCreatePayload, SavedProductCreatePayload } from "@/types";

export function useCategoryOptions() {
  return useQuery({
    queryKey: queryKeys.categoryOptions,
    queryFn: personalizationService.getCategoryOptions,
    staleTime: 10 * 60_000,
  });
}

export function usePreferences() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.preferences,
    queryFn: personalizationService.getPreferences,
    enabled: isAuthenticated,
    staleTime: 30_000,
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PreferencesUpdatePayload) => personalizationService.updatePreferences(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.preferences, data);
      queryClient.invalidateQueries({ queryKey: queryKeys.recommendations });
    },
  });
}

export function useRecommendations() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.recommendations,
    queryFn: personalizationService.getRecommendations,
    enabled: isAuthenticated,
    staleTime: 30_000,
  });
}

export function usePriceAlerts() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.priceAlerts,
    queryFn: personalizationService.getPriceAlerts,
    enabled: isAuthenticated,
    staleTime: 15_000,
  });
}

export function useCreatePriceAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PriceAlertCreatePayload) => personalizationService.createPriceAlert(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.priceAlerts });
    },
  });
}

export function useDeletePriceAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: number) => personalizationService.deletePriceAlert(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.priceAlerts });
    },
  });
}

export function useSavedProducts() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.savedProducts,
    queryFn: personalizationService.getSavedProducts,
    enabled: isAuthenticated,
    staleTime: 15_000,
  });
}

export function useSaveProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SavedProductCreatePayload) => personalizationService.saveProduct(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.savedProducts });
    },
  });
}

export function useUnsaveProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (savedId: number) => personalizationService.unsaveProduct(savedId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.savedProducts });
    },
  });
}

export function useNotifications() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.notifications,
    queryFn: personalizationService.getNotifications,
    enabled: isAuthenticated,
    staleTime: 15_000,
    refetchInterval: isAuthenticated ? 60_000 : false,
  });
}

export function useUnreadNotificationCount() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.notificationsUnreadCount,
    queryFn: personalizationService.getUnreadNotificationCount,
    enabled: isAuthenticated,
    staleTime: 15_000,
    refetchInterval: isAuthenticated ? 60_000 : false,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: number) => personalizationService.markNotificationRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
      queryClient.invalidateQueries({ queryKey: queryKeys.notificationsUnreadCount });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => personalizationService.markAllNotificationsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
      queryClient.invalidateQueries({ queryKey: queryKeys.notificationsUnreadCount });
    },
  });
}

export function useDeleteNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: number) => personalizationService.deleteNotification(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
      queryClient.invalidateQueries({ queryKey: queryKeys.notificationsUnreadCount });
    },
  });
}
