"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent, Badge, Button, Dialog } from "@/components/ui";
import type { ExtensionDeviceItem } from "./types";

interface ExtensionDevicesPaneProps {
  devices: ExtensionDeviceItem[];
  onRevokeDevice?: (deviceId: string) => Promise<void> | void;
}

export function ExtensionDevicesPane({
  devices: initialDevices,
  onRevokeDevice,
}: ExtensionDevicesPaneProps) {
  const [devices, setDevices] = useState<ExtensionDeviceItem[]>(initialDevices);
  const [revokingDevice, setRevokingDevice] = useState<ExtensionDeviceItem | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);

  const handleConfirmRevoke = async () => {
    if (!revokingDevice) return;
    setIsRevoking(true);
    try {
      if (onRevokeDevice) {
        await onRevokeDevice(revokingDevice.id);
      }
      setDevices((prev) =>
        prev.map((d) =>
          d.id === revokingDevice.id
            ? {
                ...d,
                isRevoked: true,
                status: "revoked",
                revokedAt: new Date().toISOString(),
              }
            : d
        )
      );
      setRevokingDevice(null);
    } finally {
      setIsRevoking(false);
    }
  };

  const getPlatformLabel = (platform: string) => {
    if (platform.includes("linux")) return "Linux";
    if (platform.includes("darwin")) return "macOS";
    if (platform.includes("win32")) return "Windows";
    return platform;
  };

  return (
    <div className="space-y-6">
      <Card variant="elevated">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base font-semibold">
                  Authorized Extension Devices
                </CardTitle>
                <Badge variant="signal" size="sm">
                  S-11 Companion
                </Badge>
              </div>
              <p className="text-xs text-[var(--fg-2)] mt-0.5">
                Local VS Code extension installations connected to this workspace via scoped tokens
                (ADR-012).
              </p>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowConnectModal(true)}
              className="font-mono text-xs"
            >
              + Connect Device
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          <div className="overflow-x-auto">
            <table
              className="w-full text-left font-mono text-xs"
              data-testid="extension-devices-table"
            >
              <thead>
                <tr className="border-b border-[var(--line-1)] text-[var(--fg-2)] uppercase text-[10px] tracking-wider">
                  <th scope="col" className="py-2.5 px-3">
                    Device Name
                  </th>
                  <th scope="col" className="py-2.5 px-3">
                    Platform
                  </th>
                  <th scope="col" className="py-2.5 px-3">
                    Extension Version
                  </th>
                  <th scope="col" className="py-2.5 px-3">
                    VS Code
                  </th>
                  <th scope="col" className="py-2.5 px-3">
                    Last Heartbeat
                  </th>
                  <th scope="col" className="py-2.5 px-3">
                    Status
                  </th>
                  <th scope="col" className="py-2.5 px-3 text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {devices.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-[var(--fg-2)]">
                      No extension devices registered yet.
                    </td>
                  </tr>
                ) : (
                  devices.map((device) => {
                    const statusVariant =
                      device.status === "active"
                        ? "signal"
                        : device.status === "idle"
                          ? "warn"
                          : "danger";

                    return (
                      <tr
                        key={device.id}
                        className="hover:bg-[var(--bg-1)] transition-colors"
                        data-testid={`device-row-${device.id}`}
                      >
                        <td className="py-2.5 px-3 font-semibold text-[var(--fg-0)]">
                          <div className="flex flex-col">
                            <span>{device.name}</span>
                            <span className="text-[10px] text-[var(--fg-2)] font-normal">
                              {device.id.slice(0, 16)}...
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-[var(--fg-1)]">
                          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-2)] border border-[var(--line-1)] text-[11px]">
                            {getPlatformLabel(device.platform)}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-[var(--fg-1)]">
                          {device.extensionVersion}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--fg-2)]">
                          {device.vscodeVersion || "1.95+"}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--fg-2)] text-[11px]">
                          {device.lastSeenAt}
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge variant={statusVariant} size="sm">
                            {device.status.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {device.isRevoked ? (
                            <span className="text-[10px] text-[var(--fg-2)]">Revoked</span>
                          ) : (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => setRevokingDevice(device)}
                              className="text-red-400 hover:text-red-300 hover:border-red-400 text-[11px]"
                              data-testid={`revoke-btn-${device.id}`}
                            >
                              Revoke
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Revocation Confirmation Dialog */}
      <Dialog
        isOpen={Boolean(revokingDevice)}
        onClose={() => setRevokingDevice(null)}
        title="Revoke Extension Device Access"
        description={`Are you sure you want to revoke access for ${revokingDevice?.name || "this device"}?`}
        footer={
          <>
            <Button
              variant="secondary"
              size="default"
              onClick={() => setRevokingDevice(null)}
              disabled={isRevoking}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="default"
              onClick={handleConfirmRevoke}
              isLoading={isRevoking}
              data-testid="confirm-revoke-device-btn"
            >
              Confirm Revocation
            </Button>
          </>
        }
      >
        <div className="py-2 text-xs text-[var(--fg-2)] font-mono leading-relaxed space-y-2">
          <p>
            The device&apos;s active access and refresh tokens will be immediately invalidated in
            the database per <strong>ADR-012</strong>.
          </p>
          <p>
            Local scanning in VS Code will continue to function in offline mode, but background
            metadata sync and evidence lookups will require generating a new extension token.
          </p>
        </div>
      </Dialog>

      {/* Connect Device Instructions Modal */}
      <Dialog
        isOpen={showConnectModal}
        onClose={() => setShowConnectModal(false)}
        title="Connect VS Code Extension (Screen S-11)"
        description="Authenticate your local editor companion with the DevMind Project Brain."
        footer={
          <Button variant="primary" size="default" onClick={() => setShowConnectModal(false)}>
            Done
          </Button>
        }
      >
        <div className="space-y-4 py-2 font-mono text-xs">
          <div className="p-3 rounded bg-[var(--bg-1)] border border-[var(--line-1)] space-y-2">
            <div className="text-[var(--signal)] font-semibold">
              Step 1: Open VS Code Command Palette
            </div>
            <p className="text-[var(--fg-2)] text-[11px]">
              Press{" "}
              <kbd className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[var(--fg-0)]">
                Ctrl+Shift+P
              </kbd>{" "}
              or{" "}
              <kbd className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[var(--fg-0)]">
                Cmd+Shift+P
              </kbd>{" "}
              and run:
            </p>
            <div className="px-2 py-1 rounded bg-[var(--bg-0)] text-[var(--fg-0)] font-bold">
              DevMind: Connect to Web Workspace
            </div>
          </div>

          <div className="p-3 rounded bg-[var(--bg-1)] border border-[var(--line-1)] space-y-2">
            <div className="text-[var(--signal)] font-semibold">
              Step 2: Consented Sync Protocol
            </div>
            <p className="text-[var(--fg-2)] text-[11px]">
              The extension performs AST scanning locally. No code leaves your machine without
              explicit consent (ADR-034 / docs/07 §3).
            </p>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
