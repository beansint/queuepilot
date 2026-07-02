import { useEffect, useState } from "react"
import {
  Activity,
  ArrowRight,
  GitFork,
  ListTodo,
  MessageSquareText,
  Route,
  ShieldCheck,
} from "lucide-react"
import { InviteGate } from "@/components/console/InviteGate"
import { CONTACT_URL, GITHUB_URL } from "@/lib/site"

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

/** A single flat-blue accent block (no gradient) echoing the console's confidence hero — used
 * sparingly, once, to keep the light marketing page cohesive with the app it links to. */
function GuardedCallout() {
  return (
    <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
      <div className="flex flex-col items-start gap-4 rounded-2xl border border-[#0A3A57] bg-hero px-7 py-8 text-white shadow-[0_18px_40px_rgba(15,23,42,0.10),0_4px_10px_rgba(15,23,42,0.05)] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <span className="font-mono text-[10.5px] font-bold tracking-[0.09em] text-white/60 uppercase">
            Guarded by design
          </span>
          <p className="mt-2 max-w-lg text-[15px] leading-relaxed text-white/90">
            Every decision is scored against calibrated thresholds — confidence below the line
            escalates to a human, it never guesses its way through a ticket.
          </p>
        </div>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-white bg-white px-4 py-2.5 text-[13.5px] font-semibold text-hero shadow-sm transition-all hover:-translate-y-px hover:shadow-md focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2"
        >
          <GitFork className="size-4" />
          See the workflow
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
