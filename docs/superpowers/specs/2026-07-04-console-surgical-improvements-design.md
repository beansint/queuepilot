# Console surgical improvements — design

**Date:** 2026-07-04 · **Scope:** `frontend/` only (one backend endpoint already exists) · **Slice:** post-E polish

## Context / findings

The console (`frontend/src/App.tsx`) is a router-less React SPA that conditionally renders the
marketing `Landing` (when auth-gated) or the console shell. Six asks, all frontend:

### The "no suggested reply" question — answered: **working as designed; UI presents it wrong**
The ransomware ticket scored **confidence 0.32** (below the 0.35 escalate line) **and SLA risk 0.94**.
Either alone trips the escalate branch. In `app/analyze/graph.py:167`, an `escalate` decision routes
**straight to `END`** — the `draft_reply` node never runs, so `suggested_reply` is `null` **by design**
(the guarded-copilot thesis: refuse to draft when uncertain, especially on a security incident).

The defect is in `SuggestedReply.tsx`: it only branches on *reply* vs *clarification*. Escalations fall
through to the reply branch → hollow "No suggested reply was generated" + dead Send/Edit/Copy buttons.
The SUMMARY rail already correctly labels this "Escalation" — the main column just never got the
matching treatment. **Fix = give escalation its own panel**, not force a draft (a locked guardrail).

## Decisions (confirmed with user)
1. **Escalation → dedicated panel** with reason (confidence vs handle line, SLA risk), the missing-info
   list, and actions **Assign to teammate** (mock toast) + **Copy ticket for handoff**. **No "Draft
   anyway"** — overriding the guardrail contradicts the product thesis + a 🔒 locked decision.
2. **Navigation = hash routes, zero deps** (`#/`, `#/evidence`, `#/overview`). Real URLs + back button.
3. **Sidebar keeps only real destinations:** Analysis, Evidence, Overview, Support (→ contact). Remove
   Queue, Insights, Evidence base, Routing rules, Thresholds, Integrations, Settings.

## Architecture

### A tiny hash router (`src/lib/useHashRoute.ts`)
- `type Route = "console" | "evidence" | "overview"`; parse `location.hash` → route; `hashchange` listener.
- Returns `{ route, navigate(route) }`. No dependency. Console is the default/empty-hash route.
- Auth gating still wins: if `authGate === "gated"`, show `Landing` regardless of route (except…) — see below.

### Routing behavior in `App.tsx`
- `overview` route → render `Landing` in **authed mode** (see Landing change) even when logged in, with a
  "Back to console" affordance. When *gated*, any route falls back to `Landing` in gated mode (unchanged).
- `evidence` route → render the new `EvidencePage` **if** a result exists; otherwise redirect to `console`
  (empty state — evidence only exists after an analysis). Result already lives in `App` state; no refetch.
- `console` route → current shell.

### Components
| File | Change |
|---|---|
| `console/EscalationPanel.tsx` **(new)** | Reason header (confidence + `handleLineSubline`, SLA risk pill), "Why no auto-reply" + missing-info list (reuse `resolveMissingInfo`), actions: **Assign to teammate** (toast), **Copy ticket for handoff** (copies submitted text). Reuses hero/SummaryRail tokens for visual consistency. |
| `console/SuggestedReply.tsx` | Add escalate branch: when `resolveDecision(response) === "escalate"`, render `<EscalationPanel>` instead of the reply card. Reply + clarification branches unchanged. |
| `console/EvidencePage.tsx` **(new)** | Full-screen "Evidence — similar tickets" page: header + Back-to-analysis, the submitted ticket for context, and all neighbors with **full (untruncated) snippet**, score bar, queue/priority/type. Modeled on Elicit's ranked-evidence view. |
| `console/SimilarTicketsTable.tsx` | Add a "View all →" affordance in the section header that `navigate("evidence")`. Inline table stays as the at-a-glance summary. |
| `console/NavRail.tsx` | Rebuild link list to the 4 real destinations; drive `active` from current route; each item `navigate(route)` (Support → external `CONTACT_URL`). Add **Log out** button in the user footer. |
| `console/TopBar.tsx` | (optional) avatar unchanged; logout lives in NavRail to match Intercom's account-menu pattern. |
| `marketing/Landing.tsx` | Add optional `authed?: boolean` + `onEnterConsole?: () => void`. When authed: TopNav/Hero primary CTA becomes **"Open console"** (calls `onEnterConsole`) instead of opening the invite modal; add a small "Back to console" top-left. Gated behavior unchanged. |
| `lib/api.ts` | Add `logout(): Promise<void>` → `POST /logout` (endpoint exists at `app/main.py:86`). |
| `App.tsx` | Wire `useHashRoute`, render by route, pass `handleLogout` (calls `logout()` then re-`checkAuth()` → returns to gated Landing), pass `onEnterConsole`/`authed` to Landing on the overview route. |

### Logout flow
`NavRail Log out → api.logout() → checkAuth()`. Backend `delete_cookie` clears the session; `checkAuth`
re-reads `/auth/status` → `required && !authenticated` → `authGate="gated"` → Landing. Toast on success.

## Error handling
- `logout()` failure → toast "Couldn't sign out", stay put (no half-state).
- `evidence` route with no result → silent redirect to `console` (guard in render).
- Copy-for-handoff uses the existing clipboard try/catch pattern (toast on failure).

## Testing (per verification rubric)
- **Unit:** `useHashRoute` (parse/navigate/hashchange); extend `SimilarTicketsTable` test for the View-all
  link; new `EscalationPanel` test (renders reason + missing info, no Send button); `api.test.ts` logout.
- **Build/typecheck:** `pnpm build` + `pnpm exec tsc`.
- **Playwright (golden + edge):** log in (invite code from project memory) → analyze the escalation sample
  → assert EscalationPanel (no reply card) → open Evidence via View-all → Overview via sidebar → Back to
  console → Log out → gated Landing. Edge: navigate to `#/evidence` before any analysis → lands on console.
- **Console/network scan** after the flow; **a11y**: keyboard-reach every nav item + logout + back links.

## Out of scope
Real assignment/queue backends, real "Draft anyway", persisting routes server-side, mobile nav drawer
(sidebar already `hidden md:flex`; Evidence/Overview pages will be responsive but no hamburger).
