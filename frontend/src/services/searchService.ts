import { apiClient } from "@/api/client";
import type {
  AnalyticsSummary,
  HistoryItem,
  SearchResponse,
  SortBy,
} from "@/types";

export async function searchByImage(
  file: File,
  sortBy?: SortBy | null,
  onUploadProgress?: (percent: number) => void
): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await apiClient.post<SearchResponse>("/api/search/image", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    params: sortBy ? { sort_by: sortBy } : undefined,
    onUploadProgress: (event) => {
      if (!onUploadProgress || !event.total) return;
      onUploadProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
  return data;
}

export async function getHistory(limit = 20): Promise<HistoryItem[]> {
  const { data } = await apiClient.get<HistoryItem[]>("/api/search/history", {
    params: { limit },
  });
  return data;
}

export async function getSearchDetail(
  searchId: number,
  sortBy?: SortBy | null
): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>(`/api/search/history/${searchId}`, {
    params: sortBy ? { sort_by: sortBy } : undefined,
  });
  return data;
}

export async function deleteHistoryItem(searchId: number): Promise<void> {
  await apiClient.delete(`/api/search/history/${searchId}`);
}

export async function clearHistory(): Promise<void> {
  await apiClient.delete("/api/search/history");
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  const { data } = await apiClient.get<AnalyticsSummary>("/api/search/analytics/summary");
  return data;
}

export async function getTrustedPlatforms(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>("/api/search/platforms");
  return data;
}
