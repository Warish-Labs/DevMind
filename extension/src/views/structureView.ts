import * as vscode from "vscode";
import { FindingsSource, ProjectModule, RouteDetail } from "../types";

export type StructureTreeItem = ModuleTreeItem | RouteTreeItem | EmptyStructureTreeItem;

export class ModuleTreeItem extends vscode.TreeItem {
  constructor(public readonly module: ProjectModule) {
    super(`Module: ${module.name}`, vscode.TreeItemCollapsibleState.Expanded);

    this.description = `${module.routes.length} route(s)`;
    this.tooltip = `Module: ${module.name}\nSource: ${module.file}\nRoutes: ${module.routes.length}`;
    this.iconPath = new vscode.ThemeIcon("symbol-module");
    this.contextValue = "devmindModule";
    this.command = {
      command: "devmind.openFindingLocation",
      title: "Open Module File",
      arguments: [module.file, 1],
    };
  }
}

export class RouteTreeItem extends vscode.TreeItem {
  constructor(
    public readonly route: RouteDetail,
    public readonly moduleFile: string
  ) {
    super(`${route.method.toUpperCase()} ${route.path}`, vscode.TreeItemCollapsibleState.None);

    if (route.roleGuard) {
      this.description = "Protected [Role Checked]";
      this.iconPath = new vscode.ThemeIcon("shield");
    } else if (route.auth) {
      this.description = "Missing Role Guard";
      this.iconPath = new vscode.ThemeIcon(
        "warning",
        new vscode.ThemeColor("list.warningForeground")
      );
    } else {
      this.description = "Public / Unauthenticated";
      this.iconPath = new vscode.ThemeIcon("unlock");
    }

    this.tooltip = createRouteTooltip(route, moduleFile);
    this.contextValue = "devmindRoute";
    this.command = {
      command: "devmind.openFindingLocation",
      title: "Open Route Definition",
      arguments: [moduleFile, 1],
    };
  }
}

export class EmptyStructureTreeItem extends vscode.TreeItem {
  constructor() {
    super("No modules detected", vscode.TreeItemCollapsibleState.None);
    this.description = "Scan workspace to discover route architecture";
    this.iconPath = new vscode.ThemeIcon("info");
  }
}

function createRouteTooltip(route: RouteDetail, moduleFile: string): string {
  const parts = [
    `Route: ${route.method.toUpperCase()} ${route.path}`,
    `Source File: ${moduleFile}`,
    `Authentication: ${route.auth ? "Required" : "Public / None"}`,
    `Role Guard: ${route.roleGuard ? "Enforced" : route.auth ? "Missing (Vulnerability)" : "N/A"}`,
  ];

  if (route.findingId) {
    parts.push(`Associated Finding: ${route.findingId}`);
  }

  return parts.join("\n");
}

export class StructureViewProvider implements vscode.TreeDataProvider<StructureTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<StructureTreeItem | undefined | void> =
    new vscode.EventEmitter<StructureTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<StructureTreeItem | undefined | void> =
    this._onDidChangeTreeData.event;

  constructor(private findingsSource: FindingsSource) {}

  public refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  public getTreeItem(element: StructureTreeItem): vscode.TreeItem {
    return element;
  }

  public async getChildren(element?: StructureTreeItem): Promise<StructureTreeItem[]> {
    if (element instanceof ModuleTreeItem) {
      return element.module.routes.map((r) => new RouteTreeItem(r, element.module.file));
    }

    if (element instanceof RouteTreeItem || element instanceof EmptyStructureTreeItem) {
      return [];
    }

    // Root level: fetch structure
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const modules = await this.findingsSource.getStructure(workspaceRoot);

    if (!modules || modules.length === 0) {
      return [new EmptyStructureTreeItem()];
    }

    return modules.map((m) => new ModuleTreeItem(m));
  }
}
