import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SuggestedReply } from "@/components/console/SuggestedReply"
import { ESCALATION_RESPONSE, SAMPLE_RESPONSE } from "@/test/fixtures"

describe("SuggestedReply", () => {
  it("renders the drafted reply on the answer path", () => {
    render(<SuggestedReply response={SAMPLE_RESPONSE} />)
    expect(screen.getByRole("heading", { name: /suggested reply/i })).toBeInTheDocument()
    expect(screen.getByText(/could you tell me which VPN client/i)).toBeInTheDocument()
  })

  it("routes escalations to the escalation panel, not a hollow reply card", () => {
    render(<SuggestedReply response={ESCALATION_RESPONSE} submittedText="my files are encrypted" />)

    // The escalation panel, not the reply card.
    expect(screen.getByRole("heading", { name: /escalation/i })).toBeInTheDocument()
    // The original bug: an empty reply card. Must not appear for escalations.
    expect(screen.queryByText(/no suggested reply was generated/i)).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /send reply/i })).not.toBeInTheDocument()
  })
})
