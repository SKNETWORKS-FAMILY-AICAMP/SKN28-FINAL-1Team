# n8n Pipeline Security Review (2026-07-10)

## 1. Docker Compose Security Findings

| Item | Finding | Risk Level |
|------|---------|------------|
| Basic Auth | `N8N_BASIC_AUTH_ACTIVE=true` — enabled, credentials via env vars | OK |
| Port Exposure | Port 5678 bound to `0.0.0.0:5678` — exposed to all interfaces | HIGH |
| Volume Mounts | Only `n8n_data` named volume mounted — no secret files mounted | OK |
| Network Mode | Default bridge network — no isolation defined | MEDIUM |
| Hardcoded Credentials | None found — all secrets use `${VAR}` env var substitution | OK |
| Cookie Security | `N8N_SECURE_COOKIE=false` — HTTPS cookies disabled | MEDIUM |
| AWS Credentials | `${AWS_ACCESS_KEY_ID}`, `${AWS_SECRET_ACCESS_KEY}` env-injected | OK |

**Key Issue**: The compose file binds port 5678 to `0.0.0.0`, making it reachable from all network interfaces. The README acknowledges this and recommends SSH tunneling when on EC2, but for local Docker Desktop this exposes the n8n UI on the local network.

---

## 2. Credential Injection Design

### Secrets n8n needs
- `N8N_USER` / `N8N_PASSWORD` — n8n basic auth credentials
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` — S3 access to `s3://skn28-cozy` (team account 071853465256)
- KMA API key (not yet in compose but referenced in pipeline design)

### Recommended approach: Infisical CLI (`infisical run`)
The current `infisical run --env=dev -- docker compose up -d` pattern is the correct approach:
- Secrets never touch `.env` files or shell history
- Team credentials are stored in Infisical (team account 071853465256, not the EC2 role)
- Credentials are injected at process startup inside the container

### Credential passing to containers
- Use `infisical run --env=dev -- docker compose up -d` (already in place)
- Inside containers, n8n Credentials objects should be used for workflow nodes (AWS S3 node, HTTP Request nodes)
- For Python scripts called via `Execute Command` or `HTTP Request`, pass only non-secret config via CLI args; use IAM roles or temporary tokens where possible

### n8n workflow nodes needing credentials
1. **AWS S3 node** — list/get objects from `s3://skn28-cozy` (uses `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`)
2. **HTTP Request node** — calling FastAPI workers or external APIs (KMA, Slack/Discord webhooks)
3. **Execute Command** — calling `uv run python ...` scripts (AWS credentials already available in container env)

---

## 3. Secret Leakage Scan

| File | Secrets Found |
|------|---------------|
| `pipeline/n8n/docker-compose.yml` | AWS key env vars referenced (no values hardcoded) |
| `pipeline/n8n/README.md` | None — no actual secret values |
| `pipeline/n8n/workflows/` | No workflow files exist yet |

**No hardcoded secret values found.** All credentials are properly referenced as `${VARIABLE_NAME}` substitution tokens. No workflow JSON files exist in the repository yet.

---

## 4. Security Checklist

- [ ] **Bind n8n port to localhost only** — change `ports: - "5678:5678"` to `ports: - "127.0.0.1:5678:5678"` to prevent external exposure when running locally
- [ ] **Use `N8N_SECURE_COOKIE=true`** in production — only set to `false` for local HTTP development
- [ ] **Never commit actual AWS credentials** — all access should flow through Infisical-injected env vars
- [ ] **Restrict S3 bucket policy** — ensure `s3://skn28-cozy` bucket policy limits access to the team account (071853465256) only
- [ ] **Enable network isolation** — define a custom Docker network for n8n and dependent services rather than using default bridge
- [ ] **Add resource limits** — set `mem_limit`, `cpus` in docker-compose to prevent container resource exhaustion
- [ ] **Set `N8N_BASIC_AUTH_USER/PASSWORD` via Infisical** — confirm these are stored as Infisical secrets, not in any `.env` or config file
- [ ] **Rotate AWS access keys regularly** — if long-lived team account keys are used, rotate every 90 days; prefer IAM role with temporary tokens where possible