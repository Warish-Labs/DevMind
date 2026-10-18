import React from "react";
import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import {
  Button,
  Badge,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Input,
  Skeleton,
  Dialog,
  Tabs,
  TabList,
  TabTrigger,
  TabContent,
  Tooltip,
} from "../components/ui";

describe("Base UI Components (docs/08 §3-§7, M8-01)", () => {
  describe("Button Component", () => {
    it("renders primary variant with proper tokens by default", () => {
      const html = renderToString(<Button>Analyze Project</Button>);
      expect(html).toContain("Analyze Project");
      expect(html).toContain("bg-[var(--signal)]");
      expect(html).toContain("text-[var(--bg-0)]");
      expect(html).toContain("rounded-[var(--radius-control)]");
    });

    it("renders secondary and destructive variants correctly", () => {
      const secHtml = renderToString(<Button variant="secondary">Cancel</Button>);
      expect(secHtml).toContain("border-[var(--line-3)]");

      const destHtml = renderToString(<Button variant="destructive">Delete Project</Button>);
      expect(destHtml).toContain("text-[var(--danger)]");
      expect(destHtml).toContain("border-[var(--danger)]");
    });

    it("renders loading spinner and sets disabled attribute", () => {
      const html = renderToString(<Button isLoading>Submit</Button>);
      expect(html).toContain("disabled");
      expect(html).toContain("Loading…");
      expect(html).toContain("animate-spin");
    });

    it("renders left and right icons", () => {
      const html = renderToString(
        <Button
          leftIcon={<span data-testid="left-icon">◀</span>}
          rightIcon={<span data-testid="right-icon">▶</span>}
        >
          Navigate
        </Button>
      );
      expect(html).toContain("left-icon");
      expect(html).toContain("right-icon");
    });
  });

  describe("Badge Component", () => {
    it("renders semantic glyphs and variants without color alone", () => {
      const signalBadge = renderToString(<Badge variant="signal">Verified</Badge>);
      expect(signalBadge).toContain("✓");
      expect(signalBadge).toContain("text-[var(--signal)]");

      const warnBadge = renderToString(<Badge variant="warn">Pending</Badge>);
      expect(warnBadge).toContain("▲");
      expect(warnBadge).toContain("text-[var(--warn)]");

      const dangerBadge = renderToString(<Badge variant="danger">Critical</Badge>);
      expect(dangerBadge).toContain("✕");
      expect(dangerBadge).toContain("text-[var(--danger)]");
    });

    it("supports evidence levels E0, E1, E2 with automatic tinting and mono formatting", () => {
      const e2 = renderToString(<Badge evidenceLevel="E2">AST Guard Verified</Badge>);
      expect(e2).toContain("E2 · AST Guard Verified");
      expect(e2).toContain("font-mono");
      expect(e2).toContain("text-[var(--danger)]");

      const e1 = renderToString(<Badge evidenceLevel="E1">Local Scan Finding</Badge>);
      expect(e1).toContain("E1 · Local Scan Finding");
      expect(e1).toContain("text-[var(--warn)]");
    });
  });

  describe("Card Component", () => {
    it("renders surface layers, headers, content, and footers", () => {
      const html = renderToString(
        <Card variant="default">
          <CardHeader>
            <CardTitle>Security Health</CardTitle>
            <CardDescription>Deterministic codebase assessment</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Score: 92/100</p>
          </CardContent>
          <CardFooter>
            <span>Updated 2m ago</span>
          </CardFooter>
        </Card>
      );
      expect(html).toContain("bg-[var(--bg-1)]");
      expect(html).toContain("Security Health");
      expect(html).toContain("Deterministic codebase assessment");
      expect(html).toContain("Score: 92/100");
      expect(html).toContain("Updated 2m ago");
    });
  });

  describe("Input Component", () => {
    it("renders accessible label linked to input id", () => {
      const html = renderToString(
        <Input id="proj-name" label="Project Name" placeholder="my-app" />
      );
      expect(html).toContain('for="proj-name"');
      expect(html).toContain('id="proj-name"');
      expect(html).toContain("Project Name");
    });

    it("renders inline error message with glyph and alert role", () => {
      const html = renderToString(
        <Input id="repo-url" label="Repository" error="Repository path is required" />
      );
      expect(html).toContain('aria-invalid="true"');
      expect(html).toContain('role="alert"');
      expect(html).toContain("Repository path is required");
      expect(html).toContain("✕");
      expect(html).toContain("border-[var(--danger)]");
    });
  });

  describe("Skeleton Component", () => {
    it("renders placeholder with pulse and reduced-motion immunity", () => {
      const html = renderToString(<Skeleton width="100%" height={24} />);
      expect(html).toContain('aria-hidden="true"');
      expect(html).toContain("bg-[var(--bg-2)]");
      expect(html).toContain("motion-reduce:animate-none");
    });
  });

  describe("Dialog Component", () => {
    it("returns null when not open", () => {
      const html = renderToString(
        <Dialog isOpen={false} onClose={() => {}} title="Confirm Action">
          Modal body
        </Dialog>
      );
      expect(html).toBe("");
    });

    it("renders accessible modal attributes when open", () => {
      const html = renderToString(
        <Dialog
          isOpen={true}
          onClose={() => {}}
          title="Confirm Action"
          description="Are you sure you want to delete this project?"
          footer={<Button variant="destructive">Confirm</Button>}
        >
          Modal body
        </Dialog>
      );
      expect(html).toContain('role="dialog"');
      expect(html).toContain('aria-modal="true"');
      expect(html).toContain('aria-labelledby="dialog-title"');
      expect(html).toContain('aria-describedby="dialog-description"');
      expect(html).toContain("Confirm Action");
      expect(html).toContain("Are you sure you want to delete this project?");
      expect(html).toContain("Confirm");
    });
  });

  describe("Tabs Component", () => {
    it("renders tablist and triggers with active signal indicator", () => {
      const html = renderToString(
        <Tabs defaultValue="findings">
          <TabList>
            <TabTrigger value="overview">Overview</TabTrigger>
            <TabTrigger value="findings">Findings</TabTrigger>
          </TabList>
          <TabContent value="overview">Overview pane</TabContent>
          <TabContent value="findings">Findings pane</TabContent>
        </Tabs>
      );
      expect(html).toContain('role="tablist"');
      expect(html).toContain('role="tab"');
      expect(html).toContain('aria-selected="true"');
      expect(html).toContain("bg-[var(--signal)]");
      expect(html).toContain("Findings pane");
      // Inactive tab content is not rendered
      expect(html).not.toContain("Overview pane");
    });
  });

  describe("Tooltip Component", () => {
    it("renders child trigger", () => {
      const html = renderToString(
        <Tooltip content="Deterministic finding based on AST proof">
          <button>Evidence Level</button>
        </Tooltip>
      );
      expect(html).toContain("Evidence Level");
    });
  });
});
