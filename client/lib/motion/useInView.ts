"use client";

import { useEffect, useRef, useState } from "react";

export interface UseInViewOptions {
  threshold?: number | number[];
  rootMargin?: string;
  once?: boolean;
}

export function useInView<T extends HTMLElement = HTMLDivElement>({
  threshold = 0.15,
  rootMargin = "0px",
  once = true,
}: UseInViewOptions = {}) {
  const ref = useRef<T | null>(null);
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setIsInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsInView(true);
            if (once) {
              observer.unobserve(entry.target);
            }
          } else if (!once) {
            setIsInView(false);
          }
        });
      },
      { threshold, rootMargin }
    );

    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, [threshold, rootMargin, once]);

  return { ref, isInView };
}
