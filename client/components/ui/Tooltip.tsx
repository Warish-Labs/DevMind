"use client";

import React, { useEffect, useRef, useState } from "react";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  position?: "top" | "bottom" | "left" | "right";
  delayMs?: number;
  className?: string;
}

export function Tooltip({
  content,
  children,
  position = "top",
  delayMs = 160,
  className = "",
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showTooltip = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delayMs);
  };

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        hideTooltip();
      }
    };

    if (isVisible) {
      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
      };
    }
  }, [isVisible]);

  return (
    <div
      className="relative inline-flex items-center"
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
    >
      {children}

      {isVisible && (
        <div
          role="tooltip"
          className={`absolute ${
            position === "right"
              ? "left-full top-1/2 -translate-y-1/2 ml-2"
              : position === "bottom"
                ? "top-full left-1/2 -translate-x-1/2 mt-2"
                : position === "left"
                  ? "right-full top-1/2 -translate-y-1/2 mr-2"
                  : "bottom-full left-1/2 -translate-x-1/2 mb-2"
          } px-2.5 py-1 z-40 bg-[var(--bg-2)] border border-[var(--line-2)] rounded-[var(--radius-control)] text-[12px] text-[var(--fg-0)] shadow-lg whitespace-nowrap pointer-events-none select-none animate-in fade-in duration-[var(--dur-2)] ${className}`}
        >
          {content}
        </div>
      )}
    </div>
  );
}
