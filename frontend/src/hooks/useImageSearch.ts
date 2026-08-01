import { useMutation, useQueryClient } from "@tanstack/react-query";
import { searchByImage } from "@/services/searchService";
import type { SearchResponse, SortBy } from "@/types";
import { useState, useCallback } from "react";
import { queryKeys } from "@/hooks/queryKeys";

interface SearchByImageVars {
  file: File;
  sortBy?: SortBy | null;
}

export function useImageSearch() {
  const queryClient = useQueryClient();
  const [uploadProgress, setUploadProgress] = useState(0);

  const mutation = useMutation<SearchResponse, Error, SearchByImageVars>({
    mutationFn: ({ file, sortBy }) =>
      searchByImage(file, sortBy, (percent) => setUploadProgress(percent)),
    onMutate: () => setUploadProgress(0),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
      queryClient.invalidateQueries({ queryKey: ["history"] });
    },
  });

  const reset = useCallback(() => {
    setUploadProgress(0);
    mutation.reset();
  }, [mutation]);

  return {
    search: mutation.mutate,
    searchAsync: mutation.mutateAsync,
    data: mutation.data,
    error: mutation.error,
    isPending: mutation.isPending,
    isError: mutation.isError,
    isSuccess: mutation.isSuccess,
    uploadProgress,
    reset,
  };
}
