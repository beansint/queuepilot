import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MobileNav } from "@/components/console/MobileNav"

describe("MobileNav", () => {
  it("renders the hamburger trigger, closed by default", () => {
    render(<MobileNav route="console" onNavigate={vi.fn()} onLogout={vi.fn()} evidenceEnabled />)

    const trigger = screen.getByRole("button", { name: /open menu/i })
    expect(trigger).toBeInTheDocument()
    expect(trigger).toHaveAttribute("aria-expanded", "false")
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAttribute("aria-hidden", "true")
  })

  it("opens the drawer on click and shows the nav destinations", async () => {
    const user = userEvent.setup()
    render(<MobileNav route="console" onNavigate={vi.fn()} onLogout={vi.fn()} evidenceEnabled />)

    await user.click(screen.getByRole("button", { name: /open menu/i }))

    expect(screen.getByRole("button", { name: /open menu/i })).toHaveAttribute("aria-expanded", "true")
    const dialog = screen.getByRole("dialog")
    expect(dialog).toHaveAttribute("aria-hidden", "false")
    expect(screen.getByRole("button", { name: "Analysis" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Evidence" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Support" })).toBeInTheDocument()
  })

  it("fires onNavigate and closes the drawer when a destination is selected", async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<MobileNav route="console" onNavigate={onNavigate} onLogout={vi.fn()} evidenceEnabled />)

    await user.click(screen.getByRole("button", { name: /open menu/i }))
    await user.click(screen.getByRole("button", { name: "Overview" }))

    expect(onNavigate).toHaveBeenCalledWith("overview")
    expect(screen.getByRole("button", { name: /open menu/i })).toHaveAttribute("aria-expanded", "false")
  })

  it("fires onLogout and closes the drawer when Log out is clicked", async () => {
    const user = userEvent.setup()
    const onLogout = vi.fn()
    render(<MobileNav route="console" onNavigate={vi.fn()} onLogout={onLogout} evidenceEnabled />)

    await user.click(screen.getByRole("button", { name: /open menu/i }))
    await user.click(screen.getByRole("button", { name: /log out/i }))

    expect(onLogout).toHaveBeenCalled()
    expect(screen.getByRole("button", { name: /open menu/i })).toHaveAttribute("aria-expanded", "false")
  })

  it("closes on Escape and restores focus to the trigger", async () => {
    const user = userEvent.setup()
    render(<MobileNav route="console" onNavigate={vi.fn()} onLogout={vi.fn()} evidenceEnabled />)

    const trigger = screen.getByRole("button", { name: /open menu/i })
    await user.click(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "true")

    await user.keyboard("{Escape}")

    expect(trigger).toHaveAttribute("aria-expanded", "false")
    expect(trigger).toHaveFocus()
  })

  it("closes on backdrop click", async () => {
    const user = userEvent.setup()
    render(<MobileNav route="console" onNavigate={vi.fn()} onLogout={vi.fn()} evidenceEnabled />)

    await user.click(screen.getByRole("button", { name: /open menu/i }))
    await user.click(screen.getByRole("button", { name: /close menu/i }))

    expect(screen.getByRole("button", { name: /open menu/i })).toHaveAttribute("aria-expanded", "false")
  })

  it("disables Evidence when no analysis result exists yet", async () => {
    const user = userEvent.setup()
    render(<MobileNav route="console" onNavigate={vi.fn()} onLogout={vi.fn()} evidenceEnabled={false} />)

    await user.click(screen.getByRole("button", { name: /open menu/i }))

    expect(screen.getByRole("button", { name: "Evidence" })).toBeDisabled()
  })
})
