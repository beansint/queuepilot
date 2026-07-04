import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { EscalationPanel } from "@/components/console/EscalationPanel"
import { ESCALATION_RESPONSE } from "@/test/fixtures"

describe("EscalationPanel", () => {
  it("shows the escalation reason (confidence + SLA risk) instead of a reply", () => {
    render(<EscalationPanel response={ESCALATION_RESPONSE} submittedText="my files are encrypted" />)

    expect(screen.getByRole("heading", { name: /escalation/i })).toBeInTheDocument()
    expect(screen.getByText("32%")).toBeInTheDocument()
    expect(screen.getByText(/SLA risk 0\.94/)).toBeInTheDocument()
    expect(screen.getByText(/didn't draft a reply/i)).toBeInTheDocument()
  })

  it("lists the missing info and offers handoff actions — never a Send button", () => {
    render(<EscalationPanel response={ESCALATION_RESPONSE} submittedText="ticket" />)

    expect(screen.getByText(/missing before it can be handled/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /assign to teammate/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /copy for handoff/i })).toBeInTheDocument()
    // The guardrail: escalations must not present a "send reply" action.
    expect(screen.queryByRole("button", { name: /send reply/i })).not.toBeInTheDocument()
  })
})
