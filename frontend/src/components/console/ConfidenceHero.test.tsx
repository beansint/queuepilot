import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ConfidenceHero } from "@/components/console/ConfidenceHero"
import { SAMPLE_RESPONSE } from "@/test/fixtures"

describe("ConfidenceHero", () => {
  it("renders the confidence percentage and the decision pill", () => {
    render(<ConfidenceHero response={SAMPLE_RESPONSE} />)
    // Big number + percent sup
    expect(
      screen.getByText(
        (_content, el) => el?.tagName === "DIV" && (el.textContent ?? "").replace(/\s/g, "") === "64%",
      ),
    ).toBeInTheDocument()
    // escalate === false -> "Handle now" pill
    expect(screen.getByText("Handle now")).toBeInTheDocument()
    expect(screen.getByText("+0.02 over the handle line")).toBeInTheDocument()
    // Weighted total from debug.confidence_breakdown.final
    expect(screen.getByText("= 0.64")).toBeInTheDocument()
  })

  it("reveals the full breakdown rows after clicking Show breakdown", async () => {
    const user = userEvent.setup()
    render(<ConfidenceHero response={SAMPLE_RESPONSE} />)

    const toggle = screen.getByRole("button", { name: /show breakdown/i })
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    // Detail rows are not mounted while collapsed.
    expect(screen.queryByText("Retrieval strength")).not.toBeInTheDocument()

    await user.click(toggle)

    expect(screen.getByRole("button", { name: /hide breakdown/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    )

    // Full-width labeled breakdown rows + total are now revealed. Use labels
    // unique to the detail rows (the legend uses shorter variants).
    expect(screen.getByText("Retrieval strength")).toBeInTheDocument()
    expect(screen.getByText("Missing-info penalty")).toBeInTheDocument()
    expect(screen.getByText("Total confidence")).toBeInTheDocument()
  })
})
