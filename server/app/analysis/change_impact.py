"""Change-impact analysis engine and subgraph dependency traversal (docs/01 CAP-06, docs/05 §6.5).

Analyzes modified files and unified diffs against Project Brain symbols and relationships,
traversing callers, importers, routes, tests, and documentation to compute structural impact.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.analysis.review_buddy import parse_unified_diff
from app.domain.pr_agent.schemas import (
    AffectedRouteItem,
    ChangeImpactReport,
    DirectSymbolItem,
    GraphEdgeItem,
    GraphNodeItem,
)
from app.persistence.models.brain import CodeRelationship, CodeSymbol

logger = logging.getLogger(__name__)

# Keywords signaling high/critical risk areas
_CRITICAL_KEYWORDS = frozenset(
    {
        "auth",
        "token",
        "crypto",
        "encryption",
        "permission",
        "password",
        "secret",
        "credential",
        "session",
    }
)
_HIGH_KEYWORDS = frozenset(
    {"alembic", "migration", "webhook", "celery", "worker", "queue", "billing", "oauth", "payment"}
)


class ChangeImpactAnalyzer:
    """Analyzes pull request diffs and Project Brain relationships to compute the change-impact graph."""

    def __init__(
        self,
        symbols: list[CodeSymbol | dict[str, Any]] | None = None,
        relationships: list[CodeRelationship | dict[str, Any]] | None = None,
        known_files: set[str] | None = None,
    ) -> None:
        self.symbols = symbols or []
        self.relationships = relationships or []
        self.known_files = known_files or set()

    def analyze(
        self,
        changed_files: list[str],
        diff_text: str = "",
        file_contents: dict[str, str] | None = None,
    ) -> ChangeImpactReport:
        """Execute full change-impact traversal and risk evaluation."""
        diff_files = parse_unified_diff(diff_text) if diff_text else []
        all_changed_paths = sorted(
            set(changed_files + [cf.path for cf in diff_files if not cf.is_deleted])
        )

        if not all_changed_paths and not diff_text:
            return ChangeImpactReport(
                changed_files=[],
                risk_level="low",
                risk_reasons=["Empty change set"],
            )

        # 1. Direct symbols in changed files
        direct_symbols = self._find_direct_symbols(all_changed_paths)

        # 2. Affected modules
        affected_modules = self._extract_affected_modules(all_changed_paths)

        # 3. Graph traversal: callers, importers, and dependents
        graph_nodes, graph_edges, dependent_modules = self._traverse_relationships(
            changed_files=all_changed_paths,
            direct_symbols=direct_symbols,
        )
        all_affected_modules = sorted(set(affected_modules + dependent_modules))

        # 4. Affected routes
        affected_routes = self._detect_affected_routes(
            changed_files=all_changed_paths,
            direct_symbols=direct_symbols,
            diff_text=diff_text,
            file_contents=file_contents,
        )

        # 5. Affected tests
        affected_tests = self._detect_affected_tests(
            changed_files=all_changed_paths,
            affected_modules=all_affected_modules,
        )

        # Connect affected routes and tests to graph
        for route in affected_routes:
            node_id = f"route:{route.method}:{route.path}"
            graph_nodes[node_id] = GraphNodeItem(
                id=node_id,
                label=f"{route.method} {route.path}",
                type="route",
                file_path=route.file_path,
            )
            file_node_id = f"file:{route.file_path}"
            graph_edges.append(
                GraphEdgeItem(from_node=file_node_id, to_node=node_id, kind="defines")
            )

        for test_file in affected_tests:
            node_id = f"test:{test_file}"
            graph_nodes[node_id] = GraphNodeItem(
                id=node_id,
                label=test_file.split("/")[-1],
                type="test",
                file_path=test_file,
            )
            # Find primary matching changed file to draw test edge
            for cf in all_changed_paths:
                mod_name = (
                    cf.split("/")[-1].replace(".py", "").replace(".ts", "").replace(".js", "")
                )
                if mod_name in test_file:
                    graph_edges.append(
                        GraphEdgeItem(from_node=node_id, to_node=f"file:{cf}", kind="tests")
                    )
                    break

        # 6. Compute risk assessment
        risk_level, risk_reasons = self._evaluate_risk(
            changed_files=all_changed_paths,
            affected_routes=affected_routes,
            affected_tests=affected_tests,
            diff_text=diff_text,
        )

        return ChangeImpactReport(
            changed_files=all_changed_paths,
            direct_symbols=direct_symbols,
            affected_modules=all_affected_modules,
            affected_routes=affected_routes,
            affected_tests=affected_tests,
            dependency_graph_nodes=list(graph_nodes.values()),
            dependency_graph_edges=graph_edges,
            risk_level=risk_level,
            risk_reasons=risk_reasons,
        )

    def _find_direct_symbols(self, changed_files: list[str]) -> list[DirectSymbolItem]:
        """Find symbols defined in changed files from Project Brain symbol list."""
        direct: list[DirectSymbolItem] = []
        changed_set = set(changed_files)

        for sym in self.symbols:
            file_path = self._get_sym_attr(sym, "file_path") or ""
            if file_path in changed_set or any(
                cf.endswith(file_path) for cf in changed_files if file_path
            ):
                direct.append(
                    DirectSymbolItem(
                        name=self._get_sym_attr(sym, "name") or "unknown",
                        kind=self._get_sym_attr(sym, "kind") or "function",
                        file_path=file_path,
                        symbol_key=self._get_sym_attr(sym, "symbol_key"),
                    )
                )

        return direct

    def _extract_affected_modules(self, changed_files: list[str]) -> list[str]:
        """Extract logical module names from file paths."""
        modules: set[str] = set()
        for f in changed_files:
            parts = f.replace("\\", "/").split("/")
            # e.g., server/app/api/review_rules.py -> app.api.review_rules
            if len(parts) > 1:
                modules.add("/".join(parts[:-1]))
            else:
                modules.add(".")
        return sorted(modules)

    def _traverse_relationships(
        self,
        changed_files: list[str],
        direct_symbols: list[DirectSymbolItem],
    ) -> tuple[dict[str, GraphNodeItem], list[GraphEdgeItem], list[str]]:
        """Traverse callers and importers of direct symbols using relationships."""
        nodes: dict[str, GraphNodeItem] = {}
        edges: list[GraphEdgeItem] = []
        dependent_modules: set[str] = set()

        # Add changed files as base nodes
        for f in changed_files:
            file_id = f"file:{f}"
            nodes[file_id] = GraphNodeItem(
                id=file_id,
                label=f.split("/")[-1],
                type="file",
                file_path=f,
            )

        # Add direct symbols as nodes
        sym_to_id: dict[str, str] = {}
        for s in direct_symbols:
            sym_id = f"symbol:{s.file_path}:{s.name}"
            sym_to_id[s.name] = sym_id
            nodes[sym_id] = GraphNodeItem(
                id=sym_id,
                label=s.name,
                type="symbol",
                file_path=s.file_path,
            )
            # Edge: file defines symbol
            edges.append(
                GraphEdgeItem(
                    from_node=f"file:{s.file_path}",
                    to_node=sym_id,
                    kind="defines",
                )
            )

        # Traverse relationships (callers & dependents)
        direct_symbol_names = {s.name for s in direct_symbols}
        for rel in self.relationships:
            from_name = self._get_rel_attr(rel, "from_symbol_name") or ""
            to_name = self._get_rel_attr(rel, "to_symbol_name") or ""
            kind = self._get_rel_attr(rel, "kind") or "calls"
            from_file = self._get_rel_attr(rel, "from_file_path") or ""

            if to_name in direct_symbol_names and from_name:
                # from_name is a caller of a modified symbol
                caller_node_id = f"symbol:{from_file}:{from_name}"
                if caller_node_id not in nodes:
                    nodes[caller_node_id] = GraphNodeItem(
                        id=caller_node_id,
                        label=from_name,
                        type="symbol",
                        file_path=from_file or None,
                    )
                if from_file:
                    dep_parts = from_file.replace("\\", "/").split("/")
                    if len(dep_parts) > 1:
                        dependent_modules.add("/".join(dep_parts[:-1]))

                target_id = sym_to_id.get(to_name)
                if target_id:
                    edges.append(
                        GraphEdgeItem(
                            from_node=caller_node_id,
                            to_node=target_id,
                            kind=kind,
                        )
                    )

        return nodes, edges, sorted(dependent_modules)

    def _detect_affected_routes(
        self,
        changed_files: list[str],
        direct_symbols: list[DirectSymbolItem],
        diff_text: str,
        file_contents: dict[str, str] | None = None,
    ) -> list[AffectedRouteItem]:
        """Detect REST API routes defined or modified in changed files."""
        routes: list[AffectedRouteItem] = []
        route_pattern = re.compile(
            r"""@(?:router|app)\.(get|post|put|patch|delete)\(\s*["']([^"']+)["']""",
            re.IGNORECASE,
        )

        # Search in file contents
        for file_path in changed_files:
            content = (file_contents or {}).get(file_path, "")
            if not content and diff_text:
                # Search in diff text for route decorators
                for line in diff_text.splitlines():
                    if line.startswith("+") and not line.startswith("+++"):
                        match = route_pattern.search(line)
                        if match:
                            method = match.group(1).upper()
                            path = match.group(2)
                            routes.append(
                                AffectedRouteItem(
                                    path=path,
                                    method=method,
                                    handler=f"{method} {path}",
                                    file_path=file_path,
                                )
                            )
            elif content:
                for match in route_pattern.finditer(content):
                    method = match.group(1).upper()
                    path = match.group(2)
                    routes.append(
                        AffectedRouteItem(
                            path=path,
                            method=method,
                            handler=f"{method} {path}",
                            file_path=file_path,
                        )
                    )

        return routes

    def _detect_affected_tests(
        self,
        changed_files: list[str],
        affected_modules: list[str],
    ) -> list[str]:
        """Detect existing test files covering modified files or modules."""
        affected: set[str] = set()

        for f in changed_files:
            if "test" in f.lower():
                affected.add(f)
                continue

            base = f.split("/")[-1].replace(".py", "").replace(".ts", "").replace(".js", "")
            expected_test_names = [f"test_{base}.py", f"{base}.test.ts", f"{base}.spec.ts"]

            # Match against known project files
            for kf in self.known_files:
                if any(t_name in kf for t_name in expected_test_names):
                    affected.add(kf)

        return sorted(affected)

    def _evaluate_risk(
        self,
        changed_files: list[str],
        affected_routes: list[AffectedRouteItem],
        affected_tests: list[str],
        diff_text: str,
    ) -> tuple[str, list[str]]:
        """Compute categorical risk level and human-readable risk reasons."""
        reasons: list[str] = []
        is_critical = False
        is_high = False

        # 1. Critical risk checks: auth, crypto, permissions
        for f in changed_files:
            lower = f.lower()
            if any(k in lower for k in _CRITICAL_KEYWORDS):
                is_critical = True
                reasons.append(f"Modifies security or authentication component: {f}")
            elif any(k in lower for k in _HIGH_KEYWORDS):
                is_high = True
                reasons.append(f"Modifies high-impact infrastructure/migration: {f}")

        # 2. Mutating API routes
        mutating_routes = [
            r for r in affected_routes if r.method in ("POST", "PUT", "PATCH", "DELETE")
        ]
        if mutating_routes:
            is_high = True
            reasons.append(f"Touches {len(mutating_routes)} mutating API route(s)")

        # 3. Test coverage gap
        test_files_changed = [f for f in changed_files if "test" in f.lower()]
        code_files_changed = [
            f
            for f in changed_files
            if not any(k in f.lower() for k in ("test", "doc", ".md", ".json"))
        ]

        if code_files_changed and not test_files_changed and not affected_tests:
            is_high = True
            reasons.append("Code changes lack accompanying test updates or matching test coverage")

        # 4. Large diff size
        if len(changed_files) > 15 or len(diff_text.splitlines()) > 600:
            is_high = True
            reasons.append(f"Large change surface: {len(changed_files)} files modified")

        # Default classification
        if is_critical:
            return "critical", reasons
        if is_high:
            return "high", reasons
        if code_files_changed:
            reasons.append("Contains standard application code changes")
            return "medium", reasons

        reasons.append("Documentation, config, or test-only changes")
        return "low", reasons

    @staticmethod
    def _get_sym_attr(sym: Any, attr: str) -> Any:
        if isinstance(sym, dict):
            return sym.get(attr)
        return getattr(sym, attr, None)

    @staticmethod
    def _get_rel_attr(rel: Any, attr: str) -> Any:
        if isinstance(rel, dict):
            return rel.get(attr)
        return getattr(rel, attr, None)
