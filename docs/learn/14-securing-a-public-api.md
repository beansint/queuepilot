# 14 — Securing a public API (invite cookie, rate limiting, daily cap)

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: E7 (Slice E) · Runnable companion: `uv run python learn/14_securing_a_public_api.py`

## 1. Concept
Once an API is publicly reachable, three separate concerns show up that don't exist on `localhost`:

- **Authentication** — proving *who's allowed in* without building a whole user system. A **signed
  cookie** is a compact way to do this: the server hands the browser a token it can't forge (because
  forging it requires a secret key only the server has), the browser echoes it back on every request,
  and the server re-checks the signature — no server-side session store needed.
- **HMAC + constant-time compare** — an HMAC (`hmac.new(secret, message, sha256)`) proves a message
  came from someone who knows `secret` *and* hasn't been altered, without exposing the key. Comparing
  the resulting signature with `==` leaks timing information (`==` short-circuits at the first
  mismatched byte, so response time correlates with how many correct leading bytes an attacker
  guessed); `hmac.compare_digest` compares in constant time regardless of where the mismatch is.
- **HTTP-only + SameSite cookies** — `HttpOnly` means client-side JavaScript can never read the cookie
  (so a XSS bug can't steal the session token via `document.cookie`); `SameSite=Lax` stops the cookie
  from being sent on cross-site requests initiated by other sites (a CSRF mitigation), while still
  allowing normal top-level navigation.
- **Rate limiting** — capping *how often* one client can call an expensive/paid endpoint, so one script
  (or one leaked link) can't hammer the service.
- **A global daily cap** — a second, coarser guard: even if every individual client stays under the
  per-client limit, the *sum* of all traffic can still exhaust a shared budget (LLM/embedding/vector-DB
  free-tier quotas). The daily cap is the backstop for that.
- **12-factor config / secrets** — configuration (including secrets) lives in the environment, never in
  source or in a built artifact (a Docker image, a git commit). This is what makes "auth is disabled
  when unconfigured" a *safe* default rather than a footgun: no secret ever needs a placeholder value
  checked into the repo.

## 2. In QueuePilot
- **`app/auth.py`** — `sign`/`verify` implement HMAC-SHA256 signing with `hmac.compare_digest` for the
  signature check, using only the stdlib (`hmac`, `hashlib`, `base64`) — no new dependency
  (`05-DECISIONS-LOCKED.md` D16). `auth_required()` is `True` only when both `INVITE_CODE` and
  `SESSION_SECRET` are set; `require_auth` (a FastAPI dependency) is a pure no-op when it's `False`.
  `POST /login` checks the submitted code against `INVITE_CODE` with `hmac.compare_digest` (constant
  time, so an attacker can't time-guess the code), then sets `qp_session` — `HttpOnly`, `SameSite=Lax`,
  `Secure` outside `development` — via `issue_cookie_value()`.
- **`app/ratelimit.py`** — an in-process, thread-safe (`threading.Lock`) fixed-window counter per
  client IP (`RATE_LIMIT_PER_MIN`, default 20/min) plus a process-global counter that resets at UTC
  midnight (`DAILY_CAP`, default 500/day). No Redis — fine for the single free-tier Render instance
  this runs on (D16); the client IP is read from `X-Forwarded-For`'s first hop since Render sits
  behind a proxy, falling back to the raw socket peer.
- **`app/main.py`** — `POST /analyze` and `POST /feedback` carry
  `dependencies=[Depends(require_auth), Depends(rate_limit)]`; `GET /health`, `POST /login`,
  `POST /logout`, and `GET /auth/status` stay open (Render's health check and the frontend's
  "am I logged in?" probe must never 401).
- **Frontend** — `frontend/src/components/console/LoginGate.tsx` renders a code-entry screen when
  `GET /auth/status` reports `required && !authenticated`; `frontend/src/App.tsx` checks this once on
  mount and re-gates if a later `/analyze` call ever comes back `401` (session expired/cleared
  mid-session).

## 3. Why this way
- **No new runtime dependency.** `itsdangerous`/`slowapi` would work too, but stdlib `hmac` +
  in-process counters keep the image lean and the supply chain small (D16) — appropriate for one
  free-tier instance behind a single shared invite code, not a multi-tenant auth system.
- **Graceful-open when unconfigured**, mirroring how LangSmith tracing degrades to a no-op
  (`app/analyze/graph_analyzer.py`) and how `/feedback` degrades when LangSmith is unconfigured
  (`app/feedback.py`): the same code path runs whether or not `INVITE_CODE`/`SESSION_SECRET` are set,
  so local dev and the offline test suite never need fake secrets, and a bare `docker run` with no
  `--env-file` still serves a working (open) demo instead of a hard-locked one.
- **Signature-only verification, no hard expiry.** The token embeds an issued-at timestamp for future
  use (e.g. a rolling max-age), but Slice E doesn't need session expiry — a single shared invite code
  behind a small demo doesn't warrant the complexity yet; that's future-work, not a shipped guarantee.
- **In-process, not Redis-backed rate limiting.** Correct for exactly one instance (Render free tier).
  It would silently under-count with multiple instances/replicas — a real limitation, deliberately
  deferred (D16) rather than solved prematurely.
- **Per-IP *and* a global cap**, not just one. A per-IP-only limit lets many distinct IPs still drain a
  shared provider budget overnight if the invite code leaks; the daily cap is the backstop that caps
  total spend regardless of how traffic is distributed across IPs.

## 4. Verify it yourself
```bash
uv run python learn/14_securing_a_public_api.py
```
**Expected:** the script imports the *real* `app.auth.sign`/`verify` and proves a valid token verifies
while a tampered one is rejected (`None`), then exercises the real `app.ratelimit` counter directly —
the first `N` calls succeed and the `N+1`th raises the `429 rate limit exceeded` `HTTPException` — and
finally exercises the daily-cap counter the same way. It's fully offline: no network, no FastAPI
`TestClient`, just the real signing/limiter functions the app uses in production.

## 5. Self-quiz
1. Why is `hmac.compare_digest` used instead of `token == expected` to check the signature?
2. What does `HttpOnly` actually protect against, and what does it *not* protect against?
3. Why does QueuePilot need both a per-IP rate limit *and* a separate global daily cap — isn't one
   enough?
4. What happens to `POST /analyze` if `SESSION_SECRET` is set but `INVITE_CODE` is not (or vice
   versa)? Why is that the safe default rather than a half-broken state?

<details><summary>Answers</summary>

1. Python's `==` on strings/bytes short-circuits at the first differing byte, so comparison time leaks
   information about how many leading bytes were correct — an attacker measuring response latency
   could recover a valid signature byte-by-byte. `hmac.compare_digest` always takes the same time
   regardless of where (or whether) a mismatch occurs, closing that timing side-channel.
2. `HttpOnly` stops client-side JavaScript from reading the cookie via `document.cookie` — so a
   cross-site-scripting (XSS) bug on the page can't exfiltrate the session token. It does **not**
   protect against cross-site *request forgery* (a malicious page making the browser send an
   authenticated request); that's what `SameSite=Lax` is for, and it doesn't protect against network
   interception either — that's what `Secure` (HTTPS-only) is for.
3. A per-IP limit only bounds *one client's* call rate. If the invite code leaks and gets shared, many
   distinct IPs can each individually stay under the per-IP limit while the *sum* of their traffic
   still exhausts the shared LLM/embedding/vector-DB free-tier budget for the day. The global daily cap
   bounds total spend regardless of how many distinct clients are calling in.
4. `auth_required()` requires *both* to be set, so it stays `False` and `/analyze` stays open (no
   401 wall) — it does not go into a state where a code is required but no secret exists to sign
   cookies with (which would be unsatisfiable) or vice versa. A half-configured deployment fails safe
   toward "open, like before Slice E" rather than into a broken 401-everything or a fake-signed-cookie
   state.

</details>

## 6. Takeaway
Gating a public demo doesn't need a new dependency or a user database: an HMAC-signed, `HttpOnly`,
`SameSite=Lax` cookie proves "this browser knows the invite code" without a session store, a
constant-time compare closes the timing side-channel on the check itself, and a per-IP rate limit plus
a global daily cap are two different failure modes (one client hammering it vs. many clients draining
the shared budget) that both need their own guard — and every one of these gates degrades to "open,
like before Slice E" the moment its config is unset, so nothing ever breaks a deployment that hasn't
opted in yet.
