import * as vscode from "vscode";
import { ExtensionSettings, SyncMode } from "../types";

export class SettingsService {
  public static get(): ExtensionSettings {
    const config = vscode.workspace.getConfiguration("devmind");
    const defaultApiUrl =
      process.env.DEVMIND_DEFAULT_API_BASE_URL || "https://api.devmind.warishlabs.in/api/v1";
    const defaultFixture =
      process.env.DEVMIND_DEFAULT_FIXTURE_MODE !== undefined
        ? process.env.DEVMIND_DEFAULT_FIXTURE_MODE === "true"
        : process.env.DEVMIND_BUILD_MODE === "production"
          ? false
          : true;

    const isProdBuild = process.env.DEVMIND_BUILD_MODE === "production";
    const rawApiUrl = config.get<string>("apiBaseUrl");
    const rawFixture = config.get<boolean>("fixtureMode");

    const apiBaseUrl =
      isProdBuild &&
      (!rawApiUrl || rawApiUrl.includes("localhost") || rawApiUrl.includes("127.0.0.1"))
        ? defaultApiUrl
        : rawApiUrl || defaultApiUrl;

    const fixtureMode =
      isProdBuild && rawFixture === true
        ? false
        : rawFixture !== undefined
          ? rawFixture
          : defaultFixture;

    const syncMode = config.get<SyncMode>("syncMode", "metadata_only");
    const projectId = config.get<string>("projectId", "") || undefined;

    return {
      apiBaseUrl,
      fixtureMode,
      syncMode,
      projectId,
    };
  }

  public static onDidChange(callback: (settings: ExtensionSettings) => void): vscode.Disposable {
    return vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("devmind")) {
        callback(SettingsService.get());
      }
    });
  }
}
