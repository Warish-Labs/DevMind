"use client";

import React from "react";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  circle?: boolean;
}

export function Skeleton({
  width,
  height,
  circle = false,
  className = "",
  style,
  ...props
}: SkeletonProps) {
  const inlineStyles: React.CSSProperties = {
    width,
    height,
    ...style,
  };

  return (
    <div
      aria-hidden="true"
      style={inlineStyles}
      className={`bg-[var(--bg-2)] ${
        circle ? "rounded-full" : "rounded-[var(--radius-control)]"
      } animate-pulse motion-reduce:animate-none ${className}`}
      {...props}
    />
  );
}
