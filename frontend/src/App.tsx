import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AlertCircle, RotateCcw, Sparkles } from "lucide-react"
import { toast } from "sonner"
import { Toaster } from "@/components/ui/sonner"
import { NavRail } from "@/components/console/NavRail"
import { MobileNav } from "@/components/console/MobileNav"
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
import { IdleRail } from "@/components/console/IdleRail"
import { ResultSkeleton } from "@/components/console/ResultSkeleton"
import { EvidencePage } from "@/components/console/EvidencePage"
import { InsightsPage } from "@/components/console/InsightsPage"
import { Landing } from "@/components/marketing/Landing"
import { AuthRequiredError, analyzeTicket, getAuthStatus, logout } from "@/lib/api"
import { useHashRoute } from "@/lib/useHashRoute"
import type { AnalyzeResponse } from "@/lib/types"

const SAMPLE_TICKET =
  "My laptop won't connect to the office VPN after the latest Windows update. I've tried restarting and reinstalling the client but nothing works — I have a client demo in 2 hours and I'm completely stuck. Please help!"

type Status = "idle" | "loading" | "error" | "success"
type AuthGate = "checking" | "gated" | "open"

/** How long the initial auth check is allowed to hang before we fail open rather than
 * stranding the user on a blank "checking" screen (e.g. a slow Render cold start). */
const AUTH_CHECK_TIMEOUT_MS = 5000

function nextTicketId(): string {
  return String(Math.floor(1000 + Math.random() * 9000))
}

export default function App() {
  const { route, navigate } = useHashRoute()
  const [authGate, setAuthGate] = useState<AuthGate>("checking")
  const [inputText, setInputText] = useState(SAMPLE_TICKET)
  const [status, setStatus] = useState<Status>("idle")
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState<{ text: string; id: string } | null>(null)
  const [explainOpen, setExplainOpen] = useState(false)
  const explainTriggerRef = useRef<HTMLButtonElement>(null)

  const checkAuth = useCallback(async () => {
    try {
      const { required, authenticated } = await getAuthStatus()
      setAuthGate(required && !authenticated ? "gated" : "open")
    } catch {
      // Auth-status check itself failed (e.g. network hiccup) — fail open rather than
      // stranding the user on a blank screen; /analyze will still 401 -> re-gate if needed.
      setAuthGate("open")
    }
  }, [])

  useEffect(() => {
    // Race the initial auth check against a timeout so a stalled/never-settling request
    // (e.g. a slow cold start or hung connection) can't leave the user stuck on a blank
    // "checking" screen forever — fail open the same way the catch above does.
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      setAuthGate((current) => (current === "checking" ? "open" : current))
    }, AUTH_CHECK_TIMEOUT_MS)

    void checkAuth().finally(() => {
      if (!timedOut) clearTimeout(timer)
    })

    return () => clearTimeout(timer)
  }, [checkAuth])

  const handleAuthExpired = useCallback(() => {
    setStatus("idle")
    setSubmitted(null)
    setAuthGate("gated")
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await logout()
      // Clear analysis state so a re-login starts clean, then re-gate to the landing page.
      // (No success toast: the Toaster unmounts with the console when we re-gate, so the
      // login screen itself is the confirmation. The error path stays in the console.)
      setStatus("idle")
      setResult(null)
      setSubmitted(null)
      navigate("console")
      setAuthGate("gated")
    } catch {
      toast.error("Couldn't sign out — please try again.")
    }
  }, [navigate])

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
      if (err instanceof AuthRequiredError) {
        handleAuthExpired()
        return
      }
      const message = err instanceof Error ? err.message : "Something went wrong analyzing this ticket."
      setErrorMessage(message)
      setStatus("error")
      toast.error("Analysis failed", { description: message })
    }
  }, [handleAuthExpired])

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

  // Evidence only exists after a successful analysis; if someone deep-links to
  // #/evidence without one, bounce them back to the console (and fix the hash).
  const evidenceAvailable = status === "success" && result !== null
  useEffect(() => {
    if (route === "evidence" && !evidenceAvailable) navigate("console")
  }, [route, evidenceAvailable, navigate])

  if (authGate === "checking") {
    return <div className="min-h-screen bg-background" aria-busy="true" />
  }

  // Gated (logged out): always the marketing landing, regardless of route.
  if (authGate === "gated") {
    return <Landing onAuthed={() => void checkAuth()} />
  }

  // Logged-in "Overview": the marketing landing, viewable from inside the app.
  if (route === "overview") {
    return (
      <Landing onAuthed={() => void checkAuth()} authed onEnterConsole={() => navigate("console")} />
    )
  }

  // Evidence page shares the NavRail shell but drops the right-hand summary rail.
  if (route === "evidence" && evidenceAvailable && result) {
    return (
      <div className="grid min-h-screen grid-cols-1 md:grid-cols-[232px_1fr]">
        <MobileNav route="evidence" onNavigate={navigate} onLogout={handleLogout} evidenceEnabled />
        <NavRail route="evidence" onNavigate={navigate} onLogout={handleLogout} evidenceEnabled />
        <EvidencePage response={result} submittedText={submitted?.text} onBack={() => navigate("console")} />
        <Toaster />
      </div>
    )
  }

  // Insights page shares the same NavRail shell as Evidence, but needs no prior
  // analysis (no redirect guard) — it fetches its own eval-snapshot data on mount.
  if (route === "insights") {
    return (
      <div className="grid min-h-screen grid-cols-1 md:grid-cols-[232px_1fr]">
        <MobileNav route="insights" onNavigate={navigate} onLogout={handleLogout} evidenceEnabled={evidenceAvailable} />
        <NavRail route="insights" onNavigate={navigate} onLogout={handleLogout} evidenceEnabled={evidenceAvailable} />
        <InsightsPage onBack={() => navigate("console")} onAuthExpired={handleAuthExpired} />
        <Toaster />
      </div>
    )
  }

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[232px_1fr] xl:grid-cols-[232px_1fr_300px]">
      <MobileNav route="console" onNavigate={navigate} onLogout={handleLogout} evidenceEnabled={evidenceAvailable} />
      <NavRail route="console" onNavigate={navigate} onLogout={handleLogout} evidenceEnabled={evidenceAvailable} />

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
            <SuggestedReply response={result} submittedText={submitted?.text} />
            <FeedbackWidget
              response={result}
              submittedText={submitted?.text}
              onAuthExpired={handleAuthExpired}
            />
            <SimilarTicketsTable
              tickets={result.similar_tickets}
              onViewAll={() => navigate("evidence")}
            />
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

      {status === "success" && result ? (
        <SummaryRail response={result} />
      ) : (
        <IdleRail onPickSample={runAnalysis} />
      )}

      <Toaster />
    </div>
  )
}
