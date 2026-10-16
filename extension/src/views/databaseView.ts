import * as vscode from "vscode";
import { DatabaseField, DatabaseModel, FindingsSource } from "../types";

export type DatabaseTreeItem =
  DatabaseNoticeTreeItem | DatabaseModelTreeItem | DatabaseFieldTreeItem | EmptyDatabaseTreeItem;

export class DatabaseNoticeTreeItem extends vscode.TreeItem {
  constructor() {
    super("Discovered from files · Zero live connections", vscode.TreeItemCollapsibleState.None);
    this.description = "ADR-034 enforced";
    this.tooltip =
      "All database schema information is discovered statically from repository files (Prisma, SQLAlchemy, migrations).\nDevMind strictly forbids live or production database connections.";
    this.iconPath = new vscode.ThemeIcon("info");
  }
}

export class DatabaseModelTreeItem extends vscode.TreeItem {
  constructor(public readonly model: DatabaseModel) {
    super(`Model: ${model.name}`, vscode.TreeItemCollapsibleState.Expanded);
    this.description = `${model.fields.length} fields · ${model.sourceFile}`;
    this.tooltip = `Model: ${model.name}\nSource: ${model.sourceFile}\nFields: ${model.fields.length}`;
    this.iconPath = new vscode.ThemeIcon("database");
    this.contextValue = "devmindDbModel";
    this.command = {
      command: "devmind.openFindingLocation",
      title: "Open Model File",
      arguments: [model.sourceFile, 1],
    };
  }
}

export class DatabaseFieldTreeItem extends vscode.TreeItem {
  constructor(public readonly field: DatabaseField) {
    super(`${field.name}: ${field.type}`, vscode.TreeItemCollapsibleState.None);

    const tags: string[] = [];
    if (field.isPrimary) tags.push("[PK]");
    if (field.isUnique) tags.push("[Unique]");
    if (field.isForeignKey) tags.push("[FK]");

    this.description = tags.join(" ");
    this.iconPath = field.isPrimary
      ? new vscode.ThemeIcon("key")
      : new vscode.ThemeIcon("symbol-field");
  }
}

export class EmptyDatabaseTreeItem extends vscode.TreeItem {
  constructor() {
    super("No database models discovered", vscode.TreeItemCollapsibleState.None);
    this.description = "Workspace contains no recognized schema definitions";
    this.iconPath = new vscode.ThemeIcon("info");
  }
}

export class DatabaseViewProvider implements vscode.TreeDataProvider<DatabaseTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<DatabaseTreeItem | undefined | void> =
    new vscode.EventEmitter<DatabaseTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<DatabaseTreeItem | undefined | void> =
    this._onDidChangeTreeData.event;

  constructor(private findingsSource: FindingsSource) {}

  public refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  public getTreeItem(element: DatabaseTreeItem): vscode.TreeItem {
    return element;
  }

  public async getChildren(element?: DatabaseTreeItem): Promise<DatabaseTreeItem[]> {
    if (element instanceof DatabaseModelTreeItem) {
      return element.model.fields.map((f) => new DatabaseFieldTreeItem(f));
    }

    if (
      element instanceof DatabaseNoticeTreeItem ||
      element instanceof DatabaseFieldTreeItem ||
      element instanceof EmptyDatabaseTreeItem
    ) {
      return [];
    }

    // Root level
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    const models = await this.findingsSource.getDatabaseModels(workspaceRoot);

    const items: DatabaseTreeItem[] = [new DatabaseNoticeTreeItem()];

    if (!models || models.length === 0) {
      items.push(new EmptyDatabaseTreeItem());
    } else {
      for (const m of models) {
        items.push(new DatabaseModelTreeItem(m));
      }
    }

    return items;
  }
}
