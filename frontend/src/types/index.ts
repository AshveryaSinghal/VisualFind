
export type SortBy = "price_low" | "price_high" | "rating" | "reviews" | "platform";

export const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: "price_low", label: "Lowest price" },
  { value: "price_high", label: "Highest price" },
  { value: "rating", label: "Highest rated" },
  { value: "reviews", label: "Most reviews" },
  { value: "platform", label: "Platform (A-Z)" },
];

export type PriceSource =
  | "google_shopping"
  | "lens"
  | "structured_metadata"
  | "headless_browser"
  | "unavailable"
  | "cache"
  | string;

export interface PurchaseLink {
  platform: string;
  title: string;

  brand: string | null;

  price: string | null;
  currency: string | null;

  link: string;
  source_domain: string;
  thumbnail: string | null;

  rating: number | null;
  review_count: number | null;

  price_source: PriceSource | null;
  extraction_method: string | null;
  confidence_score: number | null;

  is_best_deal: boolean;
  savings: number | null;
  best_deal_reason: string | null;

  is_quick_commerce: boolean;
  delivery_estimate: string | null;
}

export interface PriceHistoryComparison {
  first_time: boolean;
  message: string;

  product_name: string | null;
  previous_price: number | null;
  previous_marketplace: string | null;
  previous_checked_at: string | null;

  current_price: number | null;
  current_marketplace: string | null;

  change_percent: number | null;
  direction: "up" | "down" | "same" | null;
}

export interface SearchResponse {
  search_id: number;
  best_guess_label: string | null;
  product_query: string | null;

  total_matches_found: number;
  trusted_matches_returned: number;
  priced_count: number;

  detected_brand: string | null;
  brand_confidence: number | null;
  official_domain: string | null;
  official_product_found: boolean;

  execution_time_ms: number | null;
  from_cache: boolean;

  results: PurchaseLink[];
  note: string | null;

  is_exact_match: boolean;
  fallback_query: string | null;
  price_history: PriceHistoryComparison | null;

  fastest_delivery: PurchaseLink | null;
}

export interface PriceTrendPoint {
  price: number;
  currency: string | null;
  marketplace: string;
  recorded_at: string;
}

export interface ReviewSentiment {
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
  basis: string;
  is_estimate: boolean;
  review_count_analyzed: number | null;
  sample_positive: string | null;
  sample_negative: string | null;
}

export interface ProductAnalyticsResponse {
  product_name: string;
  platform: string | null;
  thumbnail: string | null;
  current_price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;

  price_points: PriceTrendPoint[];
  has_price_trend: boolean;
  price_change_percent: number | null;
  price_direction: "up" | "down" | "same" | null;

  sentiment: ReviewSentiment | null;

  summary: string[];
  verdict: string;
}

export interface ProductAnalyticsQuery {
  title: string;
  platform?: string | null;
  price?: number | null;
  currency?: string | null;
  rating?: number | null;
  review_count?: number | null;
  thumbnail?: string | null;
  link?: string | null;
}

export interface SavedProduct {
  id: number;
  product_name: string;
  platform: string | null;
  price: number | null;
  currency: string | null;
  thumbnail: string | null;
  link: string | null;
  rating: number | null;
  review_count: number | null;
  created_at: string;
}

export interface SavedProductCreatePayload {
  product_name: string;
  platform?: string | null;
  price?: number | null;
  currency?: string | null;
  thumbnail?: string | null;
  link?: string | null;
  rating?: number | null;
  review_count?: number | null;
}

export interface HistoryItem {
  id: number;
  best_guess_label: string | null;
  product_query: string | null;
  result_count: number;
  filtered_count: number;
  priced_count: number;
  best_deal_platform: string | null;
  best_deal_price: number | null;
  detected_brand: string | null;
  brand_confidence: number | null;
  official_domain: string | null;
  execution_time_ms: number | null;
  created_at: string;
  thumbnail: string | null;
}

export interface NamedCount {
  name: string;
  count: number;
}

export interface DailySearchCount {
  date: string;
  count: number;
}

export interface BestDealFound {
  label: string;
  platform: string | null;
  price: number;
  search_id: number;
}

export interface AnalyticsSummary {
  total_searches: number;
  most_searched_products: NamedCount[];
  most_searched_platforms: NamedCount[];
  most_searched_brands: NamedCount[];
  average_search_time_ms: number | null;
  average_products_found: number | null;
  average_priced_products: number | null;

  total_products_found: number;
  price_hit_rate: number | null;
  official_match_rate: number | null;
  fastest_search_ms: number | null;
  searches_last_7_days: number;
  searches_by_day: DailySearchCount[];
  best_deal_found: BestDealFound | null;
  last_search_at: string | null;
}

export interface IndexStatsResponse {
  total_products: number;
  total_categories: number;
  total_brands: number;
  by_category: Record<string, number>;
  by_brand: Record<string, number>;
  by_source: Record<string, number>;

  products_with_embeddings: number;
  embedding_progress_pct: number;

  index_growth_last_24h: number;
  index_growth_last_7d: number;
  index_growth_by_day: DailySearchCount[];

  total_indexing_jobs: number;
  total_products_received: number;
  total_duplicates_removed: number;
  total_created: number;
  total_updated: number;
  duplicate_rate_pct: number | null;

  average_indexing_time_ms: number | null;
  indexing_runs_measured: number;
  average_indexing_time_by_source: Record<string, number>;

  total_searches: number;
  average_search_latency_ms: number | null;
  cache_hit_searches: number;
  cache_hit_rate_pct: number | null;
  internal_index_searches: number;
  internal_index_share_pct: number | null;
  lens_fallback_searches: number;
  lens_fallback_share_pct: number | null;

  top_searched_products: NamedCount[];
  top_searched_brands: NamedCount[];
}

export interface ApiErrorBody {
  detail: string;
}

export interface User {
  id: number;
  username: string | null;
  email: string;
  full_name: string | null;
  country_code: string | null;
  country_name: string | null;
  city: string | null;
  timezone: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ProfileUpdatePayload {
  full_name?: string | null;
  country_code?: string | null;
  country_name?: string | null;
  city?: string | null;
  timezone?: string | null;
}

export interface SignupPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

export interface UsernameAvailability {
  username: string;
  available: boolean;
  suggestions: string[];
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface StructuredQuery {
  category: string | null;
  budget_max: number | null;
  budget_currency: string | null;
  brand: string | null;
  preferences: string[];
  search_text: string;
}

export type ChatStatus = "collecting" | "ready";

export interface ChatTurnResponse {
  status: ChatStatus;
  assistant_message: string;
  structured_query: StructuredQuery | null;
}

export interface AIRecommendation {
  product: PurchaseLink | null;
  reason: string | null;
  why_it_matches: string | null;
  money_saved: number | null;
  is_official_store: boolean;
  alternatives: PurchaseLink[];
  is_exact_match: boolean;
  price_history: PriceHistoryComparison | null;
}

export interface AISearchResponse {
  search: SearchResponse;
  recommendation: AIRecommendation | null;
}

export const SUGGESTED_PROMPTS: string[] = [
  "I have oily skin and acne. Budget ₹1000.",
  "I need a laptop for machine learning under ₹90000.",
  "I need headphones for the gym.",
  "I need a gaming mouse under ₹3000.",
  "I need running shoes.",
  "I want a gift for my sister.",
];

export type ComparePriority = "price" | "quality";

export interface ComparePreferences {
  budget: number | null;
  budget_currency: string;
  main_purpose: string;
  preferred_brand: string | null;
  priority: ComparePriority;
  special_preferences: string | null;
}

export interface SmartCompareRequestPayload extends ComparePreferences {
  product_a: PurchaseLink;
  product_b: PurchaseLink;
}

export interface ProductValueScore {
  price_score: number;
  rating_score: number;
  reviews_score: number;
  overall_value_score: number;
}

export interface SmartCompareResponse {
  winner_index: 0 | 1;
  headline: string;
  personalized_reason: string;
  price_verdict: string;
  quality_verdict: string;
  value_verdict: string;
  feature_highlights_a: string[];
  feature_highlights_b: string[];
  value_scores_a: ProductValueScore;
  value_scores_b: ProductValueScore;
  confidence: number | null;
  used_ai: boolean;
}

export type ShoppingStyle = "lowest_price" | "highest_rating" | "best_value" | "premium";

export const SHOPPING_STYLE_OPTIONS: { value: ShoppingStyle; label: string; description: string }[] = [
  { value: "lowest_price", label: "Lowest price", description: "Show me the cheapest option first" },
  { value: "highest_rating", label: "Highest rating", description: "Show me the best-rated option first" },
  { value: "best_value", label: "Best value", description: "Balance price, rating, and reviews" },
  { value: "premium", label: "Premium products", description: "Show me higher-end options first" },
];

export interface CategoryOption {
  value: string;
  label: string;
}

export interface PreferencesUpdatePayload {
  favorite_categories: string[];
  preferred_platforms: string[];
  budget_min: number | null;
  budget_max: number | null;
  shopping_style: ShoppingStyle | null;
}

export interface Preferences {
  favorite_categories: string[];
  preferred_platforms: string[];
  budget_min: number | null;
  budget_max: number | null;
  shopping_style: ShoppingStyle | null;
  updated_at: string | null;
}

export type RecommendationReason = "search_history" | "viewed" | "category" | "compared" | "budget";

export interface RecommendationItem {
  reason_type: RecommendationReason;
  reason_text: string;
  category: string | null;
  product: PurchaseLink;
}

export interface RecommendationsResponse {
  items: RecommendationItem[];
  has_enough_signal: boolean;
  generated_at: string;
}

export interface PriceAlertCreatePayload {
  product_name: string;
  target_price: number;
  currency?: string | null;
  platform?: string | null;
  thumbnail?: string | null;
  link?: string | null;
}

export interface PriceAlert {
  id: number;
  product_name: string;
  target_price: number;
  currency: string | null;
  platform: string | null;
  thumbnail: string | null;
  link: string | null;
  is_active: boolean;
  triggered_at: string | null;
  triggered_price: number | null;
  created_at: string;
}

export interface AppNotification {
  id: number;
  alert_id: number | null;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}
