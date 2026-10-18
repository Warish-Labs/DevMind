"use client";

import React, { useEffect, useRef } from "react";

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

export function Dialog({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  className = "",
}: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previouslyFocusedElement.current = document.activeElement as HTMLElement;

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
        }
      };

      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";

      // Focus modal container
      dialogRef.current?.focus();

      return () => {
        document.removeEventListener("keydown", handleKeyDown);
        document.body.style.overflow = "";
        previouslyFocusedElement.current?.focus();
      };
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[rgba(11,15,18,0.75)] backdrop-blur-sm transition-opacity duration-[var(--dur-2)] animate-in fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        aria-describedby={description ? "dialog-description" : undefined}
        tabIndex={-1}
        className={`relative w-full max-w-lg bg-[var(--bg-1)] border border-[var(--line-2)] rounded-[var(--radius-panel)] shadow-2xl focus:outline-none overflow-hidden ${className}`}
      >
        <div className="flex items-start justify-between px-6 pt-5 pb-4 border-b border-[var(--line-1)]">
          <div>
            <h2
              id="dialog-title"
              className="text-[17px] font-semibold text-[var(--fg-0)] leading-6"
            >
              {title}
            </h2>
            {description && (
              <p id="dialog-description" className="mt-1 text-[13px] text-[var(--fg-2)] leading-5">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] p-1 rounded-[var(--radius-control)] hover:bg-[var(--bg-2)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
            aria-label="Close dialog"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 text-[14px] text-[var(--fg-1)] leading-relaxed">{children}</div>

        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 bg-[var(--bg-0)] border-t border-[var(--line-1)]">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
