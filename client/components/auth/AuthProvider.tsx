"use client";

import React from "react";
import { ClerkProvider } from "@clerk/nextjs";

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (!publishableKey) {
    // Graceful fallback for test or unconfigured environments
    return <>{children}</>;
  }

  return (
    <ClerkProvider
      publishableKey={publishableKey}
      appearance={{
        variables: {
          colorPrimary: "var(--signal)",
          colorBackground: "var(--bg-0)",
          colorForeground: "var(--fg-0)",
          colorInput: "var(--bg-1)",
          colorInputForeground: "var(--fg-0)",
        },
      }}
    >
      {children}
    </ClerkProvider>
  );
}
