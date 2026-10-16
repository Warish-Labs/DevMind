import * as vscode from "vscode";

export class DevMindLogger {
  private static instance: DevMindLogger;
  private channel: vscode.OutputChannel;

  private constructor() {
    this.channel = vscode.window.createOutputChannel("DevMind");
  }

  public static get(): DevMindLogger {
    if (!DevMindLogger.instance) {
      DevMindLogger.instance = new DevMindLogger();
    }
    return DevMindLogger.instance;
  }

  public info(message: string, meta?: Record<string, unknown>): void {
    this.log("INFO", message, meta);
  }

  public warn(message: string, meta?: Record<string, unknown>): void {
    this.log("WARN", message, meta);
  }

  public error(message: string, meta?: Record<string, unknown>): void {
    this.log("ERROR", message, meta);
  }

  public show(): void {
    this.channel.show();
  }

  private log(
    level: "INFO" | "WARN" | "ERROR",
    message: string,
    meta?: Record<string, unknown>
  ): void {
    const timestamp = new Date().toISOString();
    let metaStr = "";
    if (meta && Object.keys(meta).length > 0) {
      try {
        metaStr = ` | ${JSON.stringify(meta)}`;
      } catch {
        metaStr = "";
      }
    }
    this.channel.appendLine(`[${timestamp}] [${level}] ${message}${metaStr}`);
  }
}
