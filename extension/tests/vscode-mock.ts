export const window = {
  createOutputChannel: (name: string) => ({
    name,
    appendLine: (_msg: string) => {},
    show: () => {},
    dispose: () => {},
  }),
  showInformationMessage: async (msg: string) => msg,
  showWarningMessage: async (msg: string) => msg,
  showErrorMessage: async (msg: string) => msg,
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
  workspaceFolders: undefined,
  getConfiguration: (_section: string) => ({
    get: <T>(_key: string, defaultValue: T): T => defaultValue,
  }),
  onDidChangeConfiguration: () => ({ dispose: () => {} }),
};

export const commands = {
  registerCommand: (_command: string, _callback: (...args: unknown[]) => unknown) => ({
    dispose: () => {},
  }),
  executeCommand: async (_command: string, ..._args: unknown[]) => {},
};

export const ProgressLocation = {
  Notification: 15,
};
