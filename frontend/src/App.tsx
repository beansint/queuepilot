import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AlertCircle, RotateCcw, Sparkles } from "lucide-react"
import { toast } from "sonner"
import { Toaster } from "@/components/ui/sonner"
import { NavRail } from "@/components/console/NavRail"
import { TopBar } from "@/components/console/TopBar"
import { TicketInput } from "@/components/console/TicketInput"
import { SubmittedTicket } from "@/components/console/SubmittedTicket"
import { ConfidenceHero } from "@/components/console/ConfidenceHero"
import { AttributeTiles } from "@/components/console/AttributeTiles"
import { SuggestedReply } from "@/components/console/SuggestedReply"
import { FeedbackWidget } from "@/components/console/FeedbackWidget"
import { SimilarTicketsTable } from "@/components/console/SimilarTicketsTable"
import { ExplainPanel } from "@/components/console/ExplainPanel"
import { TraceStrip } from "@/components/console/TraceStrip"
import { SummaryRail } from "@/components/console/SummaryRail"
import { ResultSkeleton } from "@/components/console/ResultSkeleton"
import { analyzeTicket } from "@/lib/api"
import type { AnalyzeResponse } from "@/lib/types"

const SAMPLE_TICKET =
  "My laptop won't connect to the office VPN after the latest Windows update. I've tried restarting and reinstalling the client but nothing works — I have a client demo in 2 hours and I'm completely stuck. Please help!"

type Status = "idle" | "loading" | "error" | "success"

function nextTicketId(): string {
  return String(Math.floor(1000 + Math.random() * 9000))
}

export default function App() {
  const [inputText, setInputText] = useState(SAMPLE_TICKET)
  const [status, setStatus] = useState<Status>("idle")
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState<{ text: string; id: string } | null>(null)
  const [explainOpen, setExplainOpen] = useState(false)
  const explainTriggerRef = useRef<HTMLButtonElement>(null)

  const runAnalysis = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    setSubmitted({ text: trimmed, id: nextTicketId() })
    setStatus("loading")
    setErrorMessage(null)
    setExplainOpen(false)
    try {
      const response = await analyzeTicket(trimmed)
      setResult(response)
      setStatus("success")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong analyzing this ticket."
      setErrorMessage(message)
      setStatus("error")
      toast.error("Analysis failed", { description: message })
    }
  }, [])

  function handleNewAnalysis() {
    setStatus("idle")
    setResult(null)
    setErrorMessage(null)
    setSubmitted(null)
    setInputText("")
  }

  const subtitle = useMemo(() => {
    if (status === "success") return "Reviewed just now · Auto-routed on submission"
    if (status === "loading") return "Analyzing ticket…"
    if (status === "error") return "Analysis failed — retry below"
    return "Paste a ticket to get started"
  }, [status])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName ?? ""
      if (tag === "INPUT" || tag === "TEXTAREA") return
      if (e.key.toLowerCase() === "e" && !e.metaKey && !e.ctrlKey && status === "success") {
        setExplainOpen((v) => !v)
        explainTriggerRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [status])

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[232px_1fr] xl:grid-cols-[232px_1fr_300px]">
      <NavRail />

      <main className="w-full max-w-full min-w-0 px-4 pt-5.5 pb-15 sm:px-8 md:max-w-[920px]">
        <TopBar onNewAnalysis={handleNewAnalysis} subtitle={subtitle} />

        {(status === "idle" || status === "loading" || status === "error") && (
          <TicketInput
            value={inputText}
            onChange={setInputText}
            onSubmit={() => runAnalysis(inputText)}
            isLoading={status === "loading"}
          />
        )}

        {submitted && status !== "idle" && (
          <SubmittedTicket text={submitted.text} id={submitted.id} timestamp="just now" />
        )}

        {status === "idle" && (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border bg-card/50 px-6 py-16 text-center">
            <div className="flex size-11 items-center justify-center rounded-full bg-accent">
              <Sparkles className="size-5 text-accent-foreground" />
            </div>
            <p className="text-sm font-medium text-foreground">Paste a ticket and hit Analyze</p>
            <p className="max-w-sm text-[13px] text-muted-foreground">
              QueuePilot will classify it, route it, score confidence, and draft a grounded reply — all in one pass.
            </p>
          </div>
        )}

        {status === "loading" && <ResultSkeleton />}

        {status === "error" && (
          <div className="flex flex-col items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-5 py-4.5">
            <div className="flex items-center gap-2 text-sm font-semibold text-destructive">
              <AlertCircle className="size-4" />
              Couldn't analyze this ticket
            </div>
            <p className="text-[13px] text-muted-foreground">{errorMessage}</p>
            <button
              type="button"
              onClick={() => runAnalysis(submitted?.text ?? inputText)}
              className="flex items-center gap-1.5 rounded-lg border border-destructive/40 bg-white px-3.5 py-2 text-[13px] font-semibold text-destructive transition-colors hover:bg-destructive/10"
            >
              <RotateCcw className="size-3.5" />
              Retry
            </button>
          </div>
        )}

        {status === "success" && result && (
          <>
            <ConfidenceHero response={result} />
            <AttributeTiles response={result} />
            <SuggestedReply response={result} />
            <FeedbackWidget response={result} submittedText={submitted?.text} />
            <SimilarTicketsTable tickets={result.similar_tickets} />
            {result.debug && (
              <ExplainPanel
                ref={explainTriggerRef}
                response={result}
                open={explainOpen}
                onOpenChange={setExplainOpen}
              />
            )}
            <TraceStrip trace={result.trace} />
          </>
        )}
      </main>

      {status === "success" && result && <SummaryRail response={result} />}

      <Toaster />
    </div>
  )
}
