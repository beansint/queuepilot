import { Command, GitBranch, Sparkles } from "lucide-react"

interface IdleRailProps {
  /** Populate + analyze a ticket when a sample is picked. */
  onPickSample: (text: string) => void
}

/** A curated sample ticket a visitor can click to run instantly. */
interface Sample {
  label: string
  text: string
}

const SAMPLES: Sample[] = [
  {
    label: "Billing · duplicate charge",
    text: "I was charged twice for my Pro subscription this month and need a refund for the duplicate — can you sort this out today?",
  },
  {
    label: "Access · locked out",
    text: "I'm locked out of my account after too many login attempts and the password-reset email never arrives. I need access back before my shift starts.",
  },
  {
    label: "Bug · CSV export fails",
    text: "Exporting a report to CSV has failed with 'server error 500' every time since this morning. Nothing changed on my end — this is blocking my team.",
  },
]

const STEPS = [
  "Retrieve similar past tickets (hybrid search)",
  "Score a calibrated confidence — not the model's word",
  "Route: answer · clarify · escalate",
]

/**
 * Right-rail content shown before an analysis exists, so the third column is never empty.
 * Mirrors SummaryRail's aside/card styling (light, hairline, mono micro-labels).
 */
export function IdleRail({ onPickSample }: IdleRailProps) {
  return (
    <aside
      aria-label="Getting started"
      className="flex h-auto flex-col gap-4.5 border-t border-border px-5.5 py-5.5 md:hidden xl:sticky xl:top-0 xl:flex xl:h-screen xl:overflow-y-auto xl:border-t-0 xl:border-l"
    >
      <div className="font-mono text-[11px] font-bold tracking-[0.07em] text-muted-foreground/80 uppercase">
        Get started
      </div>

      <Card icon={<Sparkles />} title="Try a sample">
        <div className="flex flex-col gap-2">
          {SAMPLES.map((s) => (
            <button
              key={s.label}
              type="button"
              onClick={() => onPickSample(s.text)}
              className="group flex flex-col gap-1 rounded-lg border border-border bg-card px-3 py-2.5 text-left transition-colors hover:border-ring/50 hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              <span className="font-mono text-[10.5px] font-bold tracking-[0.04em] text-ring uppercase">
                {s.label}
              </span>
              <span className="line-clamp-2 text-[12.5px] leading-snug text-muted-foreground group-hover:text-foreground">
                {s.text}
              </span>
            </button>
          ))}
        </div>
      </Card>

      <Card icon={<GitBranch />} title="How it works">
        <ol className="flex flex-col gap-2.5">
          {STEPS.map((step, i) => (
            <li key={i} className="flex items-start gap-2.5 text-[12.5px] leading-relaxed text-[#334155]">
              <span className="mt-px flex size-4.5 shrink-0 items-center justify-center rounded-full bg-accent font-mono text-[10px] font-bold text-ring">
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </Card>

      <Card icon={<Command />} title="Shortcuts">
        <div className="flex flex-col gap-1.75">
          <ShortcutRow keys="⌘↵" label="Analyze ticket" />
          <ShortcutRow keys="E" label="Explain this analysis" />
        </div>
      </Card>
    </aside>
  )
}

function Card({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 px-[17px] shadow-sm">
      <div className="mb-2.5 flex items-center gap-1.75 font-mono text-[11.5px] font-bold tracking-[0.04em] text-muted-foreground uppercase">
        <span className="[&_svg]:size-3.5">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  )
}

function ShortcutRow({ keys, label }: { keys: string; label: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-1.75 text-[12.5px] last:border-b-0">
      <span className="text-muted-foreground">{label}</span>
      <kbd className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-foreground">
        {keys}
      </kbd>
    </div>
  )
}
