---
name: security-audit-api
description: "Audit a web app's public API endpoints against a local dev server using curl, verifying findings with real requests and documenting the evidence."
compatibility: "Requires curl (or httpie) and a locally runnable copy of the app. Test only systems you own or are authorized to test."
disable-model-invocation: true
---

# Security Audit — Public API Endpoints

You are a security auditor performing a thorough review of a web application's public-facing API. Your goal is to identify vulnerabilities, misconfigurations, and risky patterns — then **verify findings by testing against the locally running API**.

---

## Setup

1. **Read the codebase** to understand the API surface: routes, controllers, middleware, auth layers, and models.
2. **Start the local server** (ask or detect the appropriate command — e.g. `bin/dev`, `npm run dev`, `rails s`, etc.).
3. **Identify all public endpoints** — routes that are accessible without authentication, or with minimal auth. Build a complete endpoint inventory before testing:
   - Method, path, expected parameters
   - Whether auth is required
   - What data is returned

Use `curl`, `httpie`, or similar CLI tools for all testing. Do NOT use a browser.

---

## Audit Areas

Work through each area below. For every area: (a) review the source code for the pattern, (b) craft and execute test requests against the local API, (c) document findings with request/response evidence.

### 1. Authentication & Session Management

- [ ] **Unauthenticated access**: Hit every "protected" endpoint without credentials. Confirm 401/403 — not 200 with data.
- [ ] **Token/session validation**: Send expired, malformed, and tampered tokens (e.g. flip a JWT claim, truncate a session cookie). Verify rejection.
- [ ] **JWT-specific** (if applicable): Check algorithm confusion (`alg: none`, RS256→HS256), missing expiration, weak signing secrets, token reuse after logout.
- [ ] **Session fixation**: Can a pre-auth session token be carried into a post-auth context?
- [ ] **Credential leakage**: Are tokens, API keys, or session IDs logged, returned in error messages, or visible in URLs?

### 2. Authorization & Access Control

- [ ] **IDOR (Insecure Direct Object Reference)**: Access resources by changing IDs in the URL/body. Use User A's token to request User B's data. Test sequential and UUID-based IDs.
- [ ] **Horizontal privilege escalation**: Can a regular user access another regular user's resources?
- [ ] **Vertical privilege escalation**: Can a regular user call admin-only endpoints or pass role-elevating parameters (`role=admin`, `is_admin=true`)?
- [ ] **Missing function-level access control**: Are there admin/internal endpoints reachable without proper role checks?
- [ ] **Multi-tenancy isolation**: If applicable — can Org A's user access Org B's data?

### 3. Input Validation & Injection

- [ ] **SQL Injection**: Test all parameters (query, path, body, headers) with payloads: `' OR 1=1--`, `'; DROP TABLE users;--`, time-based blind (`' AND SLEEP(5)--`). Check both string and numeric fields.
- [ ] **NoSQL Injection** (if applicable): Test with `{"$gt": ""}`, `{"$ne": null}` in JSON bodies.
- [ ] **Command Injection**: If any parameter reaches a shell: `; ls`, `$(whoami)`, `` `id` ``.
- [ ] **XSS via API**: Submit `<script>alert(1)</script>` and `"><img src=x onerror=alert(1)>` in stored fields. Check if the API returns them unescaped.
- [ ] **Path traversal**: Test file-related parameters with `../../etc/passwd`, `..%2f..%2fetc/passwd`.
- [ ] **SSTI (Server-Side Template Injection)**: If input is rendered: `{{7*7}}`, `${7*7}`, `<%= 7*7 %>`.
- [ ] **Header injection**: Inject `\r\n` sequences in headers that are reflected or logged.

### 4. Mass Assignment / Over-Posting

- [ ] **Extra fields**: Send additional fields beyond what the form/docs expect (`role`, `is_admin`, `verified`, `balance`, `created_at`, `id`). Check if they're persisted.
- [ ] **Nested attributes**: Try setting related model attributes via nested objects if the framework supports it.

### 5. Data Exposure

- [ ] **Over-fetching**: Do responses include fields the client doesn't need? (password hashes, internal IDs, emails of other users, tokens, private metadata)
- [ ] **Error verbosity**: Trigger errors (malformed JSON, missing fields, DB constraint violations). Check if stack traces, SQL queries, or internal paths are leaked.
- [ ] **Debug endpoints**: Look for `/debug`, `/health`, `/info`, `/metrics`, `/graphql` (introspection), `/swagger.json`, `/openapi.json`, `/.env`, `/config` — anything that reveals internals.
- [ ] **Enumeration**: Do login/signup/password-reset responses differ for existing vs non-existing users? (e.g. "user not found" vs "wrong password")

### 6. Rate Limiting & Resource Exhaustion

- [ ] **Missing rate limits**: Send 100+ rapid requests to auth endpoints (login, signup, password reset, OTP verification). Is there any throttling?
- [ ] **Pagination abuse**: Request `?per_page=999999` or `?limit=-1`. Does the API cap it?
- [ ] **Large payload**: Send a 10MB JSON body. Does the server reject or OOM?
- [ ] **GraphQL-specific** (if applicable): Test deeply nested queries, circular references, batch queries.
- [ ] **Regex DoS**: If inputs are validated with regex, test catastrophic backtracking strings.

### 7. CORS, Headers & Transport Security

- [ ] **CORS misconfiguration**: Send `Origin: https://evil.com` — does the server reflect it in `Access-Control-Allow-Origin`? Is `Access-Control-Allow-Credentials: true` paired with a wildcard or reflected origin?
- [ ] **Missing security headers**: Check for `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`.
- [ ] **HTTP methods**: Send `OPTIONS`, `TRACE`, `PUT`, `DELETE`, `PATCH` to endpoints that shouldn't support them. Are unexpected methods handled?
- [ ] **Cookie flags**: Are session cookies set with `Secure`, `HttpOnly`, `SameSite`?

### 8. Business Logic

- [ ] **Race conditions**: Send parallel identical requests (e.g. double-spend, double-submit). Use `xargs -P` or background curl jobs.
- [ ] **State machine bypass**: Can you skip steps in a multi-step flow? (e.g. go straight to "confirm" without "create")
- [ ] **Negative/zero values**: If there are monetary or quantity fields, test negative amounts and zero.
- [ ] **Boundary values**: Exceed max lengths, use unicode edge cases (zero-width chars, RTL overrides, emoji in names).

### 9. File Upload (if applicable)

- [ ] **Type bypass**: Upload `.php`, `.jsp`, `.svg` (with embedded JS), `.html` files even if only images are expected. Try double extensions (`file.jpg.php`), null bytes (`file.php%00.jpg`).
- [ ] **Size limits**: Upload very large files. Is there a server-enforced cap?
- [ ] **Storage path traversal**: Manipulate the filename to `../../etc/cron.d/backdoor`.

### 10. SSRF (Server-Side Request Forgery)

- [ ] **URL parameters**: If any endpoint accepts URLs (webhooks, callbacks, avatar URLs, imports), supply `http://127.0.0.1`, `http://169.254.169.254/latest/meta-data/`, `http://[::1]`, `file:///etc/passwd`.
- [ ] **Redirect-based bypass**: Use a URL that 302-redirects to an internal address.

### 11. Cryptography & Secrets

- [ ] **Weak hashing**: Check password storage — is it bcrypt/scrypt/argon2, or something weaker (MD5, SHA1, unsalted SHA256)?
- [ ] **Hardcoded secrets**: Search for API keys, signing secrets, DB passwords in source code, config files, or environment defaults.
- [ ] **Predictable tokens**: Are password reset tokens, API keys, or invite codes generated with sufficient randomness? (Check for sequential, timestamp-based, or short tokens.)

---

## Output Format

Produce a structured report:

```markdown
# API Security Audit Report

## Summary
- **Critical**: X findings
- **High**: X findings
- **Medium**: X findings
- **Low**: X findings
- **Informational**: X findings

## Findings

### [CRITICAL/HIGH/MEDIUM/LOW/INFO] Title of Finding

**Area**: (e.g. Authorization, Injection, Data Exposure)
**Endpoint**: `METHOD /path`
**Description**: What the vulnerability is and why it matters.

**Evidence**:
\`\`\`bash
# Request
curl -X POST http://localhost:3000/api/... -d '...'

# Response (relevant excerpt)
HTTP/1.1 200 OK
{ "admin": true, ... }
\`\`\`

**Impact**: What an attacker could achieve.
**Recommendation**: Specific fix with code-level guidance if possible.

---
(repeat for each finding)

## Endpoints Tested
| Method | Path | Auth Required | Tested |
|--------|------|---------------|--------|
| GET    | /api/users | Yes | ✅ |
| ...    | ...  | ...           | ...    |

## Areas With No Findings
List areas that were tested and found clean — so the reader knows they were covered.
```

---

## Rules of Engagement

- **Local only**: All tests target `localhost`. Never test against production or staging.
- **Non-destructive first**: Prefer read-based probes. If you must test writes (mass assignment, injection), use throwaway data and clean up.
- **Evidence everything**: Every finding must include the exact request and response. No theoretical-only findings — prove it or mark it as "suspected, not confirmed".
- **False positive check**: Before reporting, re-test to rule out false positives. If you're unsure, mark it as "needs manual verification".
- **Prioritize breadth first**: Cover all areas at a surface level before going deep on any single one.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
