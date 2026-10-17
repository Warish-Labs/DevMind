import { describe, it, expect, vi, beforeEach } from "vitest";
import { ExtensionAuthService } from "../src/services/auth";
import { MockSecretStorage } from "./vscode-mock";
import * as vscode from "vscode";

describe("ExtensionAuthService (M3-06)", () => {
  let mockSecrets: MockSecretStorage;
  let authService: ExtensionAuthService;

  beforeEach(() => {
    mockSecrets = new MockSecretStorage();
    authService = ExtensionAuthService.init(mockSecrets as unknown as vscode.SecretStorage);
  });

  it("stores and retrieves access, refresh tokens, and registration ID", async () => {
    await authService.saveTokens({
      accessToken: "dme_at_test_access_token_12345",
      refreshToken: "dme_rt_test_refresh_token_67890",
      registrationId: "01920000-0000-7000-8000-000000000001",
      expiresIn: 3600,
    });

    const token = await authService.getAccessToken();
    expect(token).toBe("dme_at_test_access_token_12345");

    const refreshToken = await authService.getRefreshToken();
    expect(refreshToken).toBe("dme_rt_test_refresh_token_67890");

    const regId = await authService.getRegistrationId();
    expect(regId).toBe("01920000-0000-7000-8000-000000000001");

    const isAuth = await authService.isAuthenticated();
    expect(isAuth).toBe(true);
  });

  it("returns null when no token is stored", async () => {
    const token = await authService.getAccessToken();
    expect(token).toBeNull();

    const isAuth = await authService.isAuthenticated();
    expect(isAuth).toBe(false);
  });

  it("clears tokens cleanly on sign out", async () => {
    await authService.saveTokens({
      accessToken: "dme_at_temp_token",
      refreshToken: "dme_rt_temp_refresh",
      registrationId: "01920000-0000-7000-8000-000000000001",
      expiresIn: 3600,
    });

    expect(await authService.isAuthenticated()).toBe(true);

    await authService.clearTokens();

    expect(await authService.getAccessToken()).toBeNull();
    expect(await authService.getRefreshToken()).toBeNull();
    expect(await authService.getRegistrationId()).toBeNull();
    expect(await authService.isAuthenticated()).toBe(false);
  });

  it("automatically performs refresh rotation when access token is expired", async () => {
    // Store expired token
    const oldRefresh = "dme_rt_old_refresh_token";
    await mockSecrets.store("devmind.accessToken", "dme_at_expired_token");
    await mockSecrets.store("devmind.refreshToken", oldRefresh);
    await mockSecrets.store("devmind.registrationId", "01920000-0000-7000-8000-000000000001");
    // Expired 10 seconds ago
    await mockSecrets.store("devmind.tokenExpiresAt", String(Date.now() - 10_000));

    // Mock fetch for refresh endpoint
    const newAccessToken = "dme_at_new_rotated_token";
    const newRefreshToken = "dme_rt_new_rotated_refresh";

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
        registration_id: "01920000-0000-7000-8000-000000000001",
        expires_in: 3600,
      }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    const token = await authService.getAccessToken();

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/ext/token/refresh"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ refresh_token: oldRefresh }),
      })
    );

    expect(token).toBe(newAccessToken);
    expect(await authService.getRefreshToken()).toBe(newRefreshToken);

    vi.unstubAllGlobals();
  });

  it("purges local credentials if refresh fails with 401 token revoked", async () => {
    await mockSecrets.store("devmind.accessToken", "dme_at_expired_token");
    await mockSecrets.store("devmind.refreshToken", "dme_rt_revoked_token");
    await mockSecrets.store("devmind.tokenExpiresAt", String(Date.now() - 10_000));

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({
        code: "auth.token_revoked",
        detail: "Token reuse detected; registration has been revoked",
      }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    const token = await authService.getAccessToken();

    expect(token).toBeNull();
    // Verify tokens were cleared
    expect(await authService.getRefreshToken()).toBeNull();
    expect(await authService.isAuthenticated()).toBe(false);

    vi.unstubAllGlobals();
  });
});
