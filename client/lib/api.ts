/**
 * Type-safe DevMind API client instance for Next.js web application.
 */

import { DevMindApiClient } from "@devmind/common/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000");

/**
 * Create a configured DevMindApiClient instance.
 * Accepts an optional token retriever function (e.g. from Clerk auth).
 */
export function createApiClient(getToken?: () => Promise<string | null> | string | null) {
  return new DevMindApiClient({
    baseUrl: API_BASE_URL,
    getToken,
  });
}

/**
 * Default unauthenticated singleton client for public endpoints.
 */
export const apiClient = createApiClient();
