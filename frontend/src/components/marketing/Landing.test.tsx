import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Landing } from "@/components/marketing/Landing"
import { login } from "@/lib/api"
import { CONTACT_URL } from "@/lib/site"

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...actual,
    login: vi.fn(),
  }
})

const loginMock = vi.mocked(login)

describe("Landing", () => {
  beforeEach(() => {
    loginMock.mockReset()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders the hero headline and CTAs", () => {
    render(<Landing onAuthed={vi.fn()} />)
    expect(screen.getByText(/knows when/i)).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: /get started/i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole("link", { name: "Contact" }).length).toBeGreaterThan(0)
  })

  it("renders all 6 engineering-credibility stats", () => {
    render(<Landing onAuthed={vi.fn()} />)
    for (const value of ["3,000", "Hybrid", "8-stage", "ECE ≈ 0.15", "340+", "Traced"]) {
      expect(screen.getByText(value)).toBeInTheDocument()
    }
  })

  it("renders all 4 capability rows", () => {
    render(<Landing onAuthed={vi.fn()} />)
    for (const title of [
      "Auto-routing",
      "Grounded replies",
      "Guarded escalation",
      "Explainable & audited",
    ]) {
      expect(screen.getByText(title)).toBeInTheDocument()
    }
  })

  it("points every Contact link at CONTACT_URL", () => {
    render(<Landing onAuthed={vi.fn()} />)
    const contactLinks = screen.getAllByRole("link", { name: "Contact" })
    expect(contactLinks.length).toBeGreaterThan(0)
    for (const link of contactLinks) {
      expect(link).toHaveAttribute("href", CONTACT_URL)
      expect(link).toHaveAttribute("target", "_blank")
      expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"))
    }
  })

  it("opens the invite modal with the code input when Get started is clicked", async () => {
    const user = userEvent.setup()
    render(<Landing onAuthed={vi.fn()} />)

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()

    const [getStarted] = screen.getAllByRole("button", { name: /get started/i })
    await user.click(getStarted)

    expect(await screen.findByRole("dialog", { name: /invite code/i })).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("closes the modal on Escape", async () => {
    const user = userEvent.setup()
    render(<Landing onAuthed={vi.fn()} />)

    const [getStarted] = screen.getAllByRole("button", { name: /get started/i })
    await user.click(getStarted)
    expect(await screen.findByRole("dialog")).toBeInTheDocument()

    await user.keyboard("{Escape}")
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("closes the modal when clicking the scrim", async () => {
    const user = userEvent.setup()
    render(<Landing onAuthed={vi.fn()} />)

    const [getStarted] = screen.getAllByRole("button", { name: /get started/i })
    await user.click(getStarted)
    const dialog = await screen.findByRole("dialog")

    // The scrim is the dialog's positioning parent (role="presentation").
    const scrim = dialog.parentElement as HTMLElement
    await user.click(scrim)

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("calls onAuthed after a successful login from the modal", async () => {
    const user = userEvent.setup()
    loginMock.mockResolvedValue(undefined)
    const onAuthed = vi.fn()
    render(<Landing onAuthed={onAuthed} />)

    const [getStarted] = screen.getAllByRole("button", { name: /get started/i })
    await user.click(getStarted)

    const input = await screen.findByRole("textbox")
    await user.type(input, "abc123")
    await user.click(screen.getByRole("button", { name: /^enter$/i }))

    await waitFor(() => expect(loginMock).toHaveBeenCalledWith("abc123"))
    await waitFor(() => expect(onAuthed).toHaveBeenCalled())
  })
})
