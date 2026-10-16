export enum TreeItemCollapsibleState {
  None = 0,
  Collapsed = 1,
  Expanded = 2,
}

export class ThemeColor {
  constructor(public readonly id: string) {}
}

export class ThemeIcon {
  constructor(
    public readonly id: string,
    public readonly color?: ThemeColor
  ) {}
}

export class TreeItem {
  public description?: string;
  public tooltip?: string | unknown;
  public iconPath?: ThemeIcon | unknown;
  public command?: { command: string; title: string; arguments?: unknown[] };
  public contextValue?: string;

  constructor(
    public label: string | { label: string },
    public collapsibleState: TreeItemCollapsibleState = TreeItemCollapsibleState.None
  ) {}
}

export class EventEmitter<T> {
  private listeners: ((e: T) => void)[] = [];

  public event = (listener: (e: T) => void) => {
    this.listeners.push(listener);
    return {
      dispose: () => {
        const index = this.listeners.indexOf(listener);
        if (index >= 0) {
          this.listeners.splice(index, 1);
        }
      },
    };
  };

  public fire(data?: T): void {
    for (const listener of this.listeners) {
      listener(data as T);
    }
  }

  public dispose(): void {
    this.listeners = [];
  }
}

export class Position {
  constructor(
    public readonly line: number,
    public readonly character: number
  ) {}
}

export class Range {
  constructor(
    public readonly start: Position | number,
    public readonly end: Position | number,
    public readonly endLine?: number,
    public readonly endCharacter?: number
  ) {}
}

export const Uri = {
  file: (filePath: string) => ({
    fsPath: filePath,
    path: filePath,
    scheme: "file",
  }),
  parse: (uriString: string) => ({
    fsPath: uriString,
    path: uriString,
    scheme: "http",
  }),
};

export const window = {
  createOutputChannel: (name: string) => ({
    name,
    appendLine: (_msg: string) => {},
    show: () => {},
    dispose: () => {},
  }),
  showInformationMessage: async (msg: string, ..._items: unknown[]) => msg,
  showWarningMessage: async (msg: string, ..._items: unknown[]) => msg,
  showErrorMessage: async (msg: string, ..._items: unknown[]) => msg,
  showTextDocument: async (doc: unknown, _options?: unknown) => doc,
  registerTreeDataProvider: (_id: string, _provider: unknown) => ({
    dispose: () => {},
  }),
  withProgress: async <T>(
    _opts: unknown,
    task: (progress: {
      report: (value: { increment?: number; message?: string }) => void;
    }) => Promise<T>
  ): Promise<T> => {
    return task({ report: () => {} });
  },
};

export const workspace = {
  workspaceFolders: undefined as Array<{ uri: { fsPath: string } }> | undefined,
  getConfiguration: (_section: string) => ({
    get: <T>(_key: string, defaultValue: T): T => defaultValue,
  }),
  onDidChangeConfiguration: () => ({ dispose: () => {} }),
  openTextDocument: async (uriOrPath: unknown) => ({ uri: uriOrPath }),
};

export const commands = {
  registerCommand: (_command: string, _callback: (...args: unknown[]) => unknown) => ({
    dispose: () => {},
  }),
  executeCommand: async (_command: string, ..._args: unknown[]) => {},
};

export const env = {
  openExternal: async (_uri: unknown) => true,
};

export const ProgressLocation = {
  Notification: 15,
};
