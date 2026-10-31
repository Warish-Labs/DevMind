"""Deterministic Evaluation and Release-Readiness Scoring Engine (docs/01 CAP-09, docs/03 §3.7, OQ-18)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Dimension weights summing to 1.0
DIMENSION_WEIGHTS: dict[str, float] = {
    "security": 0.25,
    "code_quality": 0.20,
    "testing": 0.20,
    "documentation": 0.15,
    "functionality": 0.10,
    "architecture": 0.10,
}


@dataclass
class FindingInput:
    """Security or quality finding summary input."""

    id: str
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    status: str  # open, confirmed, dismissed, fixed
    category: str = "security"  # security, quality, review


@dataclass
class BugRecordInput:
    """Bug memory recurring error input."""

    id: str
    title: str
    occurrence_count: int
    has_resolution: bool


@dataclass
class DocDriftInput:
    """Living documentation drift item input."""

    id: str
    kind: str  # undocumented_route, removed_route, missing_symbol, stale_section
    status: str  # detected, approved, rejected, applied
    explanation: str


@dataclass
class TestSignalInput:
    """Test suite and CI execution metrics."""

    __test__ = False

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    has_ci_run: bool = True


@dataclass
class FeatureChecklistInput:
    """Declared feature checklist item (per OQ-18)."""

    name: str
    completed: bool
    is_critical: bool = False


@dataclass
class TaskSummaryInput:
    """High-level summary of project backlog tasks."""

    total_tasks: int = 0
    completed_tasks: int = 0
    blocked_tasks: int = 0
    has_cyclic_dependency: bool = False


@dataclass
class EvaluationInputs:
    """Aggregated deterministic input payload for health and readiness evaluation."""

    findings: list[FindingInput] = field(default_factory=list)
    bugs: list[BugRecordInput] = field(default_factory=list)
    drift_items: list[DocDriftInput] = field(default_factory=list)
    test_signals: TestSignalInput = field(default_factory=TestSignalInput)
    feature_checklist: list[FeatureChecklistInput] = field(default_factory=list)
    task_summary: TaskSummaryInput = field(default_factory=TaskSummaryInput)
    has_tracked_docs: bool = True


@dataclass
class DimensionScore:
    """Calculated score and breakdown for a single health dimension."""

    score: float
    weight: float
    deductions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Final release-readiness verdict, composite scores, and blocker synthesis."""

    overall_score: float
    dimension_scores: dict[str, float]
    dimension_breakdown: dict[str, DimensionScore]
    verdict: str  # ready, ready_with_warnings, not_ready
    blockers: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    positive_indicators: list[str]
    functionality_confidence: str  # high or low (OQ-18)
    rubric_version: str = "1.0"


class ProjectEvaluationScorer:
    """Computes deterministic health scores across 6 dimensions and synthesizes release readiness."""

    RUBRIC_VERSION = "1.0"

    @classmethod
    def evaluate(cls, inputs: EvaluationInputs) -> EvaluationResult:
        """Execute full deterministic evaluation across all dimensions."""
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        positives: list[str] = []

        # 1. Security Dimension
        sec_score, sec_blockers, sec_warnings, sec_deductions = cls._score_security(inputs.findings)
        blockers.extend(sec_blockers)
        warnings.extend(sec_warnings)
        if not sec_blockers and not sec_warnings:
            positives.append("Zero open security findings detected")

        # 2. Code Quality Dimension
        qual_score, qual_blockers, qual_warnings, qual_deductions = cls._score_code_quality(
            inputs.findings, inputs.bugs
        )
        blockers.extend(qual_blockers)
        warnings.extend(qual_warnings)
        if not qual_blockers and qual_score >= 90.0:
            positives.append("Code quality and error memory maintain high stability")

        # 3. Testing Dimension
        test_score, test_blockers, test_warnings, test_deductions = cls._score_testing(
            inputs.test_signals
        )
        blockers.extend(test_blockers)
        warnings.extend(test_warnings)
        if inputs.test_signals.total_tests > 0 and inputs.test_signals.failed_tests == 0:
            positives.append(
                f"100% test pass rate across {inputs.test_signals.total_tests} test suites"
            )

        # 4. Documentation Dimension
        doc_score, doc_warnings, doc_deductions = cls._score_documentation(
            inputs.has_tracked_docs, inputs.drift_items
        )
        warnings.extend(doc_warnings)
        if inputs.has_tracked_docs and not doc_warnings:
            positives.append("Technical documentation is fully synchronized with code interface")

        # 5. Functionality Dimension (OQ-18)
        func_score, func_blockers, func_warnings, func_deductions, func_confidence = (
            cls._score_functionality(inputs.feature_checklist, inputs.task_summary)
        )
        blockers.extend(func_blockers)
        warnings.extend(func_warnings)
        if func_confidence == "high" and func_score >= 95.0:
            positives.append("All user-declared feature checklist milestones complete")

        # 6. Architecture Dimension
        arch_score, arch_blockers, arch_warnings, arch_deductions = cls._score_architecture(
            inputs.task_summary
        )
        blockers.extend(arch_blockers)
        warnings.extend(arch_warnings)
        if not arch_blockers and not inputs.task_summary.has_cyclic_dependency:
            positives.append("Architecture dependency graph is strictly acyclic")

        # Dimension breakdown
        breakdown = {
            "security": DimensionScore(
                score=sec_score,
                weight=DIMENSION_WEIGHTS["security"],
                deductions=sec_deductions,
            ),
            "code_quality": DimensionScore(
                score=qual_score,
                weight=DIMENSION_WEIGHTS["code_quality"],
                deductions=qual_deductions,
            ),
            "testing": DimensionScore(
                score=test_score,
                weight=DIMENSION_WEIGHTS["testing"],
                deductions=test_deductions,
            ),
            "documentation": DimensionScore(
                score=doc_score,
                weight=DIMENSION_WEIGHTS["documentation"],
                deductions=doc_deductions,
            ),
            "functionality": DimensionScore(
                score=func_score,
                weight=DIMENSION_WEIGHTS["functionality"],
                deductions=func_deductions,
                details={"confidence": func_confidence},
            ),
            "architecture": DimensionScore(
                score=arch_score,
                weight=DIMENSION_WEIGHTS["architecture"],
                deductions=arch_deductions,
            ),
        }

        # Composite score
        overall = sum(dim.score * dim.weight for dim in breakdown.values())
        overall = round(max(0.0, min(100.0, overall)), 1)

        dimension_scores = {k: v.score for k, v in breakdown.items()}

        # Release readiness verdict
        if blockers or overall < 70.0:
            verdict = "not_ready"
        elif warnings or overall < 85.0:
            verdict = "ready_with_warnings"
        else:
            verdict = "ready"

        return EvaluationResult(
            overall_score=overall,
            dimension_scores=dimension_scores,
            dimension_breakdown=breakdown,
            verdict=verdict,
            blockers=blockers,
            warnings=warnings,
            positive_indicators=positives,
            functionality_confidence=func_confidence,
            rubric_version=cls.RUBRIC_VERSION,
        )

    # -----------------------------------------------------------------------
    # Dimension Scorers
    # -----------------------------------------------------------------------

    @staticmethod
    def _score_security(
        findings: list[FindingInput],
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        score = 100.0
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        deductions: list[str] = []

        for f in findings:
            if f.category != "security":
                continue
            # Dismissed and fixed findings do not penalize security score
            if f.status in {"dismissed", "fixed"}:
                continue

            sev = f.severity.upper()
            if sev == "CRITICAL":
                score -= 35.0
                deductions.append(f"Critical vulnerability: {f.title} (-35)")
                blockers.append(
                    {
                        "id": f.id,
                        "dimension": "security",
                        "title": f.title,
                        "severity": "CRITICAL",
                        "detail": f"Open critical security finding: {f.title}",
                    }
                )
            elif sev == "HIGH":
                score -= 20.0
                deductions.append(f"High vulnerability: {f.title} (-20)")
                blockers.append(
                    {
                        "id": f.id,
                        "dimension": "security",
                        "title": f.title,
                        "severity": "HIGH",
                        "detail": f"Open high-severity security finding: {f.title}",
                    }
                )
            elif sev == "MEDIUM":
                score -= 10.0
                deductions.append(f"Medium vulnerability: {f.title} (-10)")
                warnings.append(
                    {
                        "id": f.id,
                        "dimension": "security",
                        "title": f.title,
                        "severity": "MEDIUM",
                        "detail": f"Unresolved medium finding: {f.title}",
                    }
                )
            elif sev == "LOW":
                score -= 3.0
                deductions.append(f"Low vulnerability: {f.title} (-3)")
                warnings.append(
                    {
                        "id": f.id,
                        "dimension": "security",
                        "title": f.title,
                        "severity": "LOW",
                        "detail": f"Low severity advisory: {f.title}",
                    }
                )

        return round(max(0.0, min(100.0, score)), 1), blockers, warnings, deductions

    @staticmethod
    def _score_code_quality(
        findings: list[FindingInput],
        bugs: list[BugRecordInput],
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        score = 100.0
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        deductions: list[str] = []

        # Quality & review findings
        for f in findings:
            if f.category not in {"quality", "review"}:
                continue
            if f.status in {"dismissed", "fixed"}:
                continue

            sev = f.severity.upper()
            if sev in {"CRITICAL", "HIGH"}:
                score -= 15.0
                deductions.append(f"High-severity review finding: {f.title} (-15)")
                warnings.append(
                    {
                        "id": f.id,
                        "dimension": "code_quality",
                        "title": f.title,
                        "severity": sev,
                        "detail": f"Review checklist violation: {f.title}",
                    }
                )
            elif sev == "MEDIUM":
                score -= 8.0
                deductions.append(f"Medium review finding: {f.title} (-8)")
            elif sev == "LOW":
                score -= 3.0
                deductions.append(f"Low review finding: {f.title} (-3)")

        # Unresolved recurring bugs from Bug Memory
        for bug in bugs:
            if not bug.has_resolution:
                if bug.occurrence_count >= 10:
                    score -= 15.0
                    deductions.append(
                        f"Severe recurring bug ({bug.occurrence_count}x): {bug.title} (-15)"
                    )
                    blockers.append(
                        {
                            "id": bug.id,
                            "dimension": "code_quality",
                            "title": bug.title,
                            "severity": "CRITICAL",
                            "detail": f"Unresolved recurring exception with {bug.occurrence_count} occurrences",
                        }
                    )
                elif bug.occurrence_count >= 3:
                    score -= 6.0
                    deductions.append(f"Recurring bug ({bug.occurrence_count}x): {bug.title} (-6)")
                    warnings.append(
                        {
                            "id": bug.id,
                            "dimension": "code_quality",
                            "title": bug.title,
                            "severity": "MEDIUM",
                            "detail": f"Unresolved bug with {bug.occurrence_count} occurrences",
                        }
                    )

        return round(max(0.0, min(100.0, score)), 1), blockers, warnings, deductions

    @staticmethod
    def _score_testing(
        test_signals: TestSignalInput,
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        score = 100.0
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        deductions: list[str] = []

        if not test_signals.has_ci_run or test_signals.total_tests == 0:
            deductions.append("No active test execution signals detected (-50)")
            warnings.append(
                {
                    "id": "missing_tests",
                    "dimension": "testing",
                    "title": "No Test Execution",
                    "detail": "Project has 0 recorded automated tests or missing CI signal",
                }
            )
            return 50.0, blockers, warnings, deductions

        if test_signals.failed_tests > 0:
            score -= test_signals.failed_tests * 25.0
            deductions.append(f"{test_signals.failed_tests} failing test suite(s)")
            blockers.append(
                {
                    "id": "failed_tests",
                    "dimension": "testing",
                    "title": f"{test_signals.failed_tests} Failing Tests",
                    "severity": "CRITICAL",
                    "detail": f"CI reported {test_signals.failed_tests} failing tests out of {test_signals.total_tests}",
                }
            )

        pass_rate = test_signals.passed_tests / test_signals.total_tests
        if pass_rate < 0.95 and test_signals.failed_tests == 0:
            score -= (1.0 - pass_rate) * 50.0

        return round(max(0.0, min(100.0, score)), 1), blockers, warnings, deductions

    @staticmethod
    def _score_documentation(
        has_tracked_docs: bool,
        drift_items: list[DocDriftInput],
    ) -> tuple[float, list[dict[str, Any]], list[str]]:
        score = 100.0
        warnings: list[dict[str, Any]] = []
        deductions: list[str] = []

        if not has_tracked_docs:
            deductions.append("No documentation files tracked in Living Docs (-40)")
            warnings.append(
                {
                    "id": "untracked_docs",
                    "dimension": "documentation",
                    "title": "Missing Documentation",
                    "detail": "Project has no tracked README or documentation files",
                }
            )
            return 60.0, warnings, deductions

        # Active detected drift items reduce documentation confidence
        for drift in drift_items:
            if drift.status == "detected":
                if drift.kind == "undocumented_route":
                    score -= 12.0
                    deductions.append(f"Undocumented active route: {drift.explanation} (-12)")
                    warnings.append(
                        {
                            "id": drift.id,
                            "dimension": "documentation",
                            "title": "Undocumented Active Route",
                            "detail": drift.explanation,
                        }
                    )
                elif drift.kind == "removed_route":
                    score -= 8.0
                    deductions.append("Removed route still in documentation (-8)")
                    warnings.append(
                        {
                            "id": drift.id,
                            "dimension": "documentation",
                            "title": "Ghost Documentation Route",
                            "detail": drift.explanation,
                        }
                    )
                elif drift.kind == "missing_symbol":
                    score -= 8.0
                    deductions.append("Documented symbol missing in codebase (-8)")
                elif drift.kind == "stale_section":
                    score -= 4.0
                    deductions.append("Stale section documentation (-4)")

        return round(max(0.0, min(100.0, score)), 1), warnings, deductions

    @staticmethod
    def _score_functionality(
        checklist: list[FeatureChecklistInput],
        tasks: TaskSummaryInput,
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]], list[str], str]:
        """Calculates functionality health adhering to OQ-18."""
        score = 100.0
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        deductions: list[str] = []

        # If user has not declared a feature checklist, use task progress with low confidence
        if not checklist:
            confidence = "low"
            if tasks.total_tasks > 0:
                completed_ratio = tasks.completed_tasks / tasks.total_tasks
                score = completed_ratio * 100.0
                deductions.append(
                    f"Measured via backlog tasks: {tasks.completed_tasks}/{tasks.total_tasks} completed (OQ-18 low confidence)"
                )
            else:
                score = 75.0
                deductions.append(
                    "No declared feature checklist or tasks; defaulted per OQ-18 (low confidence)"
                )
            return round(max(0.0, min(100.0, score)), 1), blockers, warnings, deductions, confidence

        confidence = "high"
        total = len(checklist)
        completed = sum(1 for item in checklist if item.completed)

        for item in checklist:
            if not item.completed:
                if item.is_critical:
                    score -= 25.0
                    deductions.append(f"Missing critical feature: {item.name} (-25)")
                    blockers.append(
                        {
                            "id": f"feat_{item.name}",
                            "dimension": "functionality",
                            "title": f"Incomplete Feature: {item.name}",
                            "severity": "CRITICAL",
                            "detail": f"Target milestone requires completed feature '{item.name}'",
                        }
                    )
                else:
                    deductions.append(f"Incomplete feature: {item.name}")
                    warnings.append(
                        {
                            "id": f"feat_{item.name}",
                            "dimension": "functionality",
                            "title": f"Incomplete Feature: {item.name}",
                            "detail": f"Feature '{item.name}' is marked incomplete",
                        }
                    )

        checklist_ratio = completed / total
        base_score = checklist_ratio * 100.0
        final_score = min(score, base_score)

        return (
            round(max(0.0, min(100.0, final_score)), 1),
            blockers,
            warnings,
            deductions,
            confidence,
        )

    @staticmethod
    def _score_architecture(
        tasks: TaskSummaryInput,
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        score = 100.0
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        deductions: list[str] = []

        if tasks.has_cyclic_dependency:
            score -= 35.0
            deductions.append("Circular dependency detected in project task DAG (-35)")
            blockers.append(
                {
                    "id": "cyclic_dependency",
                    "dimension": "architecture",
                    "title": "Cyclic Task Dependency",
                    "severity": "CRITICAL",
                    "detail": "Task graph contains one or more circular dependency cycles",
                }
            )

        if tasks.blocked_tasks > 0:
            score -= min(30.0, tasks.blocked_tasks * 5.0)
            deductions.append(
                f"{tasks.blocked_tasks} tasks currently blocked by unmet prerequisites"
            )
            warnings.append(
                {
                    "id": "blocked_tasks",
                    "dimension": "architecture",
                    "title": f"{tasks.blocked_tasks} Blocked Tasks",
                    "detail": f"{tasks.blocked_tasks} work items are blocked by incomplete upstream dependencies",
                }
            )

        return round(max(0.0, min(100.0, score)), 1), blockers, warnings, deductions
