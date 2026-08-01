import axios, { AxiosError } from "axios";
import type { ApiErrorBody } from "@/types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export const AUTH_TOKEN_STORAGE_KEY = "visualfind-token";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60_000,
});

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

apiClient.interceptors.request.use((config) => {
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const AUTH_EXPIRED_EVENT = "visualfind:auth-expired";

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response) {
      const isAuthRoute = (error.config?.url ?? "").includes("/api/auth/");
      if (error.response.status === 401 && !isAuthRoute) {
        window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
      }
      const detail = error.response.data?.detail;
      throw new ApiError(
        detail || `Request failed with status ${error.response.status}.`,
        error.response.status
      );
    }
    if (error.request) {
      throw new ApiError(
        "Couldn't reach the VisualFind backend. Make sure it's running and reachable at " +
          API_BASE_URL +
          ".",
        null
      );
    }
    throw new ApiError(error.message || "Something went wrong.", null);
  }
);
