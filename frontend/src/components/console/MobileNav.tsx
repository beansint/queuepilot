import { useEffect, useId, useRef, useState } from "react"
import { LifeBuoy, LogOut, Menu } from "lucide-react"
import { BrandGlyph } from "@/components/BrandGlyph"
import { NavItem } from "@/components/console/NavItem"
import { getGeneralItems, getWorkspaceItems } from "@/components/console/navItems"
import { cn } from "@/lib/utils"
import { CONTACT_URL } from "@/lib/site"
import type { Route } from "@/lib/useHashRoute"

interface MobileNavProps {
  route: Route
  onNavigate: (route: Route) => void
  onLogout: () => void
  /** Whether an analysis result exists — Evidence is a dead end without one. */
  evidenceEnabled: boolean
}

/**
 * Mobile-only top bar + slide-in drawer (`md:hidden`) — the primary NavRail is
 * `hidden md:flex`, so below the `md` breakpoint this is the only way to switch
 * routes, reach Overview/Support, or log out. Hand-rolled (no Sheet/Dialog
 * primitive in this project) but keeps the same nav-item visual language.
 */
export function MobileNav({ route, onNavigate, onLogout, evidenceEnabled }: MobileNavProps) {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const drawerId = useId()

  const close = () => {
    // Move focus back to the trigger before the panel becomes aria-hidden,
    // so we never leave focus stranded inside a hidden subtree.
    triggerRef.current?.focus()
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    panelRef.current?.focus()
    // Lock body scroll while the drawer is open so the page behind it doesn't scroll.
    const original = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = original
    }
  }, [open])

  function handleNavigate(next: Route) {
    onNavigate(next)
    close()
  }

  function handleLogout() {
    onLogout()
    close()
  }

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2.5 border-b border-border bg-card px-3.5 md:hidden">
        <button
          ref={triggerRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          aria-expanded={open}
          aria-controls={drawerId}
          className="flex size-11 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
        >
          <Menu className="size-5" />
        </button>
        <div className="flex items-center gap-2">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-[8px] bg-primary shadow-sm">
            <BrandGlyph className="size-4" />
          </div>
          <span className="text-[14px] font-extrabold tracking-[-0.02em]">QueuePilot</span>
        </div>
      </header>

      <div className={cn("fixed inset-0 z-40 md:hidden", !open && "pointer-events-none")}>
        <button
          type="button"
          aria-label="Close menu"
          tabIndex={open ? 0 : -1}
          onClick={close}
          className={cn(
            "absolute inset-0 bg-black/50 transition-opacity ease-out motion-reduce:transition-none",
            open ? "duration-200 opacity-100" : "duration-150 opacity-0",
          )}
        />
        <div
          id={drawerId}
          ref={panelRef}
          role="dialog"
          aria-modal={open}
          aria-hidden={!open}
          aria-label="Navigation menu"
          tabIndex={-1}
          className={cn(
            "absolute inset-y-0 left-0 flex w-[min(80vw,272px)] flex-col gap-6 border-r border-border bg-card px-3.5 py-5 shadow-xl outline-none transition-transform ease-out motion-reduce:transition-none",
            open ? "translate-x-0 duration-200" : "-translate-x-full duration-150",
          )}
        >
          <div className="flex items-center gap-2.5 px-2 pb-2">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-primary shadow-sm">
              <BrandGlyph className="size-[19px]" />
            </div>
            <div className="flex flex-col gap-px">
              <span className="text-[15px] font-extrabold tracking-[-0.02em]">QueuePilot</span>
              <span className="text-[11px] font-medium text-muted-foreground/80">AI ops assistant</span>
            </div>
          </div>

          <div className="flex flex-col gap-0.5">
            <div className="mb-1.5 px-2.5 font-mono text-[10.5px] font-bold tracking-[0.08em] text-muted-foreground/80 uppercase">
              Workspace
            </div>
            {getWorkspaceItems(evidenceEnabled).map((item) => (
              <NavItem
                key={item.key}
                icon={item.icon}
                label={item.label}
                active={route === item.route}
                disabled={item.disabled}
                disabledHint={item.disabledHint}
                onClick={() => handleNavigate(item.route)}
                touch
              />
            ))}
          </div>

          <div className="flex flex-col gap-0.5">
            <div className="mb-1.5 px-2.5 font-mono text-[10.5px] font-bold tracking-[0.08em] text-muted-foreground/80 uppercase">
              General
            </div>
            {getGeneralItems().map((item) => (
              <NavItem
                key={item.key}
                icon={item.icon}
                label={item.label}
                active={route === item.route}
                onClick={() => handleNavigate(item.route)}
                touch
              />
            ))}
            <a
              href={CONTACT_URL}
              target="_blank"
              rel="noopener noreferrer"
              onClick={close}
              className="flex min-h-11 items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-[13.5px] font-medium tracking-[-0.006em] text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              <span className="[&_svg]:size-4 shrink-0">
                <LifeBuoy />
              </span>
              <span>Support</span>
            </a>
          </div>

          <div className="flex-1" />

          <div className="flex items-center gap-2.5 border-t border-border pt-3.5 pl-2.5">
            <div className="flex size-[26px] shrink-0 items-center justify-center rounded-full bg-accent-foreground font-mono text-[11px] font-bold text-primary-foreground">
              VP
            </div>
            <div className="min-w-0 text-xs font-medium text-muted-foreground">
              <strong className="block truncate text-[12.5px] font-semibold text-foreground">Vincent Pacaña</strong>
              Support lead
            </div>
            <button
              type="button"
              onClick={handleLogout}
              aria-label="Log out"
              title="Log out"
              className="ml-auto flex size-11 shrink-0 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/5 hover:text-destructive focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
