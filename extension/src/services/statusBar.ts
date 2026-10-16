import * as vscode from "vscode";

export type StatusBarState = "idle" | "scanning" | "offline" | "paused";

export class StatusBarService {
  private item: vscode.StatusBarItem;
  private state: StatusBarState = "idle";
  private isFixtureMode = true;

  constructor(isFixtureMode = true) {
    this.isFixtureMode = isFixtureMode;
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.item.command = "devmind.openFindings";
    this.updateDisplay();
    this.item.show();
  }

  public setFixtureMode(fixtureMode: boolean): void {
    this.isFixtureMode = fixtureMode;
    this.updateDisplay();
  }

  public setIdle(): void {
    this.state = "idle";
    this.updateDisplay();
  }

  public setScanning(current: number, total: number): void {
    this.state = "scanning";
    const modeTag = this.isFixtureMode ? "fixture" : "cloud";
    // Accessible text not color alone
    this.item.text = `$(sync~spin) DevMind · ${modeTag} · scanning ${current}/${total}`;
    this.item.tooltip = `DevMind Companion: Scanning AST routes and invariants (${current}/${total}). Click to view findings.`;
  }

  public setOffline(): void {
    this.state = "offline";
    this.updateDisplay();
  }

  public setPaused(): void {
    this.state = "paused";
    this.updateDisplay();
  }

  public dispose(): void {
    this.item.dispose();
  }

  public getItem(): vscode.StatusBarItem {
    return this.item;
  }

  private updateDisplay(): void {
    const modeTag = this.isFixtureMode ? "fixture" : "cloud";

    switch (this.state) {
      case "scanning":
        this.item.text = `$(sync~spin) DevMind · ${modeTag} · scanning`;
        this.item.tooltip = `DevMind Companion (${modeTag}): Active workspace analysis. Click to view findings.`;
        break;
      case "offline":
        this.item.text = `$(cloud-offline) DevMind · ${modeTag} · offline`;
        this.item.tooltip = `DevMind Companion (${modeTag}): Scanner offline. Analysis cached locally.`;
        break;
      case "paused":
        this.item.text = `$(shield) DevMind · ${modeTag} · sync paused`;
        this.item.tooltip = `DevMind Companion (${modeTag}): Synchronization paused. Findings remain local.`;
        break;
      case "idle":
      default:
        this.item.text = `$(shield) DevMind · ${modeTag} · idle`;
        this.item.tooltip = `DevMind Companion (${modeTag}): Ready. Click to view findings and architecture.`;
        break;
    }
  }
}
