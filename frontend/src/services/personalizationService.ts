import { apiClient } from "@/api/client";
import type {
  AppNotification,
  CategoryOption,
  Preferences,
  PreferencesUpdatePayload,
  PriceAlert,
  PriceAlertCreatePayload,
  RecommendationsResponse,
  SavedProduct,
  SavedProductCreatePayload,
} from "@/types";

export async function getCategoryOptions(): Promise<CategoryOption[]> {
  const { data } = await apiClient.get<CategoryOption[]>("/api/preferences/categories");
  return data;
}

export async function getPreferences(): Promise<Preferences> {
  const { data } = await apiClient.get<Preferences>("/api/preferences");
  return data;
}

export async function updatePreferences(payload: PreferencesUpdatePayload): Promise<Preferences> {
  const { data } = await apiClient.put<Preferences>("/api/preferences", payload);
  return data;
}

export async function getRecommendations(): Promise<RecommendationsResponse> {
  const { data } = await apiClient.get<RecommendationsResponse>("/api/recommendations");
  return data;
}

export async function saveProduct(payload: SavedProductCreatePayload): Promise<SavedProduct> {
  const { data } = await apiClient.post<SavedProduct>("/api/saved", payload);
  return data;
}

export async function getSavedProducts(): Promise<SavedProduct[]> {
  const { data } = await apiClient.get<SavedProduct[]>("/api/saved");
  return data;
}

export async function unsaveProduct(savedId: number): Promise<void> {
  await apiClient.delete(`/api/saved/${savedId}`);
}

export async function createPriceAlert(payload: PriceAlertCreatePayload): Promise<PriceAlert> {
  const { data } = await apiClient.post<PriceAlert>("/api/alerts", payload);
  return data;
}

export async function getPriceAlerts(): Promise<PriceAlert[]> {
  const { data } = await apiClient.get<PriceAlert[]>("/api/alerts");
  return data;
}

export async function deletePriceAlert(alertId: number): Promise<void> {
  await apiClient.delete(`/api/alerts/${alertId}`);
}

export async function getNotifications(): Promise<AppNotification[]> {
  const { data } = await apiClient.get<AppNotification[]>("/api/notifications");
  return data;
}

export async function getUnreadNotificationCount(): Promise<number> {
  const { data } = await apiClient.get<{ count: number }>("/api/notifications/unread-count");
  return data.count;
}

export async function markNotificationRead(notificationId: number): Promise<void> {
  await apiClient.post(`/api/notifications/${notificationId}/read`);
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiClient.post("/api/notifications/read-all");
}

export async function deleteNotification(notificationId: number): Promise<void> {
  await apiClient.delete(`/api/notifications/${notificationId}`);
}
