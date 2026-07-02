import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import App from "@/App"

describe("App (empty / initial state)", () => {
  beforeEach(() => {
    // App checks GET /auth/status on mount (Slice E login gate); default to "not required"
    // so these pre-existing console tests keep exercising the un-gated console.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ required: false, authenticated: false }),
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("shows the friendly empty state and the ticket input before any analysis", async () => {
    render(<App />)
    expect(await screen.findByText("Ticket analysis")).toBeInTheDocument()
    expect(screen.getByText("Paste a ticket and hit Analyze")).toBeInTheDocument()
    // Labelled textarea is present and accessible.
    expect(screen.getByLabelText(/new ticket/i)).toBeInTheDocument()
  })
})
