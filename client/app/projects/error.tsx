"use client";

import React, { useEffect } from "react";
import { ErrorState } from "@/components/ui/ErrorState";

export default function ProjectsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[DevMind Projects Error]", {
      name: error.name,
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <div className="py-12">
      <ErrorState
        title="Unable to load projects"
        code="devmind.projects.load_error"
        message={error.message || "Failed to load project catalog for this workspace."}
        cause="Network timeout, invalid API response, or insufficient workspace permissions."
        nextStep="Retry fetching the project directory or verify your workspace access."
        requestId={error.digest}
        retry={reset}
        homeHref="/workspaces"
      />
    </div>
  );
}
