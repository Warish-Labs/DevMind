import * as vscode from "vscode";
import { ExtensionSettings, SyncMode } from "../types";

export class SettingsService {
  public static get(): ExtensionSettings {
    const config = vscode.workspace.getConfiguration("devmind");
    const apiBaseUrl = config.get<string>("apiBaseUrl", "http://localhost:8000/api/v1");
    const fixtureMode = config.get<boolean>("fixtureMode", true);
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
