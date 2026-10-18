"use client";

import React, { useEffect } from "react";
import { ErrorState } from "@/components/ui/ErrorState";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log sanitized error without leaking secrets or source code
    console.error("[DevMind Root Error]", {
      name: error.name,
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <div className="min-h-[50vh] flex items-center justify-center p-6">
      <ErrorState
        title="Application encountered an error"
        code="devmind.client.runtime_error"
        message={error.message || "An unexpected error occurred while rendering the page."}
        cause="A client-side component threw an unhandled exception or failed to resolve data."
        nextStep="You can attempt to reset the application state or return to the projects overview."
        requestId={error.digest}
        retry={reset}
        homeHref="/"
      />
    </div>
  );
}
