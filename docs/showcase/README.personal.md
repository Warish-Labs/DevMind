<!--
  SHOWCASE README for the PERSONAL repository github.com/mdwarishansari/DevMind
  The real code lives in github.com/Warish-Labs/DevMind (ADR-047).
  How to use: copy this file to the personal repo as README.md.
  Screenshot URLs point at the public Warish-Labs repo, so no images need to be copied.
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Warish-Labs/DevMind/main/brand/svg/devmind-lockup-horizontal-for-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Warish-Labs/DevMind/main/brand/svg/devmind-lockup-horizontal-for-light.svg">
    <img alt="DevMind" src="https://raw.githubusercontent.com/Warish-Labs/DevMind/main/brand/svg/devmind-lockup-horizontal-for-dark.svg" width="420">
  </picture>
</p>

<p align="center"><b>An agentic AI software engineering system with a shared Project Brain.</b><br>
Understands your code, finds authorization gaps with evidence, remembers bugs, and keeps docs, reviews and releases in sync.</p>

<p align="center">
  <a href="https://github.com/Warish-Labs/DevMind"><b>Source code (Warish-Labs/DevMind)</b></a> ·
  <a href="https://devmind.warishlabs.in"><b>Live Platform</b></a> ·
  <a href="https://github.com/Warish-Labs/DevMind/tree/main/docs">Documentation</a>
</p>

---

> **This repository is a showcase.** The active codebase, CI test suites, deployments, and releases live in the
> **[Warish-Labs/DevMind](https://github.com/Warish-Labs/DevMind)** repository, which is built and managed
> under the [WarishLabs](https://warishlabs.in) organization. Issues and pull requests go there.

## Status

| Part | State |
|---|---|
| Product and architecture specification (18 documents) | Written & verified |
| Public web platform (Next.js 16) | Built with interactive code tracer & fixture data (Phase S1 Complete) |
| VS Code companion extension UI shell | Built with 5 views, diagnostics & VSIX packaged (Phase S2 Complete) |
| Server, Project Brain, LangGraph agents | Specification written; Milestone M1 foundation planned |

*Screenshots show the interface with example/fixture data. See the primary repository for working analysis and roadmap.*

## Screenshots

| Web Platform (Next.js 16 App Router) | Project Brain & Code Tracer |
|---|---|
| ![DevMind Desktop Hero](https://raw.githubusercontent.com/Warish-Labs/DevMind/main/docs/assets/screenshots/home-hero-desktop.png) | ![Code Trace Sequence](https://raw.githubusercontent.com/Warish-Labs/DevMind/main/docs/assets/screenshots/home-hero-mid-sequence.png) |
| **Brain Strata Explorer** | **Verifiable Privacy Ledger** |
| ![Brain Strata Explorer](https://raw.githubusercontent.com/Warish-Labs/DevMind/main/docs/assets/screenshots/home-brain-selected.png) | ![Privacy Ledger](https://raw.githubusercontent.com/Warish-Labs/DevMind/main/docs/assets/screenshots/home-privacy-ledger.png) |

## What DevMind is

Most tools treat code understanding, security, bugs, documentation, review, pull requests and deployments as separate jobs. DevMind keeps **one evidence-backed model of the project** (the *Project Brain*) and lets specialised agents read from and write to it, so one finding becomes useful everywhere.

- **Evidence, not eloquence:** every finding has a location, evidence and an evidence level (E0 to E3); "possible" is never presented as "proven".
- **Local-first & privacy-preserving:** the VS Code extension scans on your machine and sends only what you approve after a visible preview (default `metadata_only` mode).
- **Human decides:** fixes, merges and releases stay recommendations until a person approves them.

### The Nine Capabilities

Code Intelligence · Security Intelligence · Bug Memory · Living Documentation · Code Review Intelligence · Pull Request Intelligence · Deployment Diagnosis · Project Mentor · Project Evaluation. Release plan and status: [docs/01-product-requirements.md](https://github.com/Warish-Labs/DevMind/blob/main/docs/01-product-requirements.md).

## Stack

Next.js 16 · TypeScript Strict · FastAPI · Python 3.12 · LangGraph · PostgreSQL + pgvector · Redis/Celery · VS Code extension API · hosted LLM and embedding APIs (provider-agnostic). Architectural Decision Records: [docs/12-architecture-decisions-and-open-questions.md](https://github.com/Warish-Labs/DevMind/blob/main/docs/12-architecture-decisions-and-open-questions.md).

## Who built it

**MD Warish Ansari**, final-year B.Tech CSE student (RKDF University, Ranchi), solo developer, building under **WarishLabs**.
GitHub: [@mdwarishansari](https://github.com/mdwarishansari) · [Warish-Labs](https://github.com/Warish-Labs) · [warishlabs.in](https://warishlabs.in)

## Related projects

[ForgeFlow-AI](https://github.com/Warish-Labs/ForgeFlow-AI) · [WarishLabs website](https://github.com/Warish-Labs/warishlabs-website)
