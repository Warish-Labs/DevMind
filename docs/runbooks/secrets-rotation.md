# Secrets Rotation Runbook

> **Governing documents:** [docs/10 §11](../10-deployment-and-operations.md#11-environment-variables-and-secrets) · [docs/07 §7](../07-security-privacy-and-threat-model.md) · [ADR-046](../12-architecture-decisions-and-open-questions.md#adr-046-free-only-constraint-and-free-deployment-profile) · [ADR-047](../12-architecture-decisions-and-open-questions.md#adr-047-repository-ownership-and-visibility).
> **Never commit real values.** Placeholders only in documentation and `.env.example` files.

---

## 1. Inventory of secrets

| Secret | Environment variable | Where configured | Impact of compromise | Rotation frequency |
|---|---|---|---|---|
| Neon DB (pooled) | `DEVMIND_DATABASE_URL` | Render web service env | Database read/write access | 90 days or on disclosure |
| Neon DB (direct) | `DEVMIND_DATABASE_URL_DIRECT` | Render web service env | Migration / direct DDL access | 90 days or on disclosure |
| Redis / Key Value | `DEVMIND_REDIS_URL` | Render web service env | Celery broker injection / rate limit wipe | 90 days or on disclosure |
| Clerk webhook | `DEVMIND_CLERK_WEBHOOK_SECRET` | Render web service env, Clerk dashboard | Forged user creation / deletion events | On disclosure |
| Extension pepper | `DEVMIND_EXT_TOKEN_PEPPER` | Render web service env | Weakens offline hash cracking of extension tokens | On disclosure |
| Envelope encryption keys | `DEVMIND_ENCRYPTION_KEYS` | Render web service env | Decrypt stored OAuth tokens / third-party credentials | Key rotation with dual-key window |
| GitHub OAuth secret | `DEVMIND_GITHUB_OAUTH_CLIENT_SECRET` | Render web service env, GitHub Org settings | Impersonate DevMind GitHub integration | On disclosure |
| GitHub webhook secret | `DEVMIND_GITHUB_WEBHOOK_SECRET` | Render web service env, GitHub Org settings | Forged webhook payloads | On disclosure |

---

## 2. Emergency response protocol (accidental disclosure)

If any secret, key, or token is committed to git or exposed in logs:

1. **STOP immediately.** Do not attempt to hide it by rewriting git history alone; the commit may already be fetched or mirrored.
2. **Revoke the secret immediately** at the provider (Neon, Clerk, GitHub, Render).
3. **Notify the repository owner** ([Warish-Labs/DevMind](https://github.com/Warish-Labs/DevMind)).
4. **Generate a replacement secret** with equivalent permissions.
5. **Update Render / Vercel environment variables** and trigger a redeploy.
6. **Verify health endpoints:** `curl -sSf https://api.devmind.warishlabs.in/healthz`.
7. **Clean up git history** (if committed locally or pushed) using `git filter-repo` or BFG, force-pushing only with owner authorization and coordinated team notification.

---

## 3. Routine rotation procedures

### 3.1 Neon Database password

1. Log into the Neon Console (`console.neon.tech`).
2. Navigate to the DevMind project -> **Roles**.
3. Reset password for the application role (`devmind_app`).
4. Update `DEVMIND_DATABASE_URL` (pooled) and `DEVMIND_DATABASE_URL_DIRECT` (direct) in the Render web service environment.
5. Save changes in Render (triggers automatic zero-downtime rolling restart).
6. Verify `/healthz` returns `{"status": "ok"}`.

### 3.2 Render Key Value (Redis)

1. In Render dashboard, navigate to the DevMind Key Value instance.
2. If credentials need rotation, recreate or update the connection string.
3. Update `DEVMIND_REDIS_URL` in the Render web service environment.
4. Restart service.

### 3.3 Envelope encryption keys (`DEVMIND_ENCRYPTION_KEYS`)

DevMind uses dual-key envelope encryption with key IDs (e.g. `{"active": "v2", "keys": {"v1": "...", "v2": "..."}}`):

1. Generate a new cryptographic key: `openssl rand -hex 32`.
2. Add the new key with ID `v2` while retaining `v1` in `DEVMIND_ENCRYPTION_KEYS`.
3. Set `"active": "v2"`. New encryptions use `v2`; old records decrypted with `v1`.
4. Run the re-encryption background job: `uv run python -m app.cli reencrypt-credentials`.
5. After all records are migrated to `v2`, remove `v1` from the JSON configuration.

### 3.4 Extension token pepper (`DEVMIND_EXT_TOKEN_PEPPER`)

1. Generate new pepper: `openssl rand -hex 32`.
2. Note: Rotating pepper invalidates existing extension sessions (users will re-authenticate via `/extension/connect`).
3. Update `DEVMIND_EXT_TOKEN_PEPPER` in Render environment and restart.

---

## 4. Verification checklist

- [ ] New secret configured in hosting provider environment
- [ ] Service restarted cleanly
- [ ] Health check `/healthz` returns 200
- [ ] No plaintext secrets in logs or git commits
- [ ] Old credentials revoked at provider
