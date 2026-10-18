"use client";

import React, { forwardRef } from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "hollow";
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = "default", className = "", children, ...props }, ref) => {
    const variantStyles = {
      default: "bg-[var(--bg-1)] border border-[var(--line-1)]",
      elevated: "bg-[var(--bg-2)] border border-[var(--line-2)]",
      hollow: "bg-transparent border border-[var(--line-1)]",
    };

    return (
      <div
        ref={ref}
        className={`rounded-[var(--radius-panel)] transition-colors duration-[var(--dur-2)] ${variantStyles[variant]} ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className = "", children, ...props }, ref) => (
    <div
      ref={ref}
      className={`px-5 py-4 border-b border-[var(--line-1)] flex flex-col gap-1 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement> & { as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" }
>(({ as: Component = "h3", className = "", children, ...props }, ref) => (
  <Component
    ref={ref}
    className={`text-[16px] font-semibold text-[var(--fg-0)] tracking-tight leading-6 ${className}`}
    {...props}
  >
    {children}
  </Component>
));
CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className = "", children, ...props }, ref) => (
  <p ref={ref} className={`text-[13px] text-[var(--fg-2)] leading-5 ${className}`} {...props}>
    {children}
  </p>
));
CardDescription.displayName = "CardDescription";

export const CardContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className = "", children, ...props }, ref) => (
    <div ref={ref} className={`p-5 ${className}`} {...props}>
      {children}
    </div>
  )
);
CardContent.displayName = "CardContent";

export const CardFooter = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className = "", children, ...props }, ref) => (
    <div
      ref={ref}
      className={`px-5 py-3.5 border-t border-[var(--line-1)] flex items-center justify-between gap-3 text-[13px] text-[var(--fg-2)] ${className}`}
      {...props}
    >
      {children}
    </div>
  )
);
CardFooter.displayName = "CardFooter";
