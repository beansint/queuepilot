import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import App from "@/App"

describe("App (empty / initial state)", () => {
  it("shows the friendly empty state and the ticket input before any analysis", () => {
    render(<App />)
    expect(screen.getByText("Ticket analysis")).toBeInTheDocument()
    expect(screen.getByText("Paste a ticket and hit Analyze")).toBeInTheDocument()
    // Labelled textarea is present and accessible.
    expect(screen.getByLabelText(/new ticket/i)).toBeInTheDocument()
  })
})
