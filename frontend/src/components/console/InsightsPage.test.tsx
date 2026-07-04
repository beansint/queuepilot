import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { InsightsPage } from "@/components/console/InsightsPage"
import type { SnapshotCard, SnapshotListResponse } from "@/lib/types"

const LIST_RESPONSE: SnapshotListResponse = {
  snapshots: [
    {
      name: "a0.5-groq",
      n: 20,
      config: { alpha: 0.5, chat: "groq" },
      queue_match: 0.35,
      priority_match: 0.55,
      type_match: 0.4,
      label_recall_at_k: 0.75,
      reply_quality: 0.875,
      ece: 0.1526,
    },
  ],
}

const CARD_RESPONSE: SnapshotCard = {
  metrics: {
    n: 20,
    config: { alpha: 0.5, chat: "groq" },
    queue_match: 0.35,
    priority_match: 0.55,
    type_match: 0.4,
    label_recall_at_k: 0.75,
    reply_quality: 0.875,
    ece: 0.1526,
    reliability: [
      { lo: 0.0, hi: 0.4, n: 5, claimed: 0.25, accuracy: 0.0 },
      { lo: 0.4, hi: 0.55, n: 9, claimed: 0.49, accuracy: 0.33 },
    ],
    skipped_evaluators: ["reply_quality"],
  },
  baseline: null,
}

function mockFetchSequence(responses: Array<{ ok: boolean; status: number; json: () => Promise<unknown> }>) {
  const fetchMock = vi.fn()
  responses.forEach((r) => fetchMock.mockResolvedValueOnce(r))
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

describe("InsightsPage", () => {
  beforeEach(() => vi.restoreAllMocks())
  afterEach(() => vi.restoreAllMocks())

  it("shows a loading state, then renders headline metrics and the reliability table", async () => {
    mockFetchSequence([
      { ok: true, status: 200, json: async () => LIST_RESPONSE },
      { ok: true, status: 200, json: async () => CARD_RESPONSE },
    ])

    render(<InsightsPage onBack={vi.fn()} onAuthExpired={vi.fn()} />)

    expect(screen.getByText(/loading eval snapshots/i)).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText(/queue exact-match/i)).toBeInTheDocument())

    expect(screen.getByText("35.0%")).toBeInTheDocument() // queue_match
    expect(screen.getByText("55.0%")).toBeInTheDocument() // priority_match
    expect(screen.getByText("0.1526")).toBeInTheDocument() // ece
    expect(screen.getByText(/reliability table/i)).toBeInTheDocument()
    expect(screen.getByText("[0.00, 0.40)")).toBeInTheDocument()
    expect(screen.getByText(/skipped evaluators/i)).toBeInTheDocument()
  })

  it("renders an empty state when there are no snapshots", async () => {
    mockFetchSequence([{ ok: true, status: 200, json: async () => ({ snapshots: [] }) }])

    render(<InsightsPage onBack={vi.fn()} onAuthExpired={vi.fn()} />)

    await waitFor(() => expect(screen.getByText(/no eval snapshots yet/i)).toBeInTheDocument())
  })

  it("renders an error state when the list request fails", async () => {
    mockFetchSequence([
      { ok: false, status: 500, json: async () => ({ detail: "boom" }) },
    ])

    render(<InsightsPage onBack={vi.fn()} onAuthExpired={vi.fn()} />)

    await waitFor(() => expect(screen.getByText(/couldn't load eval snapshots/i)).toBeInTheDocument())
    expect(screen.getByText("boom")).toBeInTheDocument()
  })

  it("calls onAuthExpired when the snapshot list 401s", async () => {
    mockFetchSequence([{ ok: false, status: 401, json: async () => ({ detail: "invite code required" }) }])
    const onAuthExpired = vi.fn()

    render(<InsightsPage onBack={vi.fn()} onAuthExpired={onAuthExpired} />)

    await waitFor(() => expect(onAuthExpired).toHaveBeenCalledTimes(1))
  })

  it("switches snapshots via the picker when more than one is available", async () => {
    const multi: SnapshotListResponse = {
      snapshots: [
        LIST_RESPONSE.snapshots[0],
        { ...LIST_RESPONSE.snapshots[0], name: "a0.7-groq" },
      ],
    }
    mockFetchSequence([
      { ok: true, status: 200, json: async () => multi },
      { ok: true, status: 200, json: async () => CARD_RESPONSE },
      { ok: true, status: 200, json: async () => CARD_RESPONSE },
    ])

    render(<InsightsPage onBack={vi.fn()} onAuthExpired={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole("button", { name: "a0.7-groq" })).toBeInTheDocument())

    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "a0.7-groq" }))

    await waitFor(() => expect(screen.getByRole("button", { name: "a0.7-groq" })).toHaveAttribute("aria-pressed", "true"))
  })

  it("calls onBack when the back link is clicked", async () => {
    mockFetchSequence([
      { ok: true, status: 200, json: async () => LIST_RESPONSE },
      { ok: true, status: 200, json: async () => CARD_RESPONSE },
    ])
    const onBack = vi.fn()

    render(<InsightsPage onBack={onBack} onAuthExpired={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/queue exact-match/i)).toBeInTheDocument())

    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: /back to analysis/i }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })
})
