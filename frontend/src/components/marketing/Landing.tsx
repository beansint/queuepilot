import { useEffect, useState } from "react"
import {
  Activity,
  ArrowRight,
  GitFork,
  ListTodo,
  MessageSquareText,
  Route,
  Sparkles,
  ShieldCheck,
} from "lucide-react"
import { InviteGate } from "@/components/console/InviteGate"
import { CONTACT_URL, GITHUB_URL } from "@/lib/site"
import { cn } from "@/lib/utils"

interface LandingProps {
  onAuthed: () => void
}

const SPECS: { value: string; label: string }[] = [
  { value: "3,000", label: "real support tickets" },
  { value: "Hybrid", label: "dense + sparse retrieval" },
  { value: "8-stage", label: "LangGraph workflow" },
  { value: "ECE ≈ 0.15", label: "calibrated confidence" },
  { value: "340+", label: "tests, CI-gated" },
  { value: "Traced", label: "LangSmith eval" },
]

const CAPABILITIES = [
  {
    icon: Route,
    number: "01",
    title: "Auto-routing",
    description: "Every ticket gets a queue, priority, and category in one pass.",
  },
  {
    icon: MessageSquareText,
    number: "02",
    title: "Grounded replies",
    description: "Draft answers cite similar resolved tickets, not hallucinations.",
  },
  {
    icon: ShieldCheck,
    number: "03",
    title: "Guarded escalation",
    description: "Low confidence or high risk? It escalates to a human instead of guessing.",
  },
  {
    icon: Activity,
    number: "04",
    title: "Explainable & audited",
    description: "Every decision ships a confidence breakdown and a LangSmith trace.",
  },
]

const STACK_BADGES = ["FastAPI", "LangGraph", "Pinecone", "LangSmith", "React"]

const UPGRADES: {
  number: string
  title: string
  pill?: string
  description: string
  detail: string
  highlight?: boolean
}[] = [
  {
    number: "01",
    title: "Hybrid retrieval",
    description:
      "Dense embeddings match meaning; BM25 catches exact terms — error codes, product names, law numbers. QueuePilot blends both (normalized) with an alpha dial.",
    detail: "dense + sparse → normalize → hybrid_score(α)",
  },
  {
    number: "02",
    title: "Structured output",
    description: "The LLM fills a form, not a paragraph — decisions a system can act on.",
    detail: "category · queue · priority · sentiment",
  },
  {
    number: "03",
    title: "Agent assembly line",
    pill: "LangGraph",
    description:
      "One prompt becomes a chain of small nodes sharing a state dict, so every step's contribution is visible.",
    detail: "retrieve → classify → sentiment → assess → score → decide",
  },
  {
    number: "04",
    title: "Calibrated confidence",
    description:
      "Never ask the model how sure it is — LLMs are overconfident. Trust is built from observable signals: neighbour agreement, retrieval closeness, consistency, a missing-info penalty.",
    detail: "f(agreement, closeness, consistency, missing) — never f(LLM's claim)",
    highlight: true,
  },
  {
    number: "05",
    title: "Guarded routing + explainability",
    pill: "LangSmith",
    description:
      "With a real confidence number, the last node routes: low → escalate, missing info → clarify, high → answer. Every run is traced and explainable.",
    detail: "escalate · clarify · answer",
  },
]

const RELIABILITY_ROWS: { claimed: string; actual: string }[] = [
  { claimed: "0.20", actual: "0.19" },
  { claimed: "0.48", actual: "0.38" },
  { claimed: "0.62", actual: "0.52" },
  { claimed: "0.85", actual: "0.71" },
]

/**
 * Public, presentational recruiter/client-facing landing page (Slice E). Rendered by App when
 * `authGate === "gated"` instead of the bare LoginGate. Makes NO API calls except `login()` from
 * the invite modal — the `/analyze` + `/feedback` gating is unchanged.
 *
 * Mirrors the console's light "command-precise" design language (see
 * `design/mockups/direction-final-command-precise.html`): light canvas, hairline borders,
 * mono micro-labels, flat-blue (no gradient) accents, and studio-precise restraint.
 */
export function Landing({ onAuthed }: LandingProps) {
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    if (!modalOpen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setModalOpen(false)
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [modalOpen])

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-background text-foreground">
      <TopNav onGetStarted={() => setModalOpen(true)} />

      <main>
        <Hero onGetStarted={() => setModalOpen(true)} />
        <SpecStrip />
        <UpgradesSection />
        <CalibrationSection />
        <ValueSection />
        <GuardedCallout />
      </main>

      <Footer />

      {modalOpen && (
        <InviteModal
          onAuthed={() => {
            setModalOpen(false)
            onAuthed()
          }}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}

function TopNav({ onGetStarted }: { onGetStarted: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-white/85 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5 sm:px-8">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-primary shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
            <ListTodo className="size-4 text-primary-foreground" strokeWidth={2.2} />
          </div>
          <div className="flex flex-col gap-px">
            <span className="text-[14px] font-extrabold tracking-[-0.02em] text-foreground">
              QueuePilot
            </span>
            <span className="text-[10.5px] font-medium text-[#8896A8]">AI ops assistant</span>
          </div>
        </div>

        <nav aria-label="Site" className="flex items-center gap-4">
          <a
            href={CONTACT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[13.5px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
          >
            Contact
          </a>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="QueuePilot on GitHub"
            className="flex size-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-[#CBD5E1] hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
          >
            <GitFork className="size-4" />
          </a>
          <button
            type="button"
            onClick={onGetStarted}
            className="hidden items-center rounded-lg border border-primary bg-primary px-3.5 py-1.75 text-[13px] font-semibold text-primary-foreground shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:-translate-y-px hover:border-hero hover:bg-hero hover:shadow-[0_4px_14px_rgba(15,23,42,0.07)] sm:flex focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
          >
            Get started
          </button>
        </nav>
      </div>
    </header>
  )
}

function Hero({ onGetStarted }: { onGetStarted: () => void }) {
  return (
    <section className="relative border-b border-border">
      {/* Extremely subtle hairline grid — keeps the canvas from feeling flat without any glow. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.5]"
        style={{
          backgroundImage:
            "linear-gradient(to right, #E2E8F0 1px, transparent 1px), linear-gradient(to bottom, #E2E8F0 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "linear-gradient(to bottom, black, transparent 85%)",
          WebkitMaskImage: "linear-gradient(to bottom, black, transparent 85%)",
        }}
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-5 pt-12 pb-16 sm:px-8 lg:grid-cols-[1.05fr_1fr] lg:gap-6 lg:pt-16 lg:pb-20">
        <div className="relative z-10">
          <span className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1 font-mono text-[10.5px] font-semibold tracking-[0.08em] text-[#8896A8] uppercase">
            Agentic AI &middot; Guarded Support Copilot
          </span>

          <h1 className="mb-5 max-w-xl text-[34px] leading-[1.1] font-extrabold tracking-[-0.02em] text-foreground sm:text-[42px] lg:text-[48px]">
            Triage support tickets with an AI that knows when{" "}
            <span className="text-accent-foreground">not</span> to answer.
          </h1>

          <p className="mb-8 max-w-lg text-[15.5px] leading-relaxed text-muted-foreground">
            QueuePilot classifies, routes, and drafts grounded replies from 3,000 real tickets —
            with calibrated confidence that escalates instead of guessing.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onGetStarted}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-primary bg-primary px-5 py-2.75 text-[14px] font-semibold text-primary-foreground shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:-translate-y-px hover:border-hero hover:bg-hero hover:shadow-[0_4px_14px_rgba(15,23,42,0.07)] focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              Get started
              <ArrowRight className="size-4" />
            </button>
            <a
              href={CONTACT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center rounded-lg border border-border bg-white px-5 py-2.75 text-[14px] font-semibold text-foreground shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-colors hover:border-[#CBD5E1] focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              Contact
            </a>
          </div>

          <p className="mt-5 font-mono text-[11.5px] tracking-[0.02em] text-[#8896A8]">
            Live demo &middot; invite-gated
          </p>
        </div>

        <ScreenshotPanel />
      </div>
    </section>
  )
}

/** The real console screenshot, framed like a genuine product window: hairline border,
 * rounded-xl corners, and the mockup's subtle `shadow-lg`. Bleeds slightly off the right edge
 * on desktop (clipped by the root's `overflow-x-hidden`, never causing horizontal scroll).
 * Stacks in-flow, full width, on small screens. */
function ScreenshotPanel() {
  return (
    <div className="relative lg:w-[122%] lg:max-w-none lg:-mr-[6vw] xl:-mr-[8vw]">
      <img
        src="/console-preview.png"
        alt="QueuePilot console analyzing a support ticket, showing routing, confidence, and a suggested reply"
        width={1380}
        height={920}
        loading="eager"
        className="relative w-full rounded-xl border border-border shadow-[0_18px_40px_rgba(15,23,42,0.10),0_4px_10px_rgba(15,23,42,0.05)]"
      />
    </div>
  )
}

function SpecStrip() {
  return (
    <section aria-label="Engineering highlights" className="border-b border-border bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap divide-x divide-border px-5 sm:px-8">
        {SPECS.map((spec) => (
          <div key={spec.label} className="flex-1 basis-1/2 px-4 py-6 sm:basis-1/3 sm:px-5 lg:basis-0">
            <div className="font-mono text-[15px] font-bold tracking-[-0.01em] text-foreground sm:text-[16px]">
              {spec.value}
            </div>
            <div className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">{spec.label}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

/** "How it works" — the 5 upgrades that separate QueuePilot from a plain retrieve-and-generate
 * pipeline. Card 04 (calibrated confidence) is the signature idea and gets the flat-blue
 * highlight treatment used by the console's ConfidenceHero, so it reads as "the big one" without
 * introducing any new visual language. */
function UpgradesSection() {
  return (
    <section
      aria-labelledby="upgrades-heading"
      className="border-b border-border bg-white px-5 py-20 sm:px-8"
    >
      <div className="mx-auto max-w-6xl">
        <span className="mb-3 block font-mono text-[10.5px] font-bold tracking-[0.09em] text-accent-foreground uppercase">
          How it works
        </span>
        <h2
          id="upgrades-heading"
          className="mb-2 max-w-2xl text-[24px] leading-tight font-extrabold tracking-[-0.015em] text-foreground sm:text-[28px]"
        >
          Five upgrades over a retrieve-and-generate pipeline
        </h2>
        <p className="mb-10 max-w-xl text-[14px] leading-relaxed text-muted-foreground">
          Each is a small, nameable idea — together they turn RAG into a copilot that knows how
          much to trust itself.
        </p>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {UPGRADES.map((upgrade) => (
            <UpgradeCard key={upgrade.number} {...upgrade} />
          ))}
        </div>
      </div>
    </section>
  )
}

function UpgradeCard({
  number,
  title,
  pill,
  description,
  detail,
  highlight,
}: (typeof UPGRADES)[number]) {
  return (
    <article
      className={cn(
        "flex flex-col gap-3 rounded-xl border px-5 py-5",
        highlight
          ? "border-[#0A3A57] bg-hero text-white shadow-[0_18px_40px_rgba(15,23,42,0.10),0_4px_10px_rgba(15,23,42,0.05)] lg:col-span-1"
          : "border-border bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "font-mono text-[13px] font-bold",
            highlight ? "text-white/70" : "text-accent-foreground",
          )}
        >
          {number}
        </span>
        {highlight ? (
          <span className="flex items-center gap-1 rounded-full border border-white/30 bg-white/10 px-2 py-0.5 font-mono text-[9.5px] font-bold tracking-[0.07em] text-white uppercase">
            <Sparkles className="size-3" />
            The big one
          </span>
        ) : pill ? (
          <span className="rounded-full border border-border bg-[#F8FAFC] px-2 py-0.5 font-mono text-[9.5px] font-semibold tracking-[0.04em] text-muted-foreground">
            {pill}
          </span>
        ) : null}
      </div>

      <h3
        className={cn(
          "text-[15.5px] font-bold tracking-[-0.01em]",
          highlight ? "text-white" : "text-foreground",
        )}
      >
        {title}
      </h3>

      <p
        className={cn(
          "text-[13.5px] leading-relaxed",
          highlight ? "text-white/85" : "text-muted-foreground",
        )}
      >
        {description}
      </p>

      <div
        className={cn(
          "mt-auto border-t pt-3 font-mono text-[11px] leading-snug",
          highlight ? "border-white/15 text-white/70" : "border-border text-[#8896A8]",
        )}
      >
        {detail}
      </div>
    </article>
  )
}

/** "Calibration" — the differentiated insight: a self-reported confidence score is useless
 * (overconfident) while the blended score tracks real accuracy. Numbers sourced from
 * `learn/10_calibration_demo.py`. Two contrasting cards echo the console's positive/destructive
 * token usage rather than introducing new colors. */
function CalibrationSection() {
  return (
    <section aria-labelledby="calibration-heading" className="px-5 py-20 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <span className="mb-3 block font-mono text-[10.5px] font-bold tracking-[0.09em] text-accent-foreground uppercase">
          Calibration
        </span>
        <h2
          id="calibration-heading"
          className="mb-2 max-w-2xl text-[24px] leading-tight font-extrabold tracking-[-0.015em] text-foreground sm:text-[28px]"
        >
          Calibrated confidence — not the model's word
        </h2>
        <p className="mb-10 max-w-xl text-[14px] leading-relaxed text-muted-foreground">
          Real numbers from <code className="font-mono text-[13px]">learn/10_calibration_demo.py</code>.
        </p>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Self-reported confidence — the false signal */}
          <div className="flex flex-col gap-4 rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-6">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-[14.5px] font-bold tracking-[-0.005em] text-foreground">
                Self-reported confidence
              </h3>
              <span className="rounded-full border border-destructive/40 bg-white px-2.5 py-0.5 font-mono text-[10px] font-semibold text-destructive">
                calibration error ≈ 0.33
              </span>
            </div>

            <div className="flex items-baseline gap-6">
              <div>
                <div className="font-mono text-[11px] font-semibold tracking-[0.04em] text-muted-foreground uppercase">
                  Claimed
                </div>
                <div className="font-mono text-[32px] leading-none font-bold text-foreground">0.95</div>
              </div>
              <div>
                <div className="font-mono text-[11px] font-semibold tracking-[0.04em] text-muted-foreground uppercase">
                  Actual
                </div>
                <div className="font-mono text-[32px] leading-none font-bold text-destructive">0.53</div>
              </div>
            </div>

            <div className="h-2 overflow-hidden rounded border border-border bg-white">
              <div className="h-full bg-destructive/70" style={{ width: "53%" }} />
            </div>

            <p className="text-[13px] leading-relaxed text-muted-foreground">
              The model claims it's right 95% of the time — it's actually right ~53%. That gap
              makes self-confidence useless for routing.
            </p>
          </div>

          {/* Blended confidence — production */}
          <div className="flex flex-col gap-4 rounded-xl border border-positive/30 bg-positive/5 px-6 py-6">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-[14.5px] font-bold tracking-[-0.005em] text-foreground">
                Blended confidence (production)
              </h3>
              <span className="rounded-full border border-positive/40 bg-white px-2.5 py-0.5 font-mono text-[10px] font-semibold text-positive">
                calibration error ≈ 0.11
              </span>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between font-mono text-[10.5px] font-semibold tracking-[0.03em] text-muted-foreground uppercase">
                <span>Claimed</span>
                <span>Actual</span>
              </div>
              {RELIABILITY_ROWS.map((row) => (
                <div
                  key={row.claimed}
                  className="flex items-center gap-3 border-t border-border pt-1.5 first:border-t-0 first:pt-0"
                >
                  <span className="w-12 font-mono text-[12.5px] font-semibold text-foreground">
                    {row.claimed}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded bg-white">
                    <div
                      className="h-full rounded bg-positive/60"
                      style={{ width: `${Number(row.actual) * 100}%` }}
                    />
                  </div>
                  <span className="w-12 text-right font-mono text-[12.5px] font-semibold text-positive">
                    {row.actual}
                  </span>
                </div>
              ))}
            </div>

            <p className="text-[13px] leading-relaxed text-muted-foreground">
              Claimed and actual track each other — "62% confident" really means right ~52–62% of
              the time.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

function ValueSection() {
  return (
    <section className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
      <h2 className="mb-2 text-[13.5px] font-bold tracking-[-0.005em] text-foreground uppercase">
        Built for support teams
      </h2>
      <p className="mb-10 max-w-md text-[14px] text-muted-foreground">
        Not a chatbot bolted onto a help desk — a guarded workflow purpose-built to know its
        limits.
      </p>

      <div className="divide-y divide-border border-t border-border">
        {CAPABILITIES.map(({ icon: Icon, number, title, description }) => (
          <div key={title} className="flex flex-col gap-3 py-6 sm:flex-row sm:items-baseline sm:gap-8">
            <span className="font-mono text-[13px] font-semibold text-accent-foreground sm:w-10 sm:shrink-0">
              {number}
            </span>
            <div className="flex items-center gap-2 sm:w-64 sm:shrink-0">
              <Icon className="size-4 shrink-0 text-accent-foreground" strokeWidth={2.2} />
              <h3 className="text-[15px] font-bold tracking-[-0.01em] text-foreground">{title}</h3>
            </div>
            <p className="text-[13.5px] leading-relaxed text-muted-foreground">{description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

/** Slimmed to a single closing CTA line — the "guarded by design" narrative now lives in
 * UpgradesSection (05) and the calibration story owns the confidence proof, so this no longer
 * needs to repeat either. Kept as a lightweight flat-blue closer that points to the repo. */
function GuardedCallout() {
  return (
    <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
      <div className="flex flex-col items-start gap-3 rounded-2xl border border-[#0A3A57] bg-hero px-7 py-6 text-white shadow-[0_18px_40px_rgba(15,23,42,0.10),0_4px_10px_rgba(15,23,42,0.05)] sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[14.5px] leading-relaxed text-white/90">
          See the full walkthrough — workflow, retrieval, and calibration source.
        </p>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-white bg-white px-4 py-2.5 text-[13.5px] font-semibold text-hero shadow-sm transition-all hover:-translate-y-px hover:shadow-md focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2"
        >
          <GitFork className="size-4" />
          GitHub
        </a>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-border px-5 py-8 sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          <span className="mr-1 text-[12px] text-muted-foreground">Built with</span>
          {STACK_BADGES.map((badge) => (
            <span
              key={badge}
              className="rounded-full border border-border bg-white px-2.5 py-0.5 font-mono text-[10.5px] text-muted-foreground"
            >
              {badge}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-4 text-[12.5px]">
          <span className="text-[#8896A8]">Invite-gated demo</span>
          <a
            href={CONTACT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
          >
            Contact
          </a>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
          >
            <GitFork className="size-3.5" />
            GitHub
          </a>
        </div>
      </div>
    </footer>
  )
}

function InviteModal({ onAuthed, onClose }: { onAuthed: () => void; onClose: () => void }) {
  return (
    <div
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/45 px-4 backdrop-blur-sm"
    >
      <div role="dialog" aria-modal="true" aria-label="Enter your invite code">
        <InviteGate onAuthed={onAuthed} onBack={onClose} />
      </div>
    </div>
  )
}
