"use client";

import React, { useEffect, useRef, useState } from "react";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  delayMs?: number;
  className?: string;
}

export function Tooltip({ content, children, delayMs = 160, className = "" }: TooltipProps) {
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
          className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2.5 py-1 z-40 bg-[var(--bg-2)] border border-[var(--line-2)] rounded-[var(--radius-control)] text-[12px] text-[var(--fg-0)] shadow-lg whitespace-nowrap pointer-events-none select-none animate-in fade-in duration-[var(--dur-2)] ${className}`}
        >
          {content}
        </div>
      )}
    </div>
  );
}
