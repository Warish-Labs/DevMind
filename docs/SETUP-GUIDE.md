# DevMind Setup Guide: what YOU do (and what Antigravity does)

**Purpose.** A plain, step-by-step manual for the owner: GitHub setup, free accounts, API keys and where to paste them, local commands, tests, CI, deployment on Render and Vercel, and publishing the VS Code extension. Antigravity builds the code from `docs/ANTIGRAVITY_PROMPT.md`; this guide covers everything only a human can do.

**Status.** Rewritten 2026-10-13 for a **free-only** setup. Vendor click-paths, limits and terms change; items marked `[VERIFY]` must be checked on the vendor's page when you reach them. The commands in §8 are the *expected* ones; Antigravity re-verifies them after each phase and stamps them `Verified by Antigravity on <date> at <commit>`. Nothing is deployed yet, and the first two phases (home page and extension screenshots) need **no keys at all**.

---

## 1. Read this first

### The decision: work in `Warish-Labs/DevMind` from today

**Follow this plan from now, not later.** Create the real repository in the WarishLabs organization **now**, make it **public**, and do all work there. Keep `mdwarishansari/DevMind` as a **showcase redirect** (the same pattern you used for ForgeFlow-AI).

Why now, and why public (every reason is about being free):

| Reason | Detail [checked 2026-10-13; see §3] |
|---|---|
| **Vercel Hobby (free)** can deploy an organization's repository **only if it is public**; private org repos are blocked on Hobby. Also the commit author must be the Hobby team owner. | Vercel docs and forum threads |
| **GitHub Free** gives rulesets (the "no push to main" rule), required reviewers on environments, secret scanning with push protection, CodeQL, dependency review and **unlimited Actions minutes only on public repos**. On a private Free repo you cannot enforce any of it, and Actions minutes are limited. | GitHub plan docs |
| **No migration pain.** Moving a repo later breaks CI secrets, Vercel/Render links, OAuth callbacks, Clerk webhooks, the Marketplace `repository` field and the history you want to keep. Doing it right from day one costs nothing. | Experience |
| **It is your portfolio.** A public repo with CI, ADRs, a brand kit and a deployed site is the point. Nothing in it needs to be secret as long as you never commit keys. | |

You wrote that in `warishlabs` you would make a README that redirects *to* the personal repo. For ForgeFlow-AI you did the opposite (personal repo redirects to the code in `warishlabs`). I used the **ForgeFlow pattern** for DevMind too: **code in `Warish-Labs/DevMind`, showcase README in `mdwarishansari/DevMind`**, because deployments, CI and releases live where the code is.

### The order of work

| Step | Who | What |
|---|---|---|
| 1 | You | Create the public repo `Warish-Labs/DevMind`, unzip the starter, make the **first push to `main`** (§4.1) |
| 2 | You | About text, topics, social preview, repo settings (§4.2 to §4.3) |
| 3 | You | Put the showcase README into `mdwarishansari/DevMind` (§4.7) |
| 4 | Antigravity | Phase P0: docs check, tooling, CI (3 small PRs). You merge each. |
| 5 | You | After the first CI run, create the **ruleset** requiring `ci-gate` (§4.4; free because the repo is public) |
| 6 | Antigravity | Phase S1: **home page**. You screenshot and merge. |
| 7 | Antigravity | Phase S2: **extension UI** (fixture data). You screenshot and merge. |
| 8 | Antigravity | Phase R1: showcase README with your screenshots; you copy it to the personal repo |
| 9 | Both | Milestones M1 to M13; you create free accounts and keys when asked (§6) |
| 10 | You | Deploy when ready: Render free, Vercel Hobby, Marketplace (§11 to §13) |

### The four code folders

| Folder | What it is | Where it deploys (all free) |
|---|---|---|
| `client/` | Next.js website | Vercel Hobby |
| `server/` | FastAPI API + Celery worker + scheduler (Python) | **One** Render free web service (worker embedded) |
| `extension/` | VS Code extension | VS Code Marketplace + Open VSX |
| `common/` | Shared TypeScript: generated API types, shared data (rule catalog, release status, privacy ledger), tokens | Not deployed alone |

Other root folders: `docs/` (specification, runbooks, showcase kit), `brand/` (logo and tokens), `evals/`, `infra/` (Docker Compose), `scripts/`, `.github/` (CI).

### Four things to know now

1. **Tests are Vitest + Playwright (TypeScript) and pytest (Python), not Jest. There is no GraphQL**: the API is REST with an OpenAPI schema. One command runs everything: `pnpm test:all` (§9).
2. **Free-tier reality (the design already accounts for it):** the Render free service **sleeps after about 15 minutes idle** and takes about a minute to wake; there is **no free background-worker service on Render**, so the Celery worker runs **inside** the same free web service (ADR-046); Render's free Key Value (the Redis) is disposable and **one per workspace**; Neon Free **suspends after about 5 minutes** and has a small storage cap. The website and extension show a "server waking up" state instead of failing.
3. **The repo is public:** never commit a key, a `.env` file, a screenshot showing a key, or private source code. Turn on secret scanning and push protection (§4.3).
4. **Free LLM tiers can use your data to improve their products.** Use synthetic fixtures or public code only with them (ADR-048). The built-in fake provider needs no key.

---

## 2. What you do vs what Antigravity does

| You (human steps) | Antigravity |
|---|---|
| Create free accounts (Clerk, Neon, Render, Vercel, an LLM provider, Marketplace publisher) | Writes all code, tests, CI workflows, Dockerfile, `render.yaml`, docs |
| Paste keys into local `.env` files and into Render/Vercel dashboards | Never sees or commits real keys; ships `.env.example` files with placeholders |
| Review and **squash-merge** each PR on GitHub after CI is green | Creates branches, commits after every task, pushes, opens PRs |
| Type `continue` after each merge or when a session ends | Reads `BRAIN.md` and `PLAN.md`, deletes merged branches, starts the next task |
| Take the screenshots (home page, extension) | Provides `pnpm screenshots` and the screenshot checklist (§14) |
| Click through the Render, Vercel, Marketplace dashboards; add DNS records | Prepares and validates `render.yaml`, build settings, release workflow |
| Decide open questions (license, publisher id, LLM provider) | Records the decision as an ADR and applies it |
| Copy the showcase README into `mdwarishansari/DevMind` | Writes and updates `docs/showcase/README.personal.md` |

---

## 3. Accounts, limits and when each is needed (all free)

Everything below must stay on the free tier. Numbers are what I could verify on 2026-10-13, some from secondary sources; they change, so check the vendor page when you sign up.

| Service | Needed from | Used for | Free-tier facts and caveats |
|---|---|---|---|
| **GitHub** (`Warish-Labs` org, free) | Now | Code, PRs, Actions CI, rulesets | Public repo: rulesets, environment reviewers, secret scanning, CodeQL, unlimited Actions minutes |
| **GitHub CLI (`gh`)** | Now | Lets Antigravity push and open PRs | Free |
| **Clerk** | M2 | Website sign-in | Free plan with a large monthly-active-user allowance (sources say 10,000 to 50,000; check) and a custom domain |
| **Neon** | Deploy / staging (local dev uses Docker) | PostgreSQL + pgvector | Free: about 0.5 GB per project (a 2026-10-02 changelog says 1 GB; plan for 0.5), compute suspends after about 5 minutes, up to 100 projects, so use one Neon project per environment |
| **Redis** | Local: Docker. Hosted: **Upstash Redis (free)** | Celery queue, rate limits | Free Tier: 10k commands/day, standard Redis TLS protocol (`rediss://`). Disposable by design: Postgres holds job state |
| **Render** | Deploy | The API + embedded worker | Free web service: 512 MB RAM, sleeps after about 15 min idle (about a minute to wake), 750 instance hours per workspace per month shared with other free services; **no free background worker** |
| **Vercel (Hobby)** | Deploy | The website | Free, **personal non-commercial use only**; org repos only if public; commit author must be the team owner. If DevMind ever earns money, move to Cloudflare Pages/Netlify or pay |
| **LLM provider** | M5 to M6 (optional) | Answers and analysis | **Google AI Studio free tier** (rate-limited; content may be used to improve products). Or the fake provider with no key |
| **Embedding provider** | M5 (optional) | Vector search | Free embedding quota from the same provider [VERIFY]; or the fake embedder |
| **Visual Studio Marketplace publisher** | Extension release | Publish the extension | Free |
| **Open VSX** | Extension release | Cursor, VSCodium, Antigravity users | Free |
| **Resend** | M11 | Invitation emails | You already verified `warishlabs.in`; free tier has daily and monthly send limits [VERIFY] |
| **GitHub OAuth app** | M11 | Connect GitHub repos | Free; create it under the `Warish-Labs` org |
| **Cloudflare R2** | Deferred / Not used by MVP | Exports and uploads | Deferred: not needed for the MVP. Zero buckets or accounts required. |
| **Error monitoring** | M10 (optional) | Error reports | Render logs are enough; a free monitoring tier is optional (OQ-15) |

**If you ever must pay for something**, do it later under the `warishlabs` account and record it as a decision. Nothing in this plan requires it.

---

## 4. GitHub setup

### 4.0 Accounts and identity

You have: the personal account **`mdwarishansari`** (showcase only), the personal account **`warishlabs`**, and the organization **`Warish-Labs`**. Antigravity and `gh` should use the account that has **write access to `Warish-Labs`** (your `warishlabs` login, if it owns the org). That same account must own your **Vercel Hobby team** (Vercel checks the commit author).

Find its numeric id to build the commit email (this avoids exposing a private address and keeps Vercel happy):

```bash
gh auth login                       # choose GitHub.com, HTTPS, login with a web browser, as the account that owns Warish-Labs
gh api user --jq '.id, .login'      # prints the id and login, for example: 12345678 / warishlabs
# your commit email is:  <id>+<login>@users.noreply.github.com
```

### 4.1 Create the repo and make the first push (you do this once)

1. Create the repo: browser → `github.com/organizations/Warish-Labs/repositories/new` → name **DevMind** → **Public** → do **not** add a README, .gitignore or license (the starter has them) → Create. (CLI alternative: `gh repo create Warish-Labs/DevMind --public`.)
2. Unzip the starter. **First move your old folder aside**, because it has the same name:

```bash
cd ~/Projects
mv DevMind DevMind-old                       # keep it until you are sure, then delete it
unzip ~/Downloads/DevMind-starter.zip        # creates ~/Projects/DevMind
cd DevMind
ls -a                                        # expect: .gitattributes .gitignore AGENTS.md README.md brand docs
```

3. Check for secrets (there should be none) and push:

```bash
grep -RIn --exclude-dir=.git -E "(sk_live|sk_test|pk_live|AKIA|BEGIN (RSA|PRIVATE)|api[_-]?key *[:=] *['\"][A-Za-z0-9]{16,})" . || echo "no secrets found"

git init -b main
git config user.name  "MD Warish Ansari"
git config user.email "<id>+<login>@users.noreply.github.com"      # from 4.0
git remote add origin https://github.com/Warish-Labs/DevMind.git
git add -A
git status                                   # nothing odd? no .env, no node_modules?
git commit -m "docs: import DevMind specification, brand kit and agent rules"
git push -u origin main
```

This is the **only** time you push to `main` directly. After this, every change goes through a pull request.

### 4.2 Repository "About" (gear icon, top right of the repo page)

GitHub's description limit is **350 characters**. Counts below are real.

| Version | Length | Text |
|---|---|---|
| **Recommended** | 226 | DevMind: an agentic AI software engineering system with a shared Project Brain. Understands your code, finds authorization gaps with evidence, remembers bugs, and keeps docs, reviews and releases in sync. Local-first VS Code extension. |
| Short | 105 | Agentic AI software engineering platform with a shared Project Brain and a local-first VS Code extension. |
| Long | 241 | Evidence-first AI engineering platform: one shared Project Brain that powers code intelligence, security review, bug memory, docs, PR analysis and project health, with a local-first VS Code extension. Next.js, FastAPI, LangGraph, PostgreSQL. |

- **Website:** `https://devmind.warishlabs.in` once it is deployed (leave empty before).
- **Topics:** `ai-agents`, `langgraph`, `nextjs`, `fastapi`, `vscode-extension`, `developer-tools`, `code-intelligence`, `security-analysis`, `rag`, `pgvector`, `typescript`, `python`, `static-analysis`.
- **Social preview:** Settings → General → *Social preview* → upload `brand/social/github-social-preview-1280x640.png`.

For the personal showcase repo use the **Short** text and add: "Source: github.com/Warish-Labs/DevMind".

### 4.3 Repository settings (`Warish-Labs/DevMind`)

Settings → **General**
- Default branch `main`. Features: Issues on; Wikis, Projects, Discussions off.
- **Pull Requests:** allow **squash merging** only (turn off merge commits and rebase merging); default squash message = **pull request title**; tick **Always suggest updating pull request branches**, **Automatically delete head branches**, and (optional) **Allow auto-merge**.

Settings → **Actions → General**
- Allow GitHub-created and verified-creator actions (Antigravity pins third-party actions by commit SHA).
- Workflow permissions: **Read repository contents**. Leave "Allow GitHub Actions to create and approve pull requests" **off**.

Settings → **Code security** (free for public repos): enable **Dependabot alerts**, **Dependabot security updates**, **Secret scanning** and **Push protection**. CodeQL runs from a workflow Antigravity adds; dependency review runs in CI.

Settings → **Environments** → New environment `extension-release` → add yourself as **required reviewer** (free for public repos). Used only when publishing the extension.

### 4.4 Block direct pushes to `main` (ruleset; free because the repo is public)

Wait until Antigravity's P0 CI PR has run once (the check name `ci-gate` appears in the picker only after it has run). Then:

Settings → **Rules → Rulesets → New ruleset → New branch ruleset**

1. Name `protect-main`; Enforcement **Active**; bypass list **empty** (this blocks you too, on purpose).
2. Target branches: **Add target → Include default branch**.
3. Tick **Restrict deletions**, **Require linear history**, **Block force pushes**.
4. Tick **Require a pull request before merging**: required approvals **0** (you cannot approve your own PR); tick **Dismiss stale pull request approvals when new commits are pushed** and **Require conversation resolution before merging**.
5. Tick **Require status checks to pass**; tick **Require branches to be up to date before merging**; **Add checks → `ci-gate`** (only this one).
6. Create. Test it from a scratch clone: `git push origin main` must be rejected.

Layers protecting `main`: this ruleset (server-side), a local pre-push hook, Antigravity's rules, and a `main-guard` workflow that flags any push to `main` that did not come from a PR.

### 4.5 GitHub Actions secrets

CI needs **no secrets** (tests use a fake LLM provider and service containers). Add secrets only when you publish the extension: Settings → Environments → `extension-release` → Environment secrets: `VSCE_PAT` and `OVSX_PAT` (§13).

### 4.6 Your routine for every pull request

1. Antigravity pushes a branch and opens a PR (or prints the link).
2. Open the PR → **Checks**. Wait for `ci-gate` to be green.
3. Skim **Files changed** and the PR description (it lists what was tested, with real output).
4. **Squash and merge** (the title is already a Conventional Commit) → Confirm. The branch deletes itself.
5. Back in Antigravity type **`continue`**. It pulls `main`, deletes the local branch, updates `PLAN.md` and `BRAIN.md`, and starts the next slice.
6. If CI is red, type `continue` (it fixes the same branch). If it keeps failing, paste the failing job name.

### 4.7 The personal showcase repo (`mdwarishansari/DevMind`)

This repo only redirects visitors. Do it once now and refresh it after S1, S2 and the live deploy.

1. Open `docs/showcase/README.personal.md` in the real repo.
2. In `mdwarishansari/DevMind` (empty today) click **Add a file → Create new file**, name it `README.md`, paste the content, replace the `{{...}}` markers (live URL, statuses), commit to `main` (no ruleset needed there).
3. Add the **Short** About text and the same topics. Pin the repo on your profile.
4. After S1 and S2 are merged, Antigravity upgrades the file with real screenshots (they load from the public repo via `raw.githubusercontent.com`), and you paste the new version again.
5. In your `warishlabs` profile README and the `Warish-Labs` org profile, link to the real repo and the live site.

### 4.8 Public-repo safety checklist

- Never paste a key into a chat, an issue, a PR, a screenshot or a file.
- `.env`, `.env.local` are git-ignored; run `git status` before every commit you make by hand.
- If a secret ever reaches GitHub: **revoke it at the provider first**, then tell Antigravity. Do not try to hide it by rewriting history.
- Screenshots must show example/fixture data only.
- Do not add a license by accident: with no license, others may view but not reuse the code. Decide later (OQ: license).

---

## 5. Local machine prerequisites (Ubuntu)

Do these once. Antigravity pins exact versions in `.nvmrc`, `package.json` and `pyproject.toml`; you only install the managers.

```bash
# basics
sudo apt update && sudo apt install -y git curl build-essential jq

# GitHub CLI: follow the official Linux install steps, then log in (done in §4.1)
#   https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Node.js via fnm (Node 24 LTS; Node 26 becomes LTS in late Oct 2026, Antigravity evaluates it later)
curl -fsSL https://fnm.vercel.app/install | bash      # restart the terminal afterwards
fnm install 24 && fnm default 24 && node -v

# pnpm via corepack (the repo's package.json decides the pnpm version)
corepack enable            # if "command not found": npm install -g corepack && corepack enable

# Python tooling: uv installs and manages Python for the server
curl -LsSf https://astral.sh/uv/install.sh | sh        # restart the terminal, then: uv --version

# Docker Engine + Compose plugin: follow https://docs.docker.com/engine/install/ubuntu/
sudo usermod -aG docker $USER                          # log out and in again
docker run --rm hello-world && docker compose version
```

Also needed: **VS Code** (for extension development, press F5) and **Antigravity**. In Antigravity use *Planning* mode, and set terminal execution to require your review for commands that push, delete or install packages [VERIFY setting names]. Disk space for Docker images: several GB.

---

---

## 6. Services step by step (free tiers; only when the milestone asks)

> **Never paste a key into a chat, a commit, a screenshot or an issue.** The repo is public. Keys go only into local `.env` files (git-ignored) and the Render/Vercel/GitHub secret fields.

### 6.1 Clerk (website sign-in), needed from M2

1. clerk.com → sign up → **Create application** `DevMind`. Enable **Email** and **GitHub** (and/or Google) sign-in.
2. Dashboard → **API keys**. Copy the **Publishable key** (`pk_test_...`) and **Secret key** (`sk_test_...`).
3. Paste into `client/.env.local`: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...` and `CLERK_SECRET_KEY=sk_test_...`.
4. For the **server** (verifies tokens): on the same page open **Show API URLs** and copy the **Frontend API URL** (looks like `https://something.clerk.accounts.dev`). In `server/.env`: `DEVMIND_CLERK_ISSUER=<that URL>`, `DEVMIND_CLERK_JWKS_URL=<that URL>/.well-known/jwks.json`, `DEVMIND_CLERK_AUTHORIZED_PARTIES=http://localhost:3000`.
5. Webhook (later): Dashboard → **Webhooks → Add endpoint** → `https://api.devmind.warishlabs.in/api/v1/webhooks/clerk` (or your Render URL), events `user.created`, `user.updated`, `user.deleted` → copy the **Signing secret** (`whsec_...`) into `DEVMIND_CLERK_WEBHOOK_SECRET`.
6. **Production** later: Clerk has separate Development and Production instances. The Production instance uses your domain (`devmind.warishlabs.in`); Clerk shows DNS records to add (§6.6). Free plan includes a custom domain [VERIFY].

### 6.2 Neon (PostgreSQL), needed at deploy or staging

Local development uses the Docker Postgres from `infra/docker-compose.yml`. Neon is for hosted environments.

1. neon.com → sign up → **Create project** `devmind-prod` (create a second free project `devmind-staging` later; each project has its own free allotment) → region **closest to your Render region** → latest Postgres version.
2. Open the project's **Connect** dialog. You need two connection strings:
   - **Pooled** (toggle *Connection pooling* on; the host contains `-pooler`) → `DEVMIND_DATABASE_URL`.
   - **Direct** (pooling off) → `DEVMIND_DATABASE_URL_DIRECT` (migrations use this).
3. Extensions (`vector`, `pg_trgm`) are enabled by Antigravity's first migration. Antigravity documents the separate database roles as SQL for you to run once in the Neon SQL editor (a HUMAN-STEP).
4. **Free-tier behavior to expect:** the database suspends after about 5 minutes idle and the first query after that is slower; storage is capped (plan for 0.5 GB), so DevMind enforces per-project limits (`server/configs/quotas.free.yaml`). Never copy production data into staging.

### 6.3 Redis: **required**, and free

DevMind needs a Redis-compatible store for the Celery job queue and rate limits.

- **Local:** nothing to sign up for. `docker compose -f infra/docker-compose.yml up -d` starts it.
- **Hosted:** **Upstash Redis (free)** on `console.upstash.com`. Connect using standard TLS Redis protocol: `rediss://default:<password>@<host>.upstash.io:6379` (do NOT use the Upstash HTTP REST URL). PostgreSQL holds persistent job state and a startup sweep re-enqueues stranded jobs.


### 6.4 LLM and embedding keys (free; needed from M5/M6, optional before)

The provider and models are still an **open decision** (ADR-017). Antigravity ships a **fake provider**, so everything builds and tests without any key. For real answers on the free tier:

| Provider | Create a key at | What to know [VERIFY] |
|---|---|---|
| **Google AI Studio (Gemini API)** (recommended start) | aistudio.google.com → *Get API key* | Free tier is rate-limited (limits shown per account in AI Studio and they change); **free-tier content may be used to improve Google products**, so use **synthetic fixtures or public code only** |
| Other providers with free tiers (OpenAI-compatible endpoints such as Groq or OpenRouter free models, Mistral) | their consoles | Quality, limits and data terms differ; Antigravity can add an OpenAI-compatible adapter if you choose one |

In `server/.env`: `DEVMIND_LLM_PRIMARY_API_KEY=...` and `DEVMIND_EMBED_API_KEY=...` (may be the same key). Model names go in `server/configs/llm/models.yaml` (not secret); Antigravity proposes them from benchmark results. Rate limits will make large analyses slow on the free tier; that is expected. **Never send private code** to any provider until you have read its terms (docs/07 §6, ADR-048).

### 6.5 Services for later milestones

- **Cloudflare Turnstile (Public forms bot protection):**
  1. Go to `dash.cloudflare.com` → **Turnstile** → **Add Site**.
  2. Set Widget name to `DevMind Production`.
  3. Domain: add `devmind.warishlabs.in` (and `localhost` if testing production widget locally).
  4. Widget Mode: **Managed** (Cloudflare automatically decides whether an interactive challenge is needed).
  5. Click **Create** to obtain:
     - **Site Key**: Public key configured in Vercel as `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
     - **Secret Key**: Private key configured in Render as `DEVMIND_TURNSTILE_SECRET_KEY` (never expose to frontend).
  6. **Local Development & Automated Testing:** Use Cloudflare's official dummy test keys:
     - Site Key (always passes): `1x00000000000000000000AA`
     - Secret Key (always passes): `1x0000000000000000000000000000000AA`
- **Resend (M11):** you already verified `warishlabs.in`. In Resend create a **new API key for DevMind** (sending access only) → `DEVMIND_RESEND_API_KEY`. Send from an address on your verified domain (for example `devmind@warishlabs.in`); no new DNS should be needed [VERIFY]. Check the free daily and monthly limits.
- **GitHub OAuth app (M11):** `github.com/organizations/Warish-Labs/settings/applications` → **New OAuth App** (create it under the org, not a personal account). Homepage URL = `https://devmind.warishlabs.in`; callback URL = `https://api.devmind.warishlabs.in/api/v1/integrations/github/callback` (local: `http://localhost:8000/api/v1/integrations/github/callback`). Client ID and secret → `DEVMIND_GITHUB_OAUTH_CLIENT_ID` / `DEVMIND_GITHUB_OAUTH_CLIENT_SECRET`. Webhook secret = a random string you generate (§6.7).
- **Cloudflare R2:** not needed for the MVP; skip.
- **Error monitoring (M10):** optional; Render logs are enough at first.

### 6.6 Domain and DNS plan (`warishlabs.in`; ADR-049, Recommended)

| Name | Points to | When |
|---|---|---|
| `devmind.warishlabs.in` | Vercel (add the domain in the Vercel project; it shows the exact CNAME/A record) | After the first Vercel deploy |
| `api.devmind.warishlabs.in` | Your Render service (add the custom domain in Render; it shows the CNAME and verifies it) | After the first Render deploy |
| Clerk production records | The CNAMEs that Clerk displays for the Production instance | When you create the Clerk Production instance |

Add the records wherever the DNS for `warishlabs.in` is managed. Both Vercel and Render provide free TLS certificates for custom domains.

### 6.7 Secrets you generate yourself

```bash
openssl rand -base64 32     # DEVMIND_EXT_TOKEN_PEPPER
openssl rand -base64 32     # an encryption key for DEVMIND_ENCRYPTION_KEYS (format documented in server/.env.example)
openssl rand -hex 32        # DEVMIND_GITHUB_WEBHOOK_SECRET
```

---

## 7. Environment variables: where each goes

Local files: `client/.env.local`, `server/.env` (both git-ignored; copy from the matching `.env.example`). Hosted: Vercel project settings (client) and Render environment (server). Antigravity keeps this table in sync with the `.env.example` files.

### Client (`client/.env.local`, Vercel)

| Variable | Value / source | Needed from |
|---|---|---|
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` locally; `https://devmind.warishlabs.in` in production | S1 (metadata) |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` locally; `https://api.devmind.warishlabs.in` (or the Render URL) | M2 |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk → API keys | M2 |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Cloudflare Dashboard → Turnstile (or `1x00000000000000000000AA` locally) | S1 / M8 |
| `CLERK_SECRET_KEY` | Clerk → API keys (server-side only) | M2 |

### Server (`server/.env`, Render)

| Variable | Value / source | Needed from |
|---|---|---|
| `DEVMIND_ENV` | `local` / `staging` / `production` | M1 |
| `DEVMIND_RUN_MODE` | `all` (API + embedded worker, used on Render free and for simple local runs), or `api` / `worker` / `scheduler` | M1 |
| `DEVMIND_REDIS_KEY_PREFIX` | Optional prefix, only if you share a Redis instance (§6.3) | M1 |
| `DEVMIND_LOG_LEVEL` | `INFO` | M1 |
| `DEVMIND_DATABASE_URL` | Local Docker Postgres URL (given in `.env.example`); Neon **pooled** URL when hosted | M2 |
| `DEVMIND_DATABASE_URL_DIRECT` | Local same URL; Neon **direct** URL when hosted | M2 |
| `DEVMIND_REDIS_URL` | Local Docker Redis; Render free Key Value **Internal** URL when hosted | M1 |
| `DEVMIND_CLERK_ISSUER`, `DEVMIND_CLERK_JWKS_URL`, `DEVMIND_CLERK_AUTHORIZED_PARTIES` | Clerk (§6.1) | M2 |
| `DEVMIND_CLERK_WEBHOOK_SECRET` | Clerk webhook signing secret | M2 |
| `DEVMIND_TURNSTILE_SECRET_KEY` | Cloudflare Dashboard → Turnstile (or `1x0000000000000000000000000000000AA` locally) | S1 / M8 |
| `DEVMIND_CORS_ORIGINS` | `http://localhost:3000`; `https://devmind.warishlabs.in` | M2 |
| `DEVMIND_ENCRYPTION_KEYS`, `DEVMIND_EXT_TOKEN_PEPPER` | You generate (§6.6) | M2 to M3 |
| `DEVMIND_LLM_PRIMARY_API_KEY`, `DEVMIND_LLM_ALT_API_KEY`, `DEVMIND_EMBED_API_KEY` | Provider consoles (§6.4) | M5 to M6 |
| `DEVMIND_GITHUB_OAUTH_CLIENT_ID`, `..._SECRET`, `DEVMIND_GITHUB_WEBHOOK_SECRET` | GitHub (§6.5) | M11 |
| `DEVMIND_RESEND_API_KEY` | Resend (§6.5) | M11 |
| `DEVMIND_SENTRY_DSN` (or vendor equivalent), `DEVMIND_OTEL_EXPORTER_ENDPOINT` | Monitoring vendor | M10 |
| `DEVMIND_MIN_EXTENSION_VERSION`, `DEVMIND_KILL_SWITCHES` | Plain config (defaults in `.env.example`) | M3 / M10 |

### GitHub Actions (only for extension releases)

| Secret | Where | Source |
|---|---|---|
| `VSCE_PAT` | Settings → Environments → `extension-release` | Azure DevOps token (§13) |
| `OVSX_PAT` | same | open-vsx.org token (§13) |

---

---

## 8. Running everything locally

Expected commands. **Verified by Antigravity on 2026-10-16 at commit `7bc34c6` (Phase S2 complete).**

| Task | Command | Available from |
|---|---|---|
| Install JS dependencies | `corepack enable && pnpm install --frozen-lockfile` | P0 |
| Home page dev server | `pnpm --filter client dev` → http://localhost:3000 | S1 |
| Home page production build | `pnpm --filter client build && pnpm --filter client start` | S1 |
| Take home-page screenshots | `pnpm screenshots` → `docs/assets/screenshots/` | S1 |
| Build the extension | `pnpm --filter devmind-vscode build` | S2 |
| Run the extension | Open the repo in VS Code, **Run and Debug → "Run DevMind Extension" (F5)**; a second window opens on the fixture project | S2 |
| Package the extension | `pnpm --filter devmind-vscode package` → `dist/devmind-vscode.vsix` | S2 |
| Start Postgres + Redis (+ API, worker) | `docker compose -f infra/docker-compose.yml up -d` | M1 |
| Server setup | `cd server && uv sync && cp .env.example .env` | M1 |
| Run the API | `cd server && uv run uvicorn app.main:app --reload --port 8000` → http://localhost:8000/healthz | M1 |
| Run the worker (separate process, for testing) | `cd server && uv run celery -A app.workers.celery_app worker -l info` | M1 |
| Run API + worker together (what Render free runs) | `cd server && DEVMIND_RUN_MODE=all uv run python -m app.launcher` | M1 |
| Database migrations | `cd server && uv run alembic upgrade head` | M2 |
| Regenerate API types | `pnpm gen:api` | M2 |
| Lint / typecheck everything | `pnpm lint && pnpm typecheck` | P0 |
| **Everything (fast)** | `pnpm test:all` (or `pnpm verify`) | P0 |
| **Everything (full)** | `pnpm test:all --full` | M1 |

Ports: client 3000, API 8000 (Antigravity confirms and documents any change).

---

---

## 9. Testing: one command

```bash
pnpm test:all            # fast: install check, lint, typecheck, unit tests, builds, docs and brand checks
pnpm test:all --full     # adds integration (needs Docker), browser end-to-end, extension-host tests, scanner and retrieval evals, migration tests
pnpm test:all --only server     # one area: client | server | extension | common | docs
```

It prints a table of steps with `PASS`, `FAIL` or `SKIP (reason)` and the time each took, saves full logs to `reports/<timestamp>/` (git-ignored) and exits with an error if anything failed. What the layers mean:

| Layer | In plain words |
|---|---|
| Lint | Style rules and obvious mistakes (ESLint, ruff) |
| Typecheck | The compiler checks types without running code (`tsc`, pyright) |
| Unit tests | Small functions tested alone (Vitest, pytest) |
| Integration tests | Code against a real Postgres and Redis in Docker |
| End-to-end | A real browser clicking through the site (Playwright) |
| Evals | Measurements of scanner accuracy and search quality on labeled examples |

If something fails, open the log file named in the table. Details: `docs/runbooks/testing.md`.

---

---

## 10. CI/CD: what exists and why there is almost no CD

- **CI (GitHub Actions)** runs on every pull request and on pushes to `main`: lint and types, unit tests, builds, Playwright e2e, docs and brand checks, security audit, dependency review, and from M1 the server jobs (Postgres + pgvector and Redis as service containers). Because the repo is **public, Actions minutes are unlimited** on standard runners. A final job named **`ci-gate`** passes only if all others pass; it is the single required check in your ruleset (§4.4). Every job runs on every PR (no path filters), which avoids the classic "required check never reported" trap.
- **CodeQL** (JavaScript/TypeScript and Python) runs on PRs and weekly. **Dependabot** opens weekly grouped PRs for dependencies and actions (Antigravity pins actions by commit SHA and uses a 7-day release-age cooldown for npm). **`main-guard`** flags any push to `main` that did not come from a PR.
- **CD** is done by the hosts: **Vercel** deploys `main` automatically (preview URLs for PRs); **Render** deploys `main`, set to wait for CI checks to pass (`autoDeployTrigger: checksPass` [VERIFY it is available on the free web service]). So there is no deploy workflow to maintain.
- The only deploy-like workflow is **extension release**: pushing a tag like `ext-v0.1.0` builds and tests, attaches the `.vsix` to a draft GitHub Release and, after your approval in the `extension-release` environment and only if tokens exist, publishes to the Marketplace and Open VSX.

---

## 11. Deploying the server on Render, free (later; do not do this yet)

**What runs:** one **free web service** (`devmind-api`) that starts the API **and** an embedded Celery worker with scheduler in the same container (`DEVMIND_RUN_MODE=all`), plus one **free Key Value** (`devmind-redis`). Antigravity prepares and validates `render.yaml` in M1.

**What to expect (free tier):** the service sleeps after about 15 minutes without requests; the next request takes about a minute while it wakes (the website and extension show "Server waking up…"). Background jobs run only while the service is awake. The free Key Value has no persistence; DevMind recovers from the database. 750 free instance hours per workspace are shared by every free service you have there.

Steps:

1. render.com → sign in with GitHub → grant access to `Warish-Labs/DevMind` (install the Render GitHub app on the org; an org owner must approve).
2. **New → Blueprint** → choose the repo and branch `main`. Render reads `render.yaml` and lists `devmind-api` (web, Docker, **Free**) and `devmind-redis` (Key Value, **Free**).
3. Render asks for each secret marked `sync: false`: Neon URLs (§6.2), Clerk values (§6.1), generated secrets (§6.7), optional LLM keys (§6.4). Paste them there, never in the file.
4. Click **Apply** and watch the deploy logs. Success looks like: the container starts, migrations run at startup, `https://<service>.onrender.com/healthz` returns OK, and `/readyz` shows the database and Redis are reachable.
5. **Build and start commands:** none to type. The service uses Docker (`server/Dockerfile`); the start command is the launcher defined in the Dockerfile/Blueprint. The pre-deploy command is not used on the free plan.
6. Custom domain: Service → **Settings → Custom Domains** → add `api.devmind.warishlabs.in` and create the CNAME Render shows (§6.6).
7. Set `DEVMIND_CORS_ORIGINS` to `https://devmind.warishlabs.in` and put the API URL in Vercel's `NEXT_PUBLIC_API_BASE_URL`. Add the Clerk production webhook URL.
8. If Render does not offer the free Key Value (one already used in the workspace), see §6.3 for the options.
9. Rollback: service → **Deploys** → redeploy an earlier successful deploy.

---

## 12. Deploying the website on Vercel Hobby (later)

Hobby is free but for **personal, non-commercial** use. If DevMind starts earning money, move the client to Cloudflare Pages or Netlify (free) or pay for Vercel Pro.

1. vercel.com → sign in with GitHub **using the account that owns the Hobby team and that authored the commits** (§4.0) → **Add New → Project** → import `Warish-Labs/DevMind` (it must be **public**; Hobby cannot deploy private organization repos).
2. **Root Directory: `client`**. Framework preset **Next.js** (auto). Keep **"Include source files outside of the Root Directory in the Build Step" enabled**, because `client` imports `common`.
3. Node.js version **24.x** (Project Settings → General). Install command `pnpm install --frozen-lockfile`. Build command `pnpm build`. Output: automatic (`.next`).
4. Environment variables: the client table in §7 (Production and Preview). Preview deployments should point to a staging API only, never production.
5. Production branch `main`; every PR gets a preview URL.
6. Domain: Project → **Settings → Domains** → add `devmind.warishlabs.in`, then add the DNS record Vercel shows (§6.6). Then set `NEXT_PUBLIC_SITE_URL`, Clerk allowed origins and the server CORS list.
7. **Output:** your public URL. Put it in the GitHub About "Website" field and in the showcase README.
8. If a deploy is blocked with a message about commit authors or private repos: the commit email or the repo visibility does not match the Hobby team owner (§4.0, §4.1).

---

## 13. Publishing the VS Code extension

**Where it goes (both free):** the **Visual Studio Marketplace** (VS Code) and **Open VSX** (VSCodium, Cursor, Antigravity and others). You can also share the `.vsix` file directly. Publisher id: **`warishlabs`** (matches your brand).

### 13.1 Try it locally first

```bash
pnpm --filter extension package                          # creates devmind-0.0.1.vsix
code --install-extension extension/devmind-0.0.1.vsix    # install it in your VS Code
```

### 13.2 Visual Studio Marketplace (one-time setup)

1. Sign in at **dev.azure.com** with a Microsoft account and create an organization (any name).
2. In Azure DevOps: User settings → **Personal access tokens → New Token**. Organization: **All accessible organizations**. Scopes: **Custom defined → Marketplace → Manage**. Copy the token once.
3. Go to **marketplace.visualstudio.com/manage** → **Create publisher**. The publisher **ID is `WarishLabs`** (`WarishLabs.devmind-vscode`).
4. Publish:
   ```bash
   npx @vscode/vsce login WarishLabs        # paste the token
   npx @vscode/vsce publish --pre-release    # use a pre-release first; drop the flag for a stable release
   ```
5. The listing is published at **[https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode](https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode)**, installable via:
   ```text
   ext install WarishLabs.devmind-vscode
   ```
   Users also find it by searching "DevMind" in the VS Code Extensions view.

**Important:** VS Code's documentation says global Azure DevOps tokens **retire on 2026-12-01** and `vsce publish --azure-credential` (Microsoft Entra credentials) is the replacement [VERIFY at publish time]. Publish manually with the token now if you are before that date; Antigravity documents the credential-based path in `docs/runbooks/release-extension.md` for CI.

### 13.3 Open VSX

1. open-vsx.org → sign in with GitHub → open your profile settings → create an **access token**; sign the **Publisher Agreement** (needs an Eclipse account).
2. ```bash
   npx ovsx create-namespace <publisher> -p <token>
   npx ovsx publish extension/devmind-0.0.1.vsix -p <token>
   ```

### 13.4 Releasing through GitHub (after tokens exist)

Add `VSCE_PAT` and `OVSX_PAT` to the `extension-release` environment (§4.5), bump the version in `extension/package.json` (Antigravity does this in a PR), merge, then:

```bash
git switch main && git pull --ff-only
git tag ext-v0.1.0 && git push origin ext-v0.1.0
```

Approve the publish job in the Actions run when it pauses.

### 13.5 Listing quality

The extension needs a 128 px icon (`brand/vscode/icon.png`, already prepared), a README with screenshots, a license, and `repository` fields. Marketplace pages load README images over **HTTPS**; because the repo is public, images served from `raw.githubusercontent.com/Warish-Labs/DevMind/...` load fine.

---

---

## 14. Screenshots checklist (you take these after each phase)

**Home page** (after S1 merges): `pnpm --filter client dev`, open Chrome at 1440 × 900. Antigravity's `pnpm screenshots` produces the standard set automatically in `docs/assets/screenshots/`; take extras by hand: (1) hero after the animation, (2) hero mid-animation, (3) the Brain section with a layer selected, (4) the walkthrough, (5) the privacy ledger toggled, (6) the custom cursor over the main button, (7) mobile 390 px and tablet 768 px.

**Extension** (after S2 merges): F5 → second window on the fixture project, VS Code **Dark Modern** theme, window about 1600 × 1000, zoom 100%. Shots listed in `docs/runbooks/screenshots.md`: Findings tree, squiggle with hover, Project structure, Scan progress with status bar, Sync view, consent preview, command palette, Database view. Save as `docs/assets/screenshots/extension-01-findings.png` and so on.

All screenshots show **example/fixture data** and say so; do not describe them as a working product. After each phase, refresh the personal showcase README (§4.7) with the new images.

---

---

## 15. Troubleshooting and FAQ

| Situation | What to do |
|---|---|
| Antigravity stops mid-task | Type `continue`. It re-reads `BRAIN.md` and `PLAN.md` |
| It asks for something you do not understand | Say "explain the HUMAN-STEP and give me the exact clicks"; it must point to a section here |
| CI is red | Type `continue` (it fixes the same branch); if repeated, paste the failing job name |
| `ci-gate` is not in the ruleset picker | It appears only after it has run at least once on a PR |
| You pushed to `main` by mistake | Do not force-push. Tell Antigravity; it reverts through a PR. The `main-guard` workflow will also open an issue |
| `pnpm: command not found` | `corepack enable` (or `npm i -g corepack`) |
| `docker: permission denied` | Log out and in after `usermod -aG docker $USER` |
| The live API is slow on the first request | Render free sleeps; wait about a minute. The UI shows "Server waking up" |
| Jobs seem stuck after idle time | The worker lives inside the web service and sleeps with it; open the app so it wakes, and the startup sweep resumes them |
| Vercel refuses to deploy | Repo must be public; commit email must belong to the Hobby team owner (§4.0) |
| Neon first query is slow | The free database suspends after about 5 minutes idle |
| Out of Render hours | 750 free hours are shared per workspace; stop unused free services |
| Cursor on the home page looks odd | Footer **Preferences**: turn the custom cursor off. It is already off on touch and with "reduce motion" |
| Free LLM gives rate-limit errors | Expected on free tiers; use the fake provider for development and wait between runs |
| Where is my data deleted? | Project settings → delete data (M9); see docs/07 |

---

## 16. Security checklist for you

- The repo is **public**: no keys, no `.env`, no private source, no screenshots with secrets.
- Turn on **secret scanning and push protection** (§4.3). If a key leaks, **revoke it at the provider immediately**, then create a new one.
- Use different keys for local, staging and production; prefer restricted keys.
- Free LLM tiers can use your prompts: only synthetic or public code.
- Merge only after `ci-gate` is green and you have read the PR description.
- Two-factor authentication on GitHub (both accounts), Render, Vercel, Clerk, Neon, the Marketplace publisher account and your DNS provider.
- Keep Render and Vercel previews pointed at staging, never at production data.

---

## 17. Kickoff message for Antigravity (paste this to start)

```text
You are the lead engineer for DevMind. Read docs/ANTIGRAVITY_PROMPT.md completely and follow it exactly.
The real repository is Warish-Labs/DevMind (public). Never touch mdwarishansari/DevMind. Everything must run on free tiers (ADR-046).
Start at section 16 ("Start now"). Use docs/SETUP-GUIDE.md for owner-side steps and keep it accurate.
Work in small feature/fix branches, commit after every task, never push to main, open PRs and stop for my merge.
Keep PLAN.md and BRAIN.md updated. When I type "continue", follow section 3.3 of the prompt.
Build order: P0 foundation, then the home page (S1), then the extension UI (S2), then the README showcase, then M1 onward.
```
