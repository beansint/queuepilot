import { useState } from "react"
import { AlertCircle, ArrowLeft, KeyRound, ListTodo, Loader2 } from "lucide-react"
import { login } from "@/lib/api"
import { CONTACT_URL } from "@/lib/site"

interface InviteGateProps {
  /** Called after a successful login so the caller can re-check auth status and reveal the console. */
  onAuthed: () => void
  /** When provided, renders a small "Back" affordance (e.g. to close a modal wrapping this card). */
  onBack?: () => void
}

/**
 * Invite-code entry CARD (Slice E — D16). Matches the console's dark `bg-hero` hero-panel
 * aesthetic (see ConfidenceHero). Reusable as the full-screen gate (LoginGate) or inside the
 * landing page's "Get started" modal.
 */
export function InviteGate({ onAuthed, onBack }: InviteGateProps) {
  const [code, setCode] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = code.trim()
    if (!trimmed || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await login(trimmed)
      onAuthed()
    } catch {
      setError("That invite code isn't right. Double-check it and try again.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative w-full max-w-sm overflow-hidden rounded-2xl border border-[#0A3A57] bg-hero p-7 text-white shadow-lg">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="mb-4 flex items-center gap-1 rounded text-[12.5px] font-medium text-white/60 transition-colors hover:text-white focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2"
        >
          <ArrowLeft className="size-3.5" />
          Back
        </button>
      )}

      <div className="mb-5 flex items-center gap-2.5">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-[9px] bg-white/15">
          <ListTodo className="size-[18px]" strokeWidth={2.2} />
        </div>
        <div className="flex flex-col gap-px">
          <span className="text-[15px] font-extrabold tracking-[-0.02em]">QueuePilot</span>
          <span className="text-[11px] font-medium text-white/60">AI ops assistant</span>
        </div>
      </div>

      <h1 className="mb-1.5 text-[19px] font-bold tracking-[-0.02em]">Enter your invite code</h1>
      <p className="mb-5 text-[13px] text-white/70">
        This demo is invite-gated to protect shared API quotas. Ask the person who shared it with
        you for the code.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label htmlFor="invite-code" className="sr-only">
          Invite code
        </label>
        <div className="flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3.5 py-2.5 focus-within:border-white/50 focus-within:ring-2 focus-within:ring-white/30">
          <KeyRound className="size-4 shrink-0 text-white/60" />
          <input
            id="invite-code"
            name="invite-code"
            type="text"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            autoFocus
            value={code}
            onChange={(e) => {
              setCode(e.target.value)
              if (error) setError(null)
            }}
            placeholder="Invite code"
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error ? "invite-code-error" : undefined}
            className="w-full bg-transparent text-[15px] tracking-[-0.006em] text-white placeholder:text-white/40 focus:outline-none"
          />
        </div>

        {error && (
          <div
            id="invite-code-error"
            role="alert"
            className="flex items-center gap-1.5 text-[13px] font-medium text-[#FCA5A5]"
          >
            <AlertCircle className="size-3.5 shrink-0" />
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !code.trim()}
          className="mt-1.5 flex items-center justify-center gap-1.5 rounded-lg border border-white bg-white px-4 py-2.5 text-[13.5px] font-semibold tracking-[-0.006em] text-hero shadow-sm transition-all hover:-translate-y-px hover:shadow-md disabled:pointer-events-none disabled:opacity-50"
        >
          {submitting && <Loader2 className="size-[15px] animate-spin" />}
          {submitting ? "Checking…" : "Enter"}
        </button>
      </form>

      <p className="mt-4 text-center text-[12px] text-white/55">
        Don't have a code?{" "}
        <a
          href={CONTACT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-[#7DD3FC] underline decoration-[#7DD3FC]/40 underline-offset-2 transition-colors hover:text-white focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2"
        >
          Contact for access
        </a>
      </p>
    </div>
  )
}
