import { LifeBuoy, LogOut } from "lucide-react"
import { BrandGlyph } from "@/components/BrandGlyph"
import { NavItem } from "@/components/console/NavItem"
import { getGeneralItems, getWorkspaceItems } from "@/components/console/navItems"
import { CONTACT_URL } from "@/lib/site"
import type { Route } from "@/lib/useHashRoute"

interface NavRailProps {
  route: Route
  onNavigate: (route: Route) => void
  onLogout: () => void
  /** Whether an analysis result exists — Evidence is a dead end without one. */
  evidenceEnabled: boolean
}

export function NavRail({ route, onNavigate, onLogout, evidenceEnabled }: NavRailProps) {
  return (
    <nav
      aria-label="Primary navigation"
      className="sticky top-0 hidden h-screen flex-col gap-6 border-r border-border bg-card px-3.5 py-5 md:flex"
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
            onClick={() => onNavigate(item.route)}
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
            onClick={() => onNavigate(item.route)}
          />
        ))}
        <a
          href={CONTACT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium tracking-[-0.006em] text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
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
          onClick={onLogout}
          aria-label="Log out"
          title="Log out"
          className="ml-auto flex size-8 shrink-0 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/5 hover:text-destructive focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
        >
          <LogOut className="size-4" />
        </button>
      </div>
    </nav>
  )
}
