import { useEffect, useState } from "react"
import { ChevronDown, MessageSquarePlus, ThumbsDown, ThumbsUp } from "lucide-react"
import { toast } from "sonner"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { postFeedback } from "@/lib/api"
import type { AnalyzeResponse } from "@/lib/types"

interface FeedbackWidgetProps {
  response: AnalyzeResponse
  /** The ticket text that was analyzed to produce `response`, used so corrections carry enough
   * context to be stored as eval data. */
  submittedText?: string
}

const DISABLED_REASON = "Feedback needs tracing enabled — no run to attach to"

export function FeedbackWidget({ response, submittedText }: FeedbackWidgetProps) {
  const runId = response.trace?.run_id
  const disabled = response.trace?.enabled !== true || !runId

  // `selectedScore` tracks the user's chosen thumb (0 | 1) so a later correction submit can
  // preserve a prior thumbs-up instead of always overwriting it with score: 0.
  const [selectedScore, setSelectedScore] = useState<0 | 1 | null>(null)
  const [submittingThumbs, setSubmittingThumbs] = useState(false)
  const [correctionOpen, setCorrectionOpen] = useState(false)
  const [queue, setQueue] = useState(response.queue ?? "")
  const [priority, setPriority] = useState(response.priority ?? "")
  const [type, setType] = useState(response.category ?? "")
  const [comment, setComment] = useState("")
  const [submittingCorrection, setSubmittingCorrection] = useState(false)
  const [correctionSent, setCorrectionSent] = useState(false)

  // Reset all feedback state whenever a new analysis run loads (different run_id), so thumbs/
  // correction state from the previous ticket doesn't leak into the new one.
  useEffect(() => {
    setSelectedScore(null)
    setSubmittingThumbs(false)
    setCorrectionOpen(false)
    setQueue(response.queue ?? "")
    setPriority(response.priority ?? "")
    setType(response.category ?? "")
    setComment("")
    setSubmittingCorrection(false)
    setCorrectionSent(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response.trace?.run_id])

  async function handleThumbs(score: 0 | 1) {
    if (disabled || submittingThumbs || !runId) return
    setSubmittingThumbs(true)
    try {
      await postFeedback({ run_id: runId, score, text: submittedText ?? null })
      setSelectedScore(score)
      toast.success("Thanks for the feedback")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Couldn't submit feedback"
      toast.error("Feedback failed", { description: message })
    } finally {
      setSubmittingThumbs(false)
    }
  }

  async function handleCorrectionSubmit() {
    if (disabled || submittingCorrection || !runId) return
    setSubmittingCorrection(true)
    try {
      await postFeedback({
        run_id: runId,
        // Preserve a prior thumbs-up rather than contradicting it — only default to 0
        // (thumbs-down) when the user never picked a thumb.
        score: selectedScore ?? 0,
        correction: {
          ...(queue.trim() ? { queue: queue.trim() } : {}),
          ...(priority.trim() ? { priority: priority.trim() } : {}),
          ...(type.trim() ? { type: type.trim() } : {}),
        },
        comment: comment.trim() ? comment.trim() : null,
        text: submittedText ?? null,
      })
      setCorrectionSent(true)
      toast.success("Thanks for the feedback")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Couldn't submit correction"
      toast.error("Feedback failed", { description: message })
    } finally {
      setSubmittingCorrection(false)
    }
  }

  const thumbsRow = (
    <div className="flex items-center gap-2">
      <button
        type="button"
        aria-label="Thumbs up — this analysis was correct"
        aria-pressed={selectedScore === 1}
        disabled={disabled || submittingThumbs}
        onClick={() => handleThumbs(1)}
        className="flex items-center justify-center rounded-lg border border-border bg-white p-2 text-foreground transition-colors hover:border-positive hover:text-positive disabled:pointer-events-none disabled:opacity-50 aria-pressed:border-positive aria-pressed:bg-positive/10 aria-pressed:text-positive"
      >
        <ThumbsUp className="size-3.75" />
      </button>
      <button
        type="button"
        aria-label="Thumbs down — this analysis was wrong"
        aria-pressed={selectedScore === 0}
        disabled={disabled || submittingThumbs}
        onClick={() => handleThumbs(0)}
        className="flex items-center justify-center rounded-lg border border-border bg-white p-2 text-foreground transition-colors hover:border-destructive hover:text-destructive disabled:pointer-events-none disabled:opacity-50 aria-pressed:border-destructive aria-pressed:bg-destructive/10 aria-pressed:text-destructive"
      >
        <ThumbsDown className="size-3.75" />
      </button>
      {selectedScore !== null && (
        <span className="text-[13px] font-medium text-muted-foreground">Thanks for the feedback</span>
      )}
    </div>
  )

  return (
    <>
      <div className="mt-3 mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13.5px] font-bold tracking-[-0.005em]">
          <MessageSquarePlus className="size-[15px] text-accent-foreground" />
          Feedback
        </h2>
      </div>
      <section
        aria-label="Feedback"
        className="mb-2 rounded-2xl border border-border bg-card p-5.5 px-[22px] shadow-sm"
      >
        {disabled ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div>{thumbsRow}</div>
              </TooltipTrigger>
              <TooltipContent>{DISABLED_REASON}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          thumbsRow
        )}

        <Collapsible open={correctionOpen} onOpenChange={setCorrectionOpen} className="mt-4 border-t border-border pt-3.5">
          <CollapsibleTrigger
            disabled={disabled}
            className="flex w-full items-center justify-between text-[13px] font-semibold tracking-[-0.006em] text-foreground transition-colors hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
          >
            Suggest a correction
            <ChevronDown className="size-3.5 transition-transform group-data-[state=open]:rotate-180 data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-3 flex flex-col gap-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="flex flex-col gap-1 text-[12px] font-semibold text-muted-foreground">
                Queue
                <input
                  type="text"
                  value={queue}
                  onChange={(e) => setQueue(e.target.value)}
                  className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-[13px] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
              </label>
              <label className="flex flex-col gap-1 text-[12px] font-semibold text-muted-foreground">
                Priority
                <input
                  type="text"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-[13px] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
              </label>
              <label className="flex flex-col gap-1 text-[12px] font-semibold text-muted-foreground">
                Type
                <input
                  type="text"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-[13px] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-[12px] font-semibold text-muted-foreground">
              Comment (optional)
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                placeholder="What should the correct answer have been?"
              />
            </label>
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleCorrectionSubmit}
                disabled={disabled || submittingCorrection}
                className="flex items-center gap-1.5 rounded-lg border border-primary bg-primary px-3.5 py-2 text-[13px] font-semibold tracking-[-0.006em] text-primary-foreground transition-colors hover:bg-[#1E293B] hover:border-[#1E293B] disabled:pointer-events-none disabled:opacity-50"
              >
                Submit correction
              </button>
              {correctionSent && (
                <span className="text-[13px] font-medium text-muted-foreground">Thanks for the feedback</span>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </section>
    </>
  )
}
