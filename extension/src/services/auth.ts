/**
 * DevMind Extension Authentication & SecretStorage Service (ADR-012, docs/07 §3).
 * Securely stores DevMind-issued scoped tokens in VS Code SecretStorage.
 * Handles automatic refresh token rotation and replay revocation handling.
 */

import * as vscode from "vscode";
import { DevMindLogger } from "./logger";
import { SettingsService } from "./settings";

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
  registrationId: string;
  expiresAt: number; // Epoch timestamp ms
}

export class ExtensionAuthService {
  private static instance: ExtensionAuthService | null = null;
  private secrets: vscode.SecretStorage;
  private logger = DevMindLogger.get();

  private static KEY_ACCESS_TOKEN = "devmind.accessToken";
  private static KEY_REFRESH_TOKEN = "devmind.refreshToken";
  private static KEY_REGISTRATION_ID = "devmind.registrationId";
  private static KEY_EXPIRES_AT = "devmind.tokenExpiresAt";

  constructor(secrets: vscode.SecretStorage) {
    this.secrets = secrets;
  }

  public static init(secrets: vscode.SecretStorage): ExtensionAuthService {
    ExtensionAuthService.instance = new ExtensionAuthService(secrets);
    return ExtensionAuthService.instance;
  }

  public static get(): ExtensionAuthService {
    if (!ExtensionAuthService.instance) {
      throw new Error("ExtensionAuthService has not been initialized with SecretStorage");
    }
    return ExtensionAuthService.instance;
  }

  public async saveTokens(tokens: {
    accessToken: string;
    refreshToken: string;
    registrationId: string;
    expiresIn: number; // Lifetime in seconds
  }): Promise<void> {
    const expiresAt = Date.now() + tokens.expiresIn * 1000;
    await this.secrets.store(ExtensionAuthService.KEY_ACCESS_TOKEN, tokens.accessToken);
    await this.secrets.store(ExtensionAuthService.KEY_REFRESH_TOKEN, tokens.refreshToken);
    await this.secrets.store(ExtensionAuthService.KEY_REGISTRATION_ID, tokens.registrationId);
    await this.secrets.store(ExtensionAuthService.KEY_EXPIRES_AT, String(expiresAt));

    this.logger.info("Extension tokens securely saved to SecretStorage", {
      registrationId: tokens.registrationId,
      expiresAt: new Date(expiresAt).toISOString(),
    });
  }

  public async getAccessToken(): Promise<string | null> {
    const accessToken = await this.secrets.get(ExtensionAuthService.KEY_ACCESS_TOKEN);
    if (!accessToken) {
      return null;
    }

    const expiresAtStr = await this.secrets.get(ExtensionAuthService.KEY_EXPIRES_AT);
    const expiresAt = expiresAtStr ? parseInt(expiresAtStr, 10) : 0;

    // Buffer: If token is valid for more than 60 seconds, use it
    const now = Date.now();
    if (expiresAt > now + 60_000) {
      return accessToken;
    }

    // Attempt automatic refresh rotation
    const refreshToken = await this.secrets.get(ExtensionAuthService.KEY_REFRESH_TOKEN);
    if (!refreshToken) {
      return null;
    }

    try {
      this.logger.info("Access token expired or expiring soon; attempting refresh rotation");
      const refreshed = await this.refreshTokens(refreshToken);
      if (refreshed) {
        return refreshed.accessToken;
      }
    } catch (err) {
      this.logger.warn("Failed to refresh token", { error: String(err) });
    }

    return null;
  }

  public async getRefreshToken(): Promise<string | null> {
    return (await this.secrets.get(ExtensionAuthService.KEY_REFRESH_TOKEN)) ?? null;
  }

  public async getRegistrationId(): Promise<string | null> {
    return (await this.secrets.get(ExtensionAuthService.KEY_REGISTRATION_ID)) ?? null;
  }

  public async isAuthenticated(): Promise<boolean> {
    const token = await this.getAccessToken();
    return token !== null;
  }

  public async clearTokens(): Promise<void> {
    await this.secrets.delete(ExtensionAuthService.KEY_ACCESS_TOKEN);
    await this.secrets.delete(ExtensionAuthService.KEY_REFRESH_TOKEN);
    await this.secrets.delete(ExtensionAuthService.KEY_REGISTRATION_ID);
    await this.secrets.delete(ExtensionAuthService.KEY_EXPIRES_AT);
    this.logger.info("Extension tokens cleared from SecretStorage");
  }

  public async refreshTokens(
    refreshToken: string
  ): Promise<{ accessToken: string; refreshToken: string } | null> {
    const settings = SettingsService.get();
    const endpoint = `${settings.apiBaseUrl}/ext/token/refresh`;

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        // Token revoked or expired; purge local tokens
        await this.clearTokens();
      }
      return null;
    }

    const data = (await res.json()) as {
      access_token: string;
      refresh_token: string;
      registration_id: string;
      expires_in: number;
    };

    await this.saveTokens({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      registrationId: data.registration_id,
      expiresIn: data.expires_in,
    });

    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    };
  }
}
