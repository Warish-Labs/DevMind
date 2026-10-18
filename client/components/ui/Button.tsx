"use client";

import React, { forwardRef } from "react";

export type ButtonVariant = "primary" | "secondary" | "tertiary" | "destructive";
export type ButtonSize = "sm" | "default" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--signal)] text-[var(--bg-0)] font-semibold hover:brightness-110 active:brightness-95 border border-transparent shadow-sm",
  secondary:
    "bg-transparent text-[var(--fg-0)] border border-[var(--line-3)] hover:bg-[var(--bg-2)] hover:border-[var(--fg-1)] active:bg-[var(--bg-1)]",
  tertiary:
    "bg-transparent text-[var(--fg-1)] border border-transparent hover:text-[var(--fg-0)] hover:underline hover:decoration-[var(--ref)] hover:underline-offset-4",
  destructive:
    "bg-transparent text-[var(--danger)] border border-[var(--danger)] hover:bg-[rgba(255,107,94,0.12)] active:bg-[var(--danger)] active:text-[var(--bg-0)]",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  default: "h-9 px-4 text-[14px] gap-2",
  lg: "h-11 px-5 text-[15px] gap-2.5 min-w-[44px]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "default",
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      className = "",
      children,
      type = "button",
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        className={`inline-flex items-center justify-center font-sans rounded-[var(--radius-control)] transition-colors duration-[var(--dur-2)] ease-[var(--ease-out)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)] select-none disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <span className="inline-flex items-center gap-1.5" aria-hidden="true">
            <svg
              className="animate-spin h-4 w-4 text-current"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>Loading…</span>
          </span>
        ) : (
          <>
            {leftIcon && <span className="shrink-0">{leftIcon}</span>}
            <span>{children}</span>
            {rightIcon && <span className="shrink-0">{rightIcon}</span>}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = "Button";
