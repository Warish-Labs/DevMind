"use client";

import React, { useEffect } from "react";
import { ErrorState } from "@/components/ui/ErrorState";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[DevMind Global Root Error]", {
      name: error.name,
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen flex items-center justify-center p-6 bg-[#0b0f12] text-[#e6edf3] font-sans antialiased">
        <ErrorState
          title="Critical root system error"
          code="devmind.client.global_failure"
          message={error.message || "A fatal layout or rendering failure occurred."}
          cause="The root document layout failed to initialize correctly."
          nextStep="Reload the page or contact system administration."
          requestId={error.digest}
          retry={reset}
          homeHref="/"
        />
      </body>
    </html>
  );
}
