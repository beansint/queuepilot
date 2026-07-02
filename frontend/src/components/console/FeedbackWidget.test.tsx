import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FeedbackWidget } from "@/components/console/FeedbackWidget"
import { SAMPLE_RESPONSE } from "@/test/fixtures"
import { AuthRequiredError, postFeedback } from "@/lib/api"

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...actual,
    postFeedback: vi.fn(),
  }
})

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const postFeedbackMock = vi.mocked(postFeedback)

describe("FeedbackWidget", () => {
  beforeEach(() => {
    postFeedbackMock.mockReset()
    postFeedbackMock.mockResolvedValue(undefined)
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders thumbs up / down controls", () => {
    render(<FeedbackWidget response={SAMPLE_RESPONSE} />)
    expect(screen.getByRole("button", { name: /thumbs up/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /thumbs down/i })).toBeInTheDocument()
  })

  it("disables the controls and shows a tooltip when tracing is disabled", async () => {
    const user = userEvent.setup()
    const response = { ...SAMPLE_RESPONSE, trace: { ...SAMPLE_RESPONSE.trace!, enabled: false } }
    render(<FeedbackWidget response={response} />)

    const up = screen.getByRole("button", { name: /thumbs up/i })
    expect(up).toBeDisabled()

    const trigger = up.closest("[data-slot='tooltip-trigger']") ?? up.parentElement!
    await user.hover(trigger)
    const tooltips = await screen.findAllByText(/feedback needs tracing enabled/i)
    expect(tooltips.length).toBeGreaterThan(0)
  })

  it("disables the controls when there is no run_id", () => {
    const response = { ...SAMPLE_RESPONSE, trace: { ...SAMPLE_RESPONSE.trace!, run_id: null } }
    render(<FeedbackWidget response={response} />)
    expect(screen.getByRole("button", { name: /thumbs up/i })).toBeDisabled()
  })

  it("clicking thumbs-up posts feedback with score 1 and the run_id", async () => {
    const user = userEvent.setup()
    render(<FeedbackWidget response={SAMPLE_RESPONSE} submittedText="my ticket text" />)

    await user.click(screen.getByRole("button", { name: /thumbs up/i }))

    expect(postFeedbackMock).toHaveBeenCalledWith({
      run_id: SAMPLE_RESPONSE.trace!.run_id,
      score: 1,
      text: "my ticket text",
    })
    expect(await screen.findByText(/thanks for the feedback/i)).toBeInTheDocument()
  })

  it("clicking thumbs-down posts feedback with score 0 and the run_id", async () => {
    const user = userEvent.setup()
    render(<FeedbackWidget response={SAMPLE_RESPONSE} submittedText="my ticket text" />)

    await user.click(screen.getByRole("button", { name: /thumbs down/i }))

    expect(postFeedbackMock).toHaveBeenCalledWith({
      run_id: SAMPLE_RESPONSE.trace!.run_id,
      score: 0,
      text: "my ticket text",
    })
  })

  it("submitting a correction posts the queue/priority/type + comment + text", async () => {
    const user = userEvent.setup()
    render(<FeedbackWidget response={SAMPLE_RESPONSE} submittedText="my ticket text" />)

    await user.click(screen.getByRole("button", { name: /suggest a correction/i }))

    const queueInput = screen.getByLabelText(/queue/i)
    await user.clear(queueInput)
    await user.type(queueInput, "Billing")

    const commentInput = screen.getByLabelText(/comment/i)
    await user.type(commentInput, "Should be billing, not tech support")

    await user.click(screen.getByRole("button", { name: /submit correction/i }))

    expect(postFeedbackMock).toHaveBeenCalledWith({
      run_id: SAMPLE_RESPONSE.trace!.run_id,
      score: 0,
      correction: {
        queue: "Billing",
        priority: SAMPLE_RESPONSE.priority,
        type: SAMPLE_RESPONSE.category,
      },
      comment: "Should be billing, not tech support",
      text: "my ticket text",
    })
  })

  it("submitting a correction after a prior thumbs-up preserves score 1", async () => {
    const user = userEvent.setup()
    render(<FeedbackWidget response={SAMPLE_RESPONSE} submittedText="my ticket text" />)

    await user.click(screen.getByRole("button", { name: /thumbs up/i }))
    postFeedbackMock.mockClear()

    await user.click(screen.getByRole("button", { name: /suggest a correction/i }))

    const queueInput = screen.getByLabelText(/queue/i)
    await user.clear(queueInput)
    await user.type(queueInput, "Billing")

    await user.click(screen.getByRole("button", { name: /submit correction/i }))

    expect(postFeedbackMock).toHaveBeenCalledWith(
      expect.objectContaining({
        run_id: SAMPLE_RESPONSE.trace!.run_id,
        score: 1,
      }),
    )
  })

  it("calls onAuthExpired instead of showing a generic error when thumbs feedback 401s", async () => {
    const user = userEvent.setup()
    postFeedbackMock.mockRejectedValueOnce(new AuthRequiredError())
    const onAuthExpired = vi.fn()
    const { toast } = await import("sonner")

    render(
      <FeedbackWidget response={SAMPLE_RESPONSE} submittedText="my ticket text" onAuthExpired={onAuthExpired} />,
    )
    await user.click(screen.getByRole("button", { name: /thumbs up/i }))

    expect(onAuthExpired).toHaveBeenCalledTimes(1)
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("calls onAuthExpired instead of showing a generic error when a correction submit 401s", async () => {
    const user = userEvent.setup()
    postFeedbackMock.mockRejectedValueOnce(new AuthRequiredError())
    const onAuthExpired = vi.fn()
    const { toast } = await import("sonner")

    render(
      <FeedbackWidget response={SAMPLE_RESPONSE} submittedText="my ticket text" onAuthExpired={onAuthExpired} />,
    )
    await user.click(screen.getByRole("button", { name: /suggest a correction/i }))
    await user.click(screen.getByRole("button", { name: /submit correction/i }))

    expect(onAuthExpired).toHaveBeenCalledTimes(1)
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("resets thumbs/correction state when a new run_id arrives", async () => {
    const user = userEvent.setup()
    const { rerender } = render(<FeedbackWidget response={SAMPLE_RESPONSE} submittedText="first ticket" />)

    await user.click(screen.getByRole("button", { name: /thumbs up/i }))
    expect(await screen.findByText(/thanks for the feedback/i)).toBeInTheDocument()

    const nextResponse = {
      ...SAMPLE_RESPONSE,
      trace: { ...SAMPLE_RESPONSE.trace!, run_id: "a-different-run-id" },
    }
    rerender(<FeedbackWidget response={nextResponse} submittedText="second ticket" />)

    expect(screen.queryByText(/thanks for the feedback/i)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /thumbs up/i })).toHaveAttribute("aria-pressed", "false")
  })
})
