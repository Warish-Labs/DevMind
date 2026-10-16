/**
 * Motion Tokens Specification
 * Source of truth: docs/08-ui-ux-design-specification.md §7.1 and client/app/tokens.css
 */

export const MOTION_DURATIONS = {
  instant: 0,
  dur1: 90, // micro-interactions, hover states, toggles
  dur2: 160, // menus, tooltips, list updates
  dur3: 240, // dialogs, drawer panels
  dur4: 400, // page sections, graph transitions
  durStory: 800, // hero sequence & walkthrough steps
} as const;

export const MOTION_EASINGS = {
  easeOut: "cubic-bezier(0.2, 0, 0, 1)", // elements entering or responding to input
  easeIn: "cubic-bezier(0.4, 0, 1, 1)", // elements leaving
  easeMove: "cubic-bezier(0.4, 0, 0.2, 1)", // elements changing position or size
} as const;
