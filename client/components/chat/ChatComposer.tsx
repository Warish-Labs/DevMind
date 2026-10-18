"use client";

import React, { useState, useRef, useEffect } from "react";
import { Button } from "../ui/Button";
import { STARTER_PROMPTS } from "./types";

export interface ChatComposerProps {
  onSendMessage: (content: string) => void;
  onStopGeneration?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  showStarters?: boolean;
  className?: string;
}

export function ChatComposer({
  onSendMessage,
  onStopGeneration,
  isStreaming = false,
  disabled = false,
  showStarters = false,
  className = "",
}: ChatComposerProps) {
  const [content, setContent] = useState<string>("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [content]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isStreaming && onStopGeneration) {
      onStopGeneration();
      return;
    }
    const trimmed = content.trim();
    if (!trimmed || disabled) return;
    onSendMessage(trimmed);
    setContent("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSelectStarter = (promptText: string) => {
    setContent(promptText);
    textareaRef.current?.focus();
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Starter Prompts */}
      {showStarters && (
        <div className="space-y-1.5 select-none">
          <div className="text-[11px] font-mono text-[var(--fg-3)]">Suggested starter queries:</div>
          <div className="flex flex-wrap gap-1.5">
            {STARTER_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectStarter(prompt)}
                className="px-2.5 py-1 rounded-[var(--radius-chip)] bg-[var(--bg-1)] border border-[var(--line-1)] hover:border-[var(--line-strong)] text-[11px] text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors text-left"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Composer Box */}
      <form
        onSubmit={handleSubmit}
        className="rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-[var(--bg-1)] p-2 shadow-sm focus-within:border-[var(--ref)] focus-within:ring-1 focus-within:ring-[var(--ref)] transition-all"
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask Project Brain anything about code architecture, guards, or findings..."
          className="w-full bg-transparent px-2.5 py-1.5 text-xs text-[var(--fg-0)] placeholder-[var(--fg-3)] resize-none focus:outline-none max-h-36 font-sans leading-relaxed"
        />

        <div className="flex items-center justify-between pt-1 px-1 text-[11px] font-mono text-[var(--fg-3)]">
          <div className="flex items-center gap-2">
            <span>Shift + Enter for new line</span>
            <span>·</span>
            <span className="text-[var(--signal)]">AST Grounded</span>
          </div>

          <div className="flex items-center gap-2">
            {isStreaming ? (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={onStopGeneration}
                className="h-7 text-xs px-2.5"
              >
                Stop
              </Button>
            ) : (
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={disabled || !content.trim()}
                className="h-7 text-xs px-3"
              >
                Ask Project
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
