import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { SearchResponse } from "@/types";

interface SearchStoreContextValue {
  pendingFile: File | null;
  setPendingFile: (file: File | null) => void;

  /** The most recent search result/error, kept here (not in SearchPage's
   * local state) specifically so it survives navigating away from /search
   * and back - e.g. checking whether a result is Saved and returning.
   * Local component state would be wiped on unmount; this context lives
   * for the whole app session (App.tsx), so it isn't. Cleared only by an
   * explicit "New search" action, or a full page reload. */
  lastSearchResult: SearchResponse | null;
  lastSearchError: string | null;
  setLastSearchResult: (result: SearchResponse | null) => void;
  setLastSearchError: (message: string | null) => void;
  clearLastSearch: () => void;

  /** An in-memory-only object URL for the photo the person searched with.
   * Used purely as a client-side display fallback (e.g. a result card
   * whose source page didn't expose a product image). It is never
   * uploaded or written to any storage beyond the browser tab's memory -
   * it's created with URL.createObjectURL and revoked as soon as it's
   * replaced or the search is cleared, so nothing persists. */
  queryImagePreviewUrl: string | null;
  setQueryImagePreviewFile: (file: File | null) => void;
}

const SearchStoreContext = createContext<SearchStoreContextValue | undefined>(undefined);

export function SearchStoreProvider({ children }: { children: ReactNode }) {
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [lastSearchResult, setLastSearchResultState] = useState<SearchResponse | null>(null);
  const [lastSearchError, setLastSearchErrorState] = useState<string | null>(null);
  const [queryImagePreviewUrl, setQueryImagePreviewUrlState] = useState<string | null>(null);
  const queryImagePreviewUrlRef = useRef<string | null>(null);

  // Creates a fresh, tab-local object URL for the given file and revokes
  // the previous one (if any) so we never accumulate blob URLs or keep
  // the uploaded photo around longer than it's needed for display.
  const setQueryImagePreviewFile = useCallback((file: File | null) => {
    setQueryImagePreviewUrlState((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      const next = file ? URL.createObjectURL(file) : null;
      queryImagePreviewUrlRef.current = next;
      return next;
    });
  }, []);

  // Revoke on final unmount (app close/navigation away) so the blob isn't
  // held past the session it was created for.
  useEffect(() => {
    return () => {
      if (queryImagePreviewUrlRef.current) URL.revokeObjectURL(queryImagePreviewUrlRef.current);
    };
  }, []);

  const setLastSearchResult = (result: SearchResponse | null) => {
    setLastSearchResultState(result);
    if (result) setLastSearchErrorState(null);
  };

  const setLastSearchError = (message: string | null) => {
    setLastSearchErrorState(message);
    if (message) setLastSearchResultState(null);
  };

  const clearLastSearch = () => {
    setLastSearchResultState(null);
    setLastSearchErrorState(null);
    setQueryImagePreviewFile(null);
  };

  const value = useMemo<SearchStoreContextValue>(
    () => ({
      pendingFile,
      setPendingFile,
      lastSearchResult,
      lastSearchError,
      setLastSearchResult,
      setLastSearchError,
      clearLastSearch,
      queryImagePreviewUrl,
      setQueryImagePreviewFile,
    }),
    [pendingFile, lastSearchResult, lastSearchError, queryImagePreviewUrl, setQueryImagePreviewFile]
  );

  return <SearchStoreContext.Provider value={value}>{children}</SearchStoreContext.Provider>;
}

export function useSearchStore(): SearchStoreContextValue {
  const ctx = useContext(SearchStoreContext);
  if (!ctx) throw new Error("useSearchStore must be used within a SearchStoreProvider");
  return ctx;
}
