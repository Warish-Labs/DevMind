"use client";

import React, { useEffect, useRef, useState } from "react";

// Official Cloudflare dummy test sitekey (always passes)
export const CLOUDFLARE_TEST_SITE_KEY = "1x00000000000000000000AA";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement | string,
        params: {
          sitekey: string;
          callback?: (token: string) => void;
          "error-callback"?: (errorCode?: string) => void;
          "expired-callback"?: () => void;
          theme?: "light" | "dark" | "auto";
          action?: string;
          cData?: string;
          size?: "normal" | "compact" | "flexible";
        }
      ) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId?: string) => void;
      getResponse: (widgetId?: string) => string | undefined;
    };
  }
}

export interface TurnstileWidgetProps {
  siteKey?: string;
  onVerify: (token: string) => void;
  onError?: (errorCode?: string) => void;
  onExpire?: () => void;
  theme?: "light" | "dark" | "auto";
  size?: "normal" | "compact" | "flexible";
  className?: string;
}

const SCRIPT_ID = "cf-turnstile-script";
const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export function TurnstileWidget({
  siteKey,
  onVerify,
  onError,
  onExpire,
  theme = "dark",
  size = "normal",
  className = "",
}: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [scriptLoaded, setScriptLoaded] = useState<boolean>(
    () => typeof window !== "undefined" && Boolean(window.turnstile)
  );
  const [loadError, setLoadError] = useState<boolean>(false);

  const activeSiteKey =
    siteKey || process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || CLOUDFLARE_TEST_SITE_KEY;

  // Load the Turnstile explicit script once
  useEffect(() => {
    if (typeof window === "undefined" || window.turnstile) return;

    let script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement("script");
      script.id = SCRIPT_ID;
      script.src = SCRIPT_URL;
      script.async = true;
      script.defer = true;
      script.onload = () => setScriptLoaded(true);
      script.onerror = () => {
        setLoadError(true);
        onError?.("script-load-error");
      };
      document.head.appendChild(script);
    } else {
      const handleLoad = () => setScriptLoaded(true);
      script.addEventListener("load", handleLoad);
      return () => script?.removeEventListener("load", handleLoad);
    }
  }, [onError]);

  // Render the Turnstile widget inside the container
  useEffect(() => {
    if (!scriptLoaded || !containerRef.current || !window.turnstile) return;

    // Clean up any previously rendered widget
    if (widgetIdRef.current) {
      try {
        window.turnstile.remove(widgetIdRef.current);
      } catch {
        // Ignored
      }
      widgetIdRef.current = null;
    }

    try {
      const id = window.turnstile.render(containerRef.current, {
        sitekey: activeSiteKey,
        callback: (token: string) => {
          onVerify(token);
        },
        "error-callback": (errorCode?: string) => {
          onError?.(errorCode);
        },
        "expired-callback": () => {
          onExpire?.();
        },
        theme,
        size,
      });
      widgetIdRef.current = id;
    } catch {
      queueMicrotask(() => {
        setLoadError(true);
      });
      onError?.("render-error");
    }

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // Ignored
        }
        widgetIdRef.current = null;
      }
    };
  }, [scriptLoaded, activeSiteKey, onVerify, onError, onExpire, theme, size]);

  if (loadError) {
    return (
      <div
        role="alert"
        className="p-3 text-xs rounded-control bg-[var(--line-1)] border border-[var(--line-2)] text-[var(--fg-1)] font-mono"
      >
        Security challenge failed to load. Please refresh the page or disable content blockers.
      </div>
    );
  }

  return (
    <div
      role="region"
      aria-label="Security verification challenge"
      className={`min-h-[65px] flex items-center ${className}`}
    >
      <div ref={containerRef} />
    </div>
  );
}
