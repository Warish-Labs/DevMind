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

    const apiBaseUrl = config.get<string>("apiBaseUrl", defaultApiUrl);
    const fixtureMode = config.get<boolean>("fixtureMode", defaultFixture);
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
