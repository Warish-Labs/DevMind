# GitHub Integration and PR Intelligence Operational Runbook

> **Governing documents:** [docs/01 §9 (CAP-05, CAP-06)](../01-product-requirements.md#cap-05-code-review-intelligence-release-11) · [docs/03 §3, §10, §11](../03-data-model-and-api.md) · [docs/05 §6.4, §6.5](../05-agents-and-llm-workflows.md#64-reviewbuddy-11) · [docs/07 §3, §10, §11](../07-security-privacy-and-threat-model.md#10-secrets-and-key-management) · [docs/10 §11, §18](../10-deployment-and-operations.md#11-environment-variables-and-secrets) · [ADR-014](../12-architecture-decisions-and-open-questions.md#adr-014-resend) · [ADR-015](../12-architecture-decisions-and-open-questions.md#adr-015-github-integration-path) · [ADR-046](../12-architecture-decisions-and-open-questions.md#adr-046-free-only-constraint-and-free-deployment-profile) · [ADR-047](../12-architecture-decisions-and-open-questions.md#adr-047-repository-ownership-and-visibility).
> **Never commit real values.** Placeholders only in documentation and `.env.example` files. Never log user source code or decrypted access tokens.

---

## 1. Subsystem overview

The DevMind GitHub Integration & PR Intelligence subsystem (Milestone 11) provides automated pull request mirroring, change-impact analysis, checklist rule evaluation, and collaborative workspace invitations:

1. **GitHub OAuth & Repository Binding:** Users authenticate with GitHub via OAuth (`/api/v1/github/oauth/authorize`), granting granular read permissions. OAuth access tokens are encrypted at rest using AES-256-GCM envelope encryption (`DEVMIND_ENCRYPTION_KEYS`) and bound to projects via `GitHubRepositoryBinding`.
2. **Webhook Ingestion Engine:** GitHub webhooks deliver real-time events (`ping`, `push`, `pull_request`, `installation`) to `/api/v1/webhooks/github`. Requests are validated using HMAC-SHA256 (`X-Hub-Signature-256`), deduplicated via delivery ID (`X-GitHub-Delivery`) against Redis/memory idempotency locks, and dispatched asynchronously.
3. **PR Intelligence (PRAgent):** Traverses the repository graph to calculate change-impact blast radius, symbol-level blast radiuses, modified routes, schema migrations, and risk ratings (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
4. **Review Intelligence (ReviewBuddy):** Parses unified diffs and evaluates declarative custom review rules (`ReviewRule`) across validation, authorization, error handling, documentation, and structural patterns.
5. **Human Approval Gate (ADR-015):** PR comments and code modifications are strictly gated behind human approval. DevMind never automatically posts comments or merges pull requests without explicit user intervention.
6. **Workspace Invitations (Resend):** Cryptographically secure transactional email invitations powered by Resend free tier on the verified `warishlabs.in` domain, using SHA-256 hashed 7-day tokens and immutable audit logging.

---

## 2. Environment variables and secrets

| Variable | Scope / Secret | Description | Where configured |
|---|---|---|---|
| `DEVMIND_GITHUB_CLIENT_ID` | API / Public | GitHub OAuth App Client ID | Render web service env |
| `DEVMIND_GITHUB_CLIENT_SECRET` | API / **Secret** | GitHub OAuth App Client Secret | Render web service env |
| `DEVMIND_GITHUB_WEBHOOK_SECRET` | API / **Secret** | Shared secret for verifying `X-Hub-Signature-256` | Render web service env, GitHub Webhook settings |
| `DEVMIND_ENCRYPTION_KEYS` | API, Worker / **Secret** | JSON list of base64 keys for envelope encryption | Render web service env |
| `DEVMIND_RESEND_API_KEY` | API / **Secret** | Resend API key for transactional emails | Render web service env |
| `DEVMIND_EMAIL_FROM` | API / Public | From sender address (`DevMind <invitations@warishlabs.in>`) | Render web service env |
| `DEVMIND_APP_BASE_URL` | API / Public | Base URL for invite acceptance links (`https://devmind.warishlabs.in`) | Render web service env |
| `DEVMIND_KILL_WEBHOOKS` | API / Public | Kill switch (`true`/`false`) to halt webhook processing | Render web service env |

---

## 3. Operational procedures

### 3.1 GitHub Webhook secret rotation

When the shared webhook secret needs rotation:

1. **Generate replacement secret:**
   ```bash
   openssl rand -base64 32
   ```
2. **Update GitHub Webhook configuration:**
   - Navigate to GitHub Organization / Repository -> **Settings** -> **Webhooks**.
   - Edit the DevMind webhook (`https://api.devmind.warishlabs.in/api/v1/webhooks/github`).
   - Enter the new secret into the **Secret** field and click **Update webhook**.
3. **Update DevMind service environment:**
   - Log into Render Console -> DevMind Web Service -> **Environment**.
   - Set `DEVMIND_GITHUB_WEBHOOK_SECRET` to the new secret string.
   - Click **Save Changes** (triggers rolling zero-downtime deployment).
4. **Verify signature acceptance:**
   - In GitHub Webhook settings, select **Recent Deliveries** and click **Redeliver** on a recent ping or PR event.
   - Ensure the delivery response is `200 OK` with JSON body `{"status": "ok", "action": "pong"}` or `{"status": "ok", ...}`.

### 3.2 GitHub OAuth credentials rotation

If GitHub OAuth App Client Secret is disclosed:

1. **Revoke existing secret:**
   - Navigate to GitHub Organization -> **Settings** -> **Developer settings** -> **OAuth Apps** -> DevMind.
   - Click **Generate a new client secret**.
   - Delete the compromised secret after the new secret is deployed.
2. **Update Render environment:**
   - Update `DEVMIND_GITHUB_CLIENT_SECRET` in Render.
   - Save changes and await container restart.
3. **Verify OAuth flow:**
   - In DevMind web app, navigate to a project -> **Settings** -> **GitHub Connection**.
   - Initiate OAuth connection flow to confirm successful token exchange.

### 3.3 Webhook delivery failure triage & manual replay

When webhook deliveries fail or show high error rates:

1. **Inspect GitHub Delivery History:**
   - Navigate to GitHub -> Repository / Org **Settings** -> **Webhooks** -> **Recent Deliveries**.
   - Check the HTTP response status code:
     - `401 Unauthorized`: HMAC signature mismatch (`integration.github.signature_invalid`). Check `DEVMIND_GITHUB_WEBHOOK_SECRET`.
     - `400 Bad Request`: Payload is malformed JSON or unparseable.
     - `404 Not Found`: Webhook router path incorrect. Ensure URL is `/api/v1/webhooks/github`.
     - `422 Unprocessable Entity`: Missing `X-GitHub-Event` or required header.
     - `503 Service Unavailable`: Subsystem kill switch `DEVMIND_KILL_WEBHOOKS=true` is active.
2. **Manual Replay via GitHub UI:**
   - GitHub retains webhook delivery records for 30 days.
   - In the **Recent Deliveries** tab, select the failed delivery and click **Redeliver**.
   - DevMind's webhook handler is strictly idempotent; deliveries with duplicate `X-GitHub-Delivery` IDs return `200 OK` with `status: "ignored_duplicate"`.
3. **Manual Replay via CLI / curl:**
   ```bash
   PAYLOAD='{"action":"opened","pull_request":{"id":123,"number":42,"title":"Fix auth","state":"open","head":{"sha":"abc1234"},"base":{"sha":"def5678"},"user":{"login":"octocat"}},"repository":{"id":999,"full_name":"Warish-Labs/DevMind"}}'
   SECRET="your_webhook_secret_here"
   SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')
   
   curl -X POST "https://api.devmind.warishlabs.in/api/v1/webhooks/github" \
     -H "Content-Type: application/json" \
     -H "X-GitHub-Event: pull_request" \
     -H "X-GitHub-Delivery: manual-replay-$(date +%s)" \
     -H "X-Hub-Signature-256: sha256=$SIG" \
     -d "$PAYLOAD"
   ```

### 3.4 GitHub rate limiting mitigation

GitHub REST API imposes rate limits (5,000 requests/hour for OAuth tokens; 60 requests/hour unauthenticated).

1. **Symptoms:**
   - Logs show `integration.github.rate_limited` or HTTP `429 Too Many Requests`.
   - PR analysis tasks fail with `RateLimitExceededError`.
2. **Mitigation:**
   - Check remaining quota in rate limit headers (`x-ratelimit-remaining`, `x-ratelimit-reset`).
   - DevMind caches repository diffs and tree structures during PR analysis; avoid repeated re-analysis of identical `head_sha`.
   - If a tenant account is blocked, guide them to wait for the reset window or bind a repository under a GitHub Organization token with higher limits.

### 3.5 Emergency kill switch activation

If webhooks are flooded or an upstream provider is compromised:

1. **Set `DEVMIND_KILL_WEBHOOKS=true`** in the Render service environment.
2. The webhook receiver immediately rejects inbound requests with `503 Service Unavailable` without enqueuing background tasks or querying PostgreSQL.
3. Once the incident is mitigated, set `DEVMIND_KILL_WEBHOOKS=false` and redeploy.

---

## 4. Resend email and workspace invitations

### 4.1 Domain and sender verification

- DevMind sends transactional emails from `notifications@warishlabs.in` or `invitations@warishlabs.in`.
- Sending domain `warishlabs.in` is pre-verified in Resend DNS (DKIM, SPF, MX).
- The Resend client includes an automatic offline mock fallback: if `DEVMIND_RESEND_API_KEY` is not configured or uses a placeholder (e.g. `re_REPLACE_ME`), emails are simulated in memory and logged securely without network failures.

### 4.2 Free tier quota management (ADR-046)

- **Resend Free Tier Quota:** 3,000 emails/month, 100 emails/day.
- Rate limiting on invitation dispatch prevents exhaustion:
  - Max 10 pending invitations per workspace.
  - Workspace member invites are throttled per user principal.
- If daily quota is exceeded (HTTP 429 from Resend), invitations remain stored in database as `PENDING`; administrators can copy the invitation link directly via the UI (`WorkspaceMembersManager.tsx`) to share out-of-band.

### 4.3 Stale invitation cleanup

Workspace invitations expire after 7 days:
```sql
-- Query expired, unaccepted invitations
SELECT id, workspace_id, email, created_at, expires_at
FROM workspace_invitations
WHERE accepted_at IS NULL AND expires_at < NOW();

-- Clean up expired invitations older than 30 days
DELETE FROM workspace_invitations
WHERE accepted_at IS NULL AND expires_at < NOW() - INTERVAL '30 days';
```

---

## 5. Audit and compliance verification

All PR intelligence actions, review evaluations, and workspace invitations emit immutable structured audit log events:

- `workspace.invitation.created`: Emitted when an invite is issued with recipient email and assigned role.
- `workspace.invitation.revoked`: Emitted when an invitation is cancelled prior to acceptance.
- `workspace.invitation.accepted`: Emitted when a user completes the token verification and joins the workspace.
- `pr.analysis.triggered`: Emitted when a PR change-impact analysis starts.
- `pr.comment.approved`: Emitted when a human explicitly approves a PR comment posting.

Never log:
- Decrypted GitHub OAuth tokens or personal access tokens.
- Raw customer repository source code or diff hunks in audit tables.
- Raw plaintext invitation tokens (only SHA-256 hashes are stored).
