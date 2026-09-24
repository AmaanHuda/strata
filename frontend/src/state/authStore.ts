/**
 * Authentication state store.
 * Manages access/refresh tokens in localStorage.
 * All backend API calls require a valid Bearer token.
 */
import { create } from "zustand";
import { loginUser, refreshToken, TokenResponse } from "@/api/strataBackend";

type AuthState = {
  accessToken: string | null;
  refreshTokenStr: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  hydrateFromStorage: () => void;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshTokenStr: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  hydrateFromStorage: () => {
    const token = localStorage.getItem("strata_access_token");
    const refresh = localStorage.getItem("strata_refresh_token");
    if (token) {
      set({ accessToken: token, refreshTokenStr: refresh, isAuthenticated: true });
    }
  },

  login: async (username: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const tokens: TokenResponse = await loginUser(username, password);
      localStorage.setItem("strata_access_token", tokens.access_token);
      localStorage.setItem("strata_refresh_token", tokens.refresh_token);
      set({
        accessToken: tokens.access_token,
        refreshTokenStr: tokens.refresh_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return true;
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || "Login failed. Check credentials.";
      set({ isLoading: false, error: msg, isAuthenticated: false });
      return false;
    }
  },

  logout: () => {
    localStorage.removeItem("strata_access_token");
    localStorage.removeItem("strata_refresh_token");
    set({ accessToken: null, refreshTokenStr: null, isAuthenticated: false, error: null });
  },
}));
