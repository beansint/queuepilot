import { FileText, Loader2, Sparkles } from "lucide-react"
import { Textarea } from "@/components/ui/textarea"

interface TicketInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  isLoading: boolean
}

export function TicketInput({ value, onChange, onSubmit, isLoading }: TicketInputProps) {
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault()
      if (!isLoading && value.trim()) onSubmit()
    }
  }

  return (
    <section
      aria-label="Ticket input"
      className="mb-5 rounded-2xl border border-border bg-card p-5 shadow-sm"
    >
      <div className="mb-2.5 flex items-center justify-between">
        <label
          htmlFor="ticket-text"
          className="flex items-center gap-1.5 font-mono text-[11px] font-bold tracking-[0.06em] text-muted-foreground/80 uppercase"
        >
          <FileText className="size-3.5" />
          New ticket
        </label>
        <span className="font-mono text-[11.5px] text-muted-foreground/80">
          {value.length.toLocaleString()} chars
        </span>
      </div>
      <Textarea
        id="ticket-text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Paste a ticket and hit Analyze…"
        rows={5}
        className="min-h-32 resize-y border-none bg-transparent p-0 text-[15px] leading-relaxed tracking-[-0.006em] text-foreground shadow-none focus-visible:ring-0"
      />
      <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
        <span className="text-xs text-muted-foreground">
          Paste a ticket and hit Analyze, or press{" "}
          <kbd className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10.5px]">
            ⌘↵
          </kbd>
        </span>
        <button
          type="button"
          onClick={onSubmit}
          disabled={isLoading || !value.trim()}
          className="flex items-center gap-1.5 rounded-lg border border-primary bg-primary px-4 py-2.5 text-[13.5px] font-semibold tracking-[-0.006em] text-primary-foreground shadow-sm transition-all hover:-translate-y-px hover:bg-hero hover:border-hero hover:shadow-md disabled:pointer-events-none disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="size-[15px] animate-spin" />
          ) : (
            <Sparkles className="size-[15px]" />
          )}
          {isLoading ? "Analyzing…" : "Analyze"}
        </button>
      </div>
    </section>
  )
}
