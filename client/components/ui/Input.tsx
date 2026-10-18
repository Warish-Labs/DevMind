"use client";

import React, { forwardRef, useId } from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      helperText,
      error,
      leftIcon,
      rightIcon,
      id,
      className = "",
      disabled,
      required,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = error ? `${inputId}-error` : undefined;
    const helperId = helperText ? `${inputId}-helper` : undefined;

    return (
      <div className="flex flex-col gap-1.5 w-full text-left font-sans">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[13px] font-medium text-[var(--fg-1)] select-none flex items-center justify-between"
          >
            <span>
              {label}
              {required && (
                <span className="text-[var(--danger)] ml-1" aria-hidden="true">
                  *
                </span>
              )}
            </span>
          </label>
        )}

        <div className="relative flex items-center w-full">
          {leftIcon && (
            <span
              className="absolute left-3 text-[var(--fg-2)] pointer-events-none flex items-center justify-center shrink-0"
              aria-hidden="true"
            >
              {leftIcon}
            </span>
          )}

          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            required={required}
            aria-invalid={Boolean(error)}
            aria-describedby={errorId || helperId}
            className={`w-full h-9 bg-[var(--bg-2)] text-[var(--fg-0)] placeholder:text-[var(--fg-2)] text-[14px] rounded-[var(--radius-control)] border transition-colors duration-[var(--dur-2)] ${
              error
                ? "border-[var(--danger)] focus:border-[var(--danger)] focus:ring-1 focus:ring-[var(--danger)]"
                : "border-[var(--line-3)] focus:border-[var(--ref)] focus:ring-1 focus:ring-[var(--ref)]"
            } ${leftIcon ? "pl-9" : "pl-3"} ${
              rightIcon ? "pr-9" : "pr-3"
            } focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
            {...props}
          />

          {rightIcon && (
            <span
              className="absolute right-3 text-[var(--fg-2)] flex items-center justify-center shrink-0"
              aria-hidden="true"
            >
              {rightIcon}
            </span>
          )}
        </div>

        {error ? (
          <p
            id={errorId}
            className="text-[12px] text-[var(--danger)] flex items-center gap-1 mt-0.5 leading-4"
            role="alert"
          >
            <span aria-hidden="true">✕</span>
            <span>{error}</span>
          </p>
        ) : helperText ? (
          <p id={helperId} className="text-[12px] text-[var(--fg-2)] mt-0.5 leading-4">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = "Input";
