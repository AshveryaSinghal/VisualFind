import { apiClient } from "@/api/client";
import type {
  AISearchResponse,
  ChatMessage,
  ChatTurnResponse,
  SmartCompareRequestPayload,
  SmartCompareResponse,
  StructuredQuery,
} from "@/types";

export async function sendChatTurn(messages: ChatMessage[]): Promise<ChatTurnResponse> {
  const { data } = await apiClient.post<ChatTurnResponse>("/api/ai/chat", { messages });
  return data;
}

export async function runAISearch(structuredQuery: StructuredQuery): Promise<AISearchResponse> {
  const { data } = await apiClient.post<AISearchResponse>("/api/ai/search", {
    search_text: structuredQuery.search_text,
    category: structuredQuery.category,
    budget_max: structuredQuery.budget_max,
    budget_currency: structuredQuery.budget_currency,
    brand: structuredQuery.brand,
    preferences: structuredQuery.preferences,
  });
  return data;
}

export async function runTextSearch(query: string): Promise<AISearchResponse> {
  const { data } = await apiClient.post<AISearchResponse>("/api/ai/text-search", { query });
  return data;
}

export async function compareProducts(
  payload: SmartCompareRequestPayload
): Promise<SmartCompareResponse> {
  const { data } = await apiClient.post<SmartCompareResponse>("/api/ai/compare-products", {
    product_a: payload.product_a,
    product_b: payload.product_b,
    budget: payload.budget,
    budget_currency: payload.budget_currency,
    main_purpose: payload.main_purpose,
    preferred_brand: payload.preferred_brand,
    priority: payload.priority,
    special_preferences: payload.special_preferences,
  });
  return data;
}
