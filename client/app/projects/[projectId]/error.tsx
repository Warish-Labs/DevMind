"use client";

import React, { useEffect } from "react";
import { ErrorState } from "@/components/ui/ErrorState";

export default function ProjectScopedError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[DevMind Project Scoped Error]", {
      name: error.name,
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  return (
    <div className="py-12">
      <ErrorState
        title="Project operation failed"
        code="devmind.project.scoped_error"
        message={error.message || "Failed to complete the requested project view or action."}
        cause="The target project resource could not be accessed, or an indexing service was unreachable."
        nextStep="Retry the action or return to the projects catalog."
        requestId={error.digest}
        retry={reset}
        homeHref="/projects"
      />
    </div>
  );
}
