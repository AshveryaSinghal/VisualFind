export const queryKeys = {
  history: (limit: number) => ["history", limit] as const,
  searchDetail: (id: number, sortBy?: string | null) =>
    ["searchDetail", id, sortBy ?? "default"] as const,
  analytics: ["analytics"] as const,
  indexStats: ["indexStats"] as const,
  platforms: ["platforms"] as const,
  productAnalytics: (title: string, platform?: string | null) =>
    ["productAnalytics", title, platform ?? "any"] as const,
  preferences: ["preferences"] as const,
  categoryOptions: ["categoryOptions"] as const,
  recommendations: ["recommendations"] as const,
  priceAlerts: ["priceAlerts"] as const,
  savedProducts: ["savedProducts"] as const,
  notifications: ["notifications"] as const,
  notificationsUnreadCount: ["notifications", "unread-count"] as const,
};
