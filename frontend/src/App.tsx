import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { ThemeProvider } from "@/context/ThemeContext";
import { ToastProvider } from "@/context/ToastContext";
import { AuthProvider } from "@/context/AuthContext";
import { SearchStoreProvider } from "@/context/SearchStoreContext";
import { CompareProvider } from "@/context/CompareContext";
import { SavedProductsProvider } from "@/context/SavedProductsContext";
import { AssistantChatProvider } from "@/context/AssistantChatContext";
import { CompareBar } from "@/components/compare/CompareBar";
import { CompareDialog } from "@/components/compare/CompareDialog";
import { AppLayout } from "@/components/layouts/AppLayout";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { SignupPage } from "@/pages/SignupPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";

const AssistantPage = lazy(() =>
  import("@/pages/AssistantPage").then((m) => ({ default: m.AssistantPage }))
);
const SearchPage = lazy(() =>
  import("@/pages/SearchPage").then((m) => ({ default: m.SearchPage }))
);
const RecommendationsPage = lazy(() =>
  import("@/pages/RecommendationsPage").then((m) => ({ default: m.RecommendationsPage }))
);
const SearchResultDetailPage = lazy(() =>
  import("@/pages/SearchResultDetailPage").then((m) => ({ default: m.SearchResultDetailPage }))
);
const ProductAnalyticsPage = lazy(() =>
  import("@/pages/ProductAnalyticsPage").then((m) => ({ default: m.ProductAnalyticsPage }))
);
const HistoryPage = lazy(() =>
  import("@/pages/HistoryPage").then((m) => ({ default: m.HistoryPage }))
);
const SavedPage = lazy(() =>
  import("@/pages/SavedPage").then((m) => ({ default: m.SavedPage }))
);
const AnalyticsPage = lazy(() =>
  import("@/pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage }))
);
const ProfilePage = lazy(() =>
  import("@/pages/ProfilePage").then((m) => ({ default: m.ProfilePage }))
);
const AboutPage = lazy(() => import("@/pages/AboutPage").then((m) => ({ default: m.AboutPage })));
const NotFoundPage = lazy(() =>
  import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage }))
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function RouteFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <SearchStoreProvider>
              <CompareProvider>
                <SavedProductsProvider>
                  <AssistantChatProvider>
                    <BrowserRouter>
                      <Suspense fallback={<RouteFallback />}>
                        <Routes>
                          <Route element={<AppLayout />}>
                            <Route index element={<LandingPage />} />
                            <Route path="login" element={<LoginPage />} />
                            <Route path="signup" element={<SignupPage />} />
                            <Route path="forgot-password" element={<ForgotPasswordPage />} />
                            <Route path="reset-password" element={<ResetPasswordPage />} />
                            <Route path="about" element={<AboutPage />} />

                            <Route element={<ProtectedRoute />}>
                              <Route path="search" element={<SearchPage />} />
                              <Route path="assistant" element={<AssistantPage />} />
                              <Route path="recommendations" element={<RecommendationsPage />} />
                              <Route path="saved" element={<SavedPage />} />
                              <Route path="history" element={<HistoryPage />} />
                              <Route path="results/:id" element={<SearchResultDetailPage />} />
                              <Route path="product-analytics" element={<ProductAnalyticsPage />} />
                              <Route path="analytics" element={<AnalyticsPage />} />
                              <Route path="profile" element={<ProfilePage />} />
                            </Route>

                            <Route path="*" element={<NotFoundPage />} />
                          </Route>
                        </Routes>
                      </Suspense>
                    </BrowserRouter>
                    <CompareBar />
                    <CompareDialog />
                  </AssistantChatProvider>
                </SavedProductsProvider>
              </CompareProvider>
            </SearchStoreProvider>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
