import { useState } from "react"
import { Copy, HelpCircle, Pencil, Send, ShieldCheck } from "lucide-react"
import { toast } from "sonner"
import type { AnalyzeResponse } from "@/lib/types"

interface SuggestedReplyProps {
  response: AnalyzeResponse
}

export function SuggestedReply({ response }: SuggestedReplyProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(response.suggested_reply ?? "")
  const neighborCount = response.similar_tickets.length
  const isClarification = !response.suggested_reply && !!response.clarification?.length

  async function handleCopy() {
    const text = isClarification ? (response.clarification ?? []).join("\n") : draft
    try {
      await navigator.clipboard.writeText(text)
      toast.success("Copied to clipboard")
    } catch {
      toast.error("Couldn't copy — copy the text manually")
    }
  }

  return (
    <>
      <div className="mt-7 mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13.5px] font-bold tracking-[-0.005em]">
          {isClarification ? (
            <HelpCircle className="size-[15px] text-accent-foreground" />
          ) : (
            <Send className="size-[15px] text-accent-foreground" />
          )}
          {isClarification ? "Clarifying questions" : "Suggested reply"}
        </h2>
        <span className="font-mono text-xs text-muted-foreground/80">
          {isClarification ? "Missing details before this can be handled" : "Grounded in evidence below"}
        </span>
      </div>
      <section aria-label={isClarification ? "Clarifying questions" : "Suggested reply"} className="mb-2 rounded-2xl border border-border bg-card p-5.5 px-[22px] shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-1.5 rounded-full bg-positive/10 px-2.5 py-1 font-mono text-[11.5px] font-bold text-positive">
            <ShieldCheck className="size-3.25" />
            Grounded in {neighborCount} similar {neighborCount === 1 ? "ticket" : "tickets"}
          </div>
        </div>

        {isClarification ? (
          <ul className="flex flex-col gap-2 border-l-2 border-accent-foreground py-0.5 pl-4">
            {response.clarification!.map((question, i) => (
              <li key={i} className="text-[14.5px] leading-[1.7] tracking-[-0.006em] text-[#1E2534]">
                {question}
              </li>
            ))}
          </ul>
        ) : editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={6}
            className="w-full resize-y rounded-lg border border-border bg-background p-3 text-[14.5px] leading-[1.7] tracking-[-0.006em] text-[#1E2534] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        ) : (
          <p className="border-l-2 border-accent-foreground py-0.5 pl-4 text-[14.5px] leading-[1.7] whitespace-pre-line tracking-[-0.006em] text-[#1E2534]">
            {draft || "No suggested reply was generated for this ticket."}
          </p>
        )}

        <div className="mt-4 flex gap-2.5 border-t border-border pt-3.5">
          <button
            type="button"
            onClick={() => toast.success("Reply sent")}
            disabled={isClarification && !response.clarification?.length}
            className="flex items-center gap-1.5 rounded-lg border border-primary bg-primary px-3.5 py-2 text-[13px] font-semibold tracking-[-0.006em] text-primary-foreground transition-colors hover:bg-[#1E293B] hover:border-[#1E293B] disabled:pointer-events-none disabled:opacity-50"
          >
            <Send className="size-3.5" />
            Send reply
          </button>
          {!isClarification && (
            <button
              type="button"
              onClick={() => setEditing((v) => !v)}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-white px-3.5 py-2 text-[13px] font-semibold tracking-[-0.006em] text-foreground transition-colors hover:border-accent-foreground hover:text-accent-foreground"
            >
              <Pencil className="size-3.5" />
              {editing ? "Done" : "Edit"}
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-white px-3.5 py-2 text-[13px] font-semibold tracking-[-0.006em] text-foreground transition-colors hover:border-accent-foreground hover:text-accent-foreground"
          >
            <Copy className="size-3.5" />
            Copy
          </button>
        </div>
      </section>
    </>
  )
}
