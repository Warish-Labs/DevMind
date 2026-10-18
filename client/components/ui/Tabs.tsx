"use client";

import React, { createContext, useContext, useState } from "react";

interface TabsContextValue {
  value: string;
  onChange: (val: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

export interface TabsProps {
  value?: string;
  defaultValue: string;
  onValueChange?: (val: string) => void;
  className?: string;
  children: React.ReactNode;
}

export function Tabs({ value, defaultValue, onValueChange, className = "", children }: TabsProps) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const activeValue = value !== undefined ? value : internalValue;

  const handleChange = (newVal: string) => {
    if (value === undefined) {
      setInternalValue(newVal);
    }
    onValueChange?.(newVal);
  };

  return (
    <TabsContext.Provider value={{ value: activeValue, onChange: handleChange }}>
      <div className={`flex flex-col w-full ${className}`}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabList({
  className = "",
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role="tablist"
      className={`flex items-center gap-1 border-b border-[var(--line-1)] overflow-x-auto ${className}`}
    >
      {children}
    </div>
  );
}

export interface TabTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabTrigger({ value, className = "", children, ...props }: TabTriggerProps) {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error("TabTrigger must be used within a Tabs component");
  }

  const isSelected = ctx.value === value;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isSelected}
      tabIndex={isSelected ? 0 : -1}
      onClick={() => ctx.onChange(value)}
      className={`relative px-4 py-2.5 text-[13px] font-medium transition-colors select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
        isSelected ? "text-[var(--fg-0)]" : "text-[var(--fg-2)] hover:text-[var(--fg-1)]"
      } ${className}`}
      {...props}
    >
      <span>{children}</span>
      {isSelected && (
        <span
          className="absolute bottom-0 left-0 right-0 h-[2px] bg-[var(--signal)]"
          aria-hidden="true"
        />
      )}
    </button>
  );
}

export interface TabContentProps {
  value: string;
  className?: string;
  children: React.ReactNode;
}

export function TabContent({ value, className = "", children }: TabContentProps) {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error("TabContent must be used within a Tabs component");
  }

  if (ctx.value !== value) {
    return null;
  }

  return (
    <div role="tabpanel" tabIndex={0} className={`py-4 focus-visible:outline-none ${className}`}>
      {children}
    </div>
  );
}
