import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  triggerHomepageHealthCheck,
  HEALTH_CHECK_STORAGE_KEY,
  HEALTH_CHECK_WINDOW_MS,
} from "../lib/health/health-check";

describe("triggerHomepageHealthCheck", () => {
  let mockStorage: Record<string, string>;
  let storageInterface: Storage;

  beforeEach(() => {
    mockStorage = {};
    storageInterface = {
      getItem: (key: string) => mockStorage[key] ?? null,
      setItem: (key: string, value: string) => {
        mockStorage[key] = value;
      },
      removeItem: (key: string) => {
        delete mockStorage[key];
      },
      clear: () => {
        mockStorage = {};
      },
      key: () => null,
      length: 0,
    };
    vi.restoreAllMocks();
  });

  it("triggers health check when no previous check timestamp exists", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
    });
    vi.stubGlobal("fetch", fetchMock);

    const now = 1000000;
    const result = await triggerHomepageHealthCheck({
      apiBaseUrl: "https://api.devmind.warishlabs.in",
      storage: storageInterface,
      now: () => now,
    });

    expect(result.checked).toBe(true);
    expect(result.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.devmind.warishlabs.in/health",
      expect.any(Object)
    );
    expect(mockStorage[HEALTH_CHECK_STORAGE_KEY]).toBe(now.toString());
  });

  it("throttles health check within 1 hour window", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const baseTime = 1000000;
    mockStorage[HEALTH_CHECK_STORAGE_KEY] = baseTime.toString();

    // 30 minutes later
    const result = await triggerHomepageHealthCheck({
      storage: storageInterface,
      now: () => baseTime + 30 * 60 * 1000,
    });

    expect(result.checked).toBe(false);
    expect(result.skippedReason).toBe("throttled");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("triggers health check after 1 hour has elapsed", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
    });
    vi.stubGlobal("fetch", fetchMock);

    const baseTime = 1000000;
    mockStorage[HEALTH_CHECK_STORAGE_KEY] = baseTime.toString();

    // 61 minutes later
    const newTime = baseTime + HEALTH_CHECK_WINDOW_MS + 60000;
    const result = await triggerHomepageHealthCheck({
      storage: storageInterface,
      now: () => newTime,
    });

    expect(result.checked).toBe(true);
    expect(result.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(mockStorage[HEALTH_CHECK_STORAGE_KEY]).toBe(newTime.toString());
  });

  it("handles network failure gracefully without throwing", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("Network timeout / cold start"));
    vi.stubGlobal("fetch", fetchMock);

    const result = await triggerHomepageHealthCheck({
      storage: storageInterface,
      now: () => 1000000,
    });

    expect(result.checked).toBe(true);
    expect(result.status).toBe("network_error");
  });

  it("handles missing storage safely without throwing", async () => {
    const result = await triggerHomepageHealthCheck({
      storage: null,
    });

    expect(result.checked).toBe(false);
    expect(result.skippedReason).toBe("no_storage");
  });
});
