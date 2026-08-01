import { apiClient } from "@/api/client";
import type { AuthResponse, ProfileUpdatePayload, User, UsernameAvailability } from "@/types";

export async function checkUsername(username: string): Promise<UsernameAvailability> {
  const { data } = await apiClient.get<UsernameAvailability>("/api/auth/check-username", {
    params: { username },
  });
  return data;
}

export async function signup(
  username: string,
  email: string,
  password: string,
  fullName?: string
): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/api/auth/signup", {
    username,
    email,
    password,
    full_name: fullName || undefined,
  });
  return data;
}

export async function login(identifier: string, password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/api/auth/login", { identifier, password });
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/api/auth/logout");
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/api/auth/me");
  return data;
}

export async function updateProfile(payload: ProfileUpdatePayload): Promise<User> {
  const { data } = await apiClient.put<User>("/api/auth/me", payload);
  return data;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  await apiClient.post("/api/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function forgotPassword(email: string): Promise<{ detail: string }> {
  const { data } = await apiClient.post<{ detail: string }>("/api/auth/forgot-password", {
    email,
  });
  return data;
}

export async function resetPassword(
  token: string,
  newPassword: string
): Promise<{ detail: string }> {
  const { data } = await apiClient.post<{ detail: string }>("/api/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return data;
}
