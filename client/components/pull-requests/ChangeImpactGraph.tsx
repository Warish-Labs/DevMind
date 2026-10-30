"use client";

import React, { useState, useMemo } from "react";
import type { ChangeImpactReport } from "@devmind/common/api";
import { Badge } from "@/components/ui/Badge";
import { SearchIcon } from "@/components/shell/icons";
import { Input } from "@/components/ui/Input";
import { getRiskLevelBadgeVariant } from "./types";

interface ChangeImpactGraphProps {
  impact: ChangeImpactReport | Record<string, unknown>;
  riskLevel: string;
}

type NodeTypeFilter = "all" | "symbol" | "route" | "test" | "file" | "module";

export function ChangeImpactGraph({ impact, riskLevel }: ChangeImpactGraphProps) {
  const [filterType, setFilterType] = useState<NodeTypeFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const typedImpact = impact as Partial<ChangeImpactReport>;
  const directSymbols = useMemo(() => typedImpact.direct_symbols || [], [typedImpact]);
  const affectedModules = useMemo(() => typedImpact.affected_modules || [], [typedImpact]);
  const affectedRoutes = useMemo(() => typedImpact.affected_routes || [], [typedImpact]);
  const affectedTests = useMemo(() => typedImpact.affected_tests || [], [typedImpact]);
  const nodes = useMemo(() => typedImpact.dependency_graph_nodes || [], [typedImpact]);
  const edges = useMemo(() => typedImpact.dependency_graph_edges || [], [typedImpact]);
  const riskReasons = useMemo(() => typedImpact.risk_reasons || [], [typedImpact]);

  // Filter nodes
  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      if (filterType !== "all" && n.type !== filterType) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesLabel = n.label.toLowerCase().includes(q);
        const matchesPath = (n.file_path || "").toLowerCase().includes(q);
        const matchesId = n.id.toLowerCase().includes(q);
        if (!matchesLabel && !matchesPath && !matchesId) return false;
      }
      return true;
    });
  }, [nodes, filterType, searchQuery]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return nodes[0] || null;
    return nodes.find((n) => n.id === selectedNodeId) || null;
  }, [nodes, selectedNodeId]);

  // Edges connected to selected node
  const connectedEdges = useMemo(() => {
    if (!selectedNode) return [];
    return edges.filter((e) => e.from_node === selectedNode.id || e.to_node === selectedNode.id);
  }, [edges, selectedNode]);

  const getNodeTypeBadge = (nodeType: string) => {
    switch (nodeType) {
      case "symbol":
        return (
          <Badge variant="danger" size="sm">
            Symbol
          </Badge>
        );
      case "module":
        return (
          <Badge variant="warn" size="sm">
            Module
          </Badge>
        );
      case "route":
        return (
          <Badge variant="ref" size="sm">
            Route
          </Badge>
        );
      case "test":
        return (
          <Badge variant="signal" size="sm">
            Test
          </Badge>
        );
      case "file":
      default:
        return (
          <Badge variant="neutral" size="sm">
            {nodeType}
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Impact Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] p-3 rounded-lg">
          <span className="text-[10px] font-mono uppercase text-[var(--fg-2)]">Direct Symbols</span>
          <div className="text-xl font-bold font-mono text-[var(--danger)] mt-0.5">
            {directSymbols.length}
          </div>
        </div>
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] p-3 rounded-lg">
          <span className="text-[10px] font-mono uppercase text-[var(--fg-2)]">
            Impacted Modules
          </span>
          <div className="text-xl font-bold font-mono text-[var(--warn)] mt-0.5">
            {affectedModules.length}
          </div>
        </div>
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] p-3 rounded-lg">
          <span className="text-[10px] font-mono uppercase text-[var(--fg-2)]">API Routes</span>
          <div className="text-xl font-bold font-mono text-[var(--ref)] mt-0.5">
            {affectedRoutes.length}
          </div>
        </div>
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] p-3 rounded-lg">
          <span className="text-[10px] font-mono uppercase text-[var(--fg-2)]">Impacted Tests</span>
          <div className="text-xl font-bold font-mono text-[var(--signal)] mt-0.5">
            {affectedTests.length}
          </div>
        </div>
      </div>

      {/* Risk Reasons Callout */}
      {riskReasons.length > 0 && (
        <div className="p-4 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold text-[var(--fg-0)]">
              Change-Impact Blast Radius:
            </span>
            <Badge variant={getRiskLevelBadgeVariant(riskLevel)} size="sm">
              {riskLevel.toUpperCase()}
            </Badge>
          </div>
          <ul className="list-disc list-inside text-xs text-[var(--fg-2)] space-y-1">
            {riskReasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Graph Explorer Main Container */}
      <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg overflow-hidden">
        {/* Controls Bar */}
        <div className="p-3 border-b border-[var(--line-1)] bg-[var(--bg-0)] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Node Type Filter Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto text-xs">
            {(
              [
                { id: "all", label: "All Nodes" },
                { id: "symbol", label: "Symbols" },
                { id: "route", label: "Routes" },
                { id: "test", label: "Tests" },
                { id: "module", label: "Modules" },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                onClick={() => setFilterType(item.id)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  filterType === item.id
                    ? "bg-[var(--bg-2)] text-[var(--fg-0)] border border-[var(--line-2)] shadow-xs"
                    : "text-[var(--fg-2)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)]/40"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Search Node */}
          <div className="relative w-full md:w-60">
            <SearchIcon
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--fg-3)] pointer-events-none"
            />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter graph node..."
              className="pl-8 text-xs h-7"
            />
          </div>
        </div>

        {/* Master-Detail Split Pane */}
        <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-[var(--line-1)] min-h-[380px]">
          {/* Node List (Left Pane) */}
          <div className="lg:col-span-2 p-3 space-y-2 max-h-[460px] overflow-y-auto">
            {filteredNodes.length === 0 ? (
              <div className="p-8 text-center text-xs text-[var(--fg-2)]">
                No dependency nodes matching filter.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {filteredNodes.map((node) => {
                  const isSelected = selectedNode?.id === node.id;
                  return (
                    <button
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      className={`text-left p-3 rounded-lg border transition-all ${
                        isSelected
                          ? "bg-[var(--bg-2)] border-[var(--signal)] shadow-xs"
                          : "bg-[var(--bg-0)]/60 border-[var(--line-2)] hover:bg-[var(--bg-2)]/50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span
                          className="font-mono text-xs font-medium text-[var(--fg-0)] truncate"
                          title={node.label}
                        >
                          {node.label}
                        </span>
                        {getNodeTypeBadge(node.type)}
                      </div>
                      <div
                        className="text-[11px] font-mono text-[var(--fg-2)] truncate"
                        title={node.file_path || node.id}
                      >
                        {node.file_path || node.id}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Node Inspector & Connections (Right Pane) */}
          <div className="p-4 bg-[var(--bg-0)]/40 flex flex-col justify-between">
            {selectedNode ? (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[10px] font-mono uppercase text-[var(--fg-2)]">
                      Selected Node
                    </span>
                    {getNodeTypeBadge(selectedNode.type)}
                  </div>
                  <h4 className="font-mono text-xs font-bold text-[var(--fg-0)] break-all">
                    {selectedNode.label}
                  </h4>
                  {selectedNode.file_path && (
                    <p className="text-[11px] font-mono text-[var(--fg-2)] mt-1 break-all">
                      {selectedNode.file_path}
                    </p>
                  )}
                </div>

                {/* Subgraph Connections */}
                <div>
                  <span className="text-[10px] font-mono uppercase text-[var(--fg-2)] block mb-1.5">
                    Graph Relationships ({connectedEdges.length})
                  </span>
                  {connectedEdges.length > 0 ? (
                    <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                      {connectedEdges.map((edge, idx) => {
                        const isOutgoing = edge.from_node === selectedNode.id;
                        const relatedId = isOutgoing ? edge.to_node : edge.from_node;
                        const relatedLabel = relatedId.split(":").pop() || relatedId;
                        return (
                          <div
                            key={idx}
                            className="p-2 bg-[var(--bg-1)] border border-[var(--line-1)] rounded text-[11px] font-mono flex items-center justify-between"
                          >
                            <span className="text-[var(--fg-2)]">
                              {isOutgoing ? "→" : "←"} {edge.kind}
                            </span>
                            <span
                              className="text-[var(--fg-0)] truncate max-w-[140px]"
                              title={relatedId}
                            >
                              {relatedLabel}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--fg-2)] italic">No explicit edges recorded.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-[var(--fg-2)]">
                Select a graph node to inspect details.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
