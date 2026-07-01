import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SimilarTicketsTable } from "@/components/console/SimilarTicketsTable"
import { SAMPLE_RESPONSE } from "@/test/fixtures"

describe("SimilarTicketsTable", () => {
  it("renders one row per similar ticket with its score, subject, and queue", () => {
    render(<SimilarTicketsTable tickets={SAMPLE_RESPONSE.similar_tickets} />)

    // 3 body rows + 1 header row.
    const rows = screen.getAllByRole("row")
    expect(rows).toHaveLength(SAMPLE_RESPONSE.similar_tickets.length + 1)

    // Scores render (mono, 2dp).
    expect(screen.getByText("0.42")).toBeInTheDocument()
    expect(screen.getByText("0.39")).toBeInTheDocument()
    expect(screen.getByText("0.31")).toBeInTheDocument()

    // Subjects (snippets) render.
    expect(screen.getByText("VPN fails to connect after Windows 11 22H2 update")).toBeInTheDocument()
    expect(screen.getByText("GlobalProtect drops connection post Windows update")).toBeInTheDocument()

    // Queues render (Technical Support appears twice).
    expect(screen.getAllByText("Technical Support")).toHaveLength(2)
    expect(screen.getByText("IT")).toBeInTheDocument()
  })

  it("shows an empty state when there are no similar tickets", () => {
    render(<SimilarTicketsTable tickets={[]} />)
    expect(screen.getByText(/no similar tickets found/i)).toBeInTheDocument()
  })
})
