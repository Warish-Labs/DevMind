<!--
  SHOWCASE README for the PERSONAL repository  github.com/mdwarishansari/DevMind
  The real code lives in  github.com/Warish-Labs/DevMind  (ADR-047).
  How to use: copy this file to the personal repo as README.md. Replace the {{...}} markers
  when the facts change. Screenshot URLs point at the public Warish-Labs repo, so no images
  need to be copied. Antigravity upgrades this file after the home-page and extension
  screenshots exist (task R1-03); keep the claims honest.
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
  <a href="{{LIVE_URL}}"><b>Live site</b></a> ·
  <a href="https://github.com/Warish-Labs/DevMind/tree/main/docs">Documentation</a>
</p>

---

> **This repository is a showcase.** The code, CI, deployments and releases live in the
> **[Warish-Labs/DevMind](https://github.com/Warish-Labs/DevMind)** repository, which is built and managed
> under the [WarishLabs](https://warishlabs.in) account. Issues and pull requests go there.

## Status

| Part | State |
|---|---|
| Product and architecture specification (14 documents) | Written |
| Public home page | {{HOME_STATUS: not started / in progress / built, with example data}} |
| VS Code extension UI | {{EXT_STATUS: not started / in progress / UI shell with fixture data}} |
| Server, Project Brain, agents | {{SERVER_STATUS: not started}} |

*Screenshots show the interface with example/fixture data. They are not a demo of working analysis.*

## Screenshots

<!-- Replace with real files after phases S1 and S2 are merged (they are generated into docs/assets/screenshots/) -->

| Home page | VS Code extension |
|---|---|
| {{home-hero-desktop.png}} | {{extension-01-findings.png}} |

## What DevMind is

Most tools treat code understanding, security, bugs, documentation, review, pull requests and deployments as separate jobs. DevMind keeps **one evidence-backed model of the project** (the *Project Brain*) and lets specialised agents read from and write to it, so one finding becomes useful everywhere.

- **Evidence, not eloquence:** every finding has a location, evidence and an evidence level (E0 to E3); "possible" is never presented as "proven".
- **Local-first:** the VS Code extension scans on your machine and sends only what you approve after a visible preview.
- **Human decides:** fixes, merges and releases stay recommendations until a person approves them.

### The nine capabilities

Code Intelligence · Security Intelligence · Bug Memory · Living Documentation · Code Review Intelligence · Pull Request Intelligence · Deployment Diagnosis · Project Mentor · Project Evaluation. Release plan and status: [docs/01](https://github.com/Warish-Labs/DevMind/blob/main/docs/01-product-requirements.md).

## Stack

Next.js · TypeScript · FastAPI · Python · LangGraph · PostgreSQL + pgvector · Redis/Celery · VS Code extension API · hosted LLM and embedding APIs (provider-agnostic). Why each choice: [docs/12](https://github.com/Warish-Labs/DevMind/blob/main/docs/12-architecture-decisions-and-open-questions.md).

## Who built it

**MD Warish Ansari**, final-year B.Tech CSE student (RKDF University, Ranchi), solo developer, building under **WarishLabs**.
GitHub: [@mdwarishansari](https://github.com/mdwarishansari) · [Warish-Labs](https://github.com/Warish-Labs) · [warishlabs.in](https://warishlabs.in)

## Related projects

[ForgeFlow-AI](https://github.com/Warish-Labs/ForgeFlow-AI) · [WarishLabs website](https://github.com/Warish-Labs/warishlabs-website)
