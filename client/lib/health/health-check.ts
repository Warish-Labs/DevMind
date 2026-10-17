/**
 * DevMind Homepage Best-Effort Health Check
 *
 * Requirements (Mid-Build Deployment Readiness):
 * - Non-blocking request to GET /health at most once per browser within a 1-hour window.
 * - Never delays rendering or interactivity.
 * - Handles cold starts, timeouts, and network failures silently without throwing.
 * - Independent of Clerk authentication and Turnstile.
 */

export const HEALTH_CHECK_STORAGE_KEY = "devmind:last_health_check_timestamp";
export const HEALTH_CHECK_WINDOW_MS = 60 * 60 * 1000; // 1 hour

export interface HealthCheckOptions {
  apiBaseUrl?: string;
  storage?: Storage | null;
  now?: () => number;
  timeoutMs?: number;
}

export interface HealthCheckResult {
  checked: boolean;
  status?: string;
  skippedReason?: "no_storage" | "throttled" | "storage_error";
}

export async function triggerHomepageHealthCheck(
  options: HealthCheckOptions = {}
): Promise<HealthCheckResult> {
  const {
    apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.devmind.warishlabs.in",
    storage = typeof window !== "undefined" ? window.localStorage : null,
    now = () => Date.now(),
    timeoutMs = 5000,
  } = options;

  if (!storage) {
    return { checked: false, skippedReason: "no_storage" };
  }

  try {
    const lastTimestampStr = storage.getItem(HEALTH_CHECK_STORAGE_KEY);
    const currentTime = now();

    if (lastTimestampStr) {
      const lastTimestamp = parseInt(lastTimestampStr, 10);
      if (!isNaN(lastTimestamp) && currentTime - lastTimestamp < HEALTH_CHECK_WINDOW_MS) {
        return { checked: false, skippedReason: "throttled" };
      }
    }

    // Set timestamp eagerly to prevent duplicate calls from multiple tabs
    storage.setItem(HEALTH_CHECK_STORAGE_KEY, currentTime.toString());

    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

    try {
      const targetUrl = `${apiBaseUrl.replace(/\/+$/, "")}/health`;
      const response = await fetch(targetUrl, {
        method: "GET",
        signal: controller?.signal,
        headers: { Accept: "application/json" },
        cache: "no-store",
      });

      if (timeoutId) clearTimeout(timeoutId);

      if (response.ok) {
        return { checked: true, status: "ok" };
      }
      return { checked: true, status: `http_${response.status}` };
    } catch {
      if (timeoutId) clearTimeout(timeoutId);
      return { checked: true, status: "network_error" };
    }
  } catch {
    return { checked: false, skippedReason: "storage_error" };
  }
}
