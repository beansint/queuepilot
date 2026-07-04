import { Activity, GitCompareArrows, LayoutTemplate } from "lucide-react"
import type { Route } from "@/lib/useHashRoute"

/**
 * Shared nav-destination data for the desktop NavRail and the mobile drawer
 * (MobileNav) — both render the same items via the shared `NavItem` button,
 * they just differ in surrounding chrome (grouped sidebar vs. slide-in panel).
 */
export interface NavDestination {
  key: string
  icon: React.ReactNode
  label: string
  route: Route
  disabled?: boolean
  disabledHint?: string
}

/** "Workspace" group: the core console destinations. */
export function getWorkspaceItems(evidenceEnabled: boolean): NavDestination[] {
  return [
    { key: "console", icon: <Activity />, label: "Analysis", route: "console" },
    {
      key: "evidence",
      icon: <GitCompareArrows />,
      label: "Evidence",
      route: "evidence",
      disabled: !evidenceEnabled,
      disabledHint: "Run an analysis to see similar-ticket evidence",
    },
  ]
}

/** "General" group: destinations outside the core workspace. */
export function getGeneralItems(): NavDestination[] {
  return [{ key: "overview", icon: <LayoutTemplate />, label: "Overview", route: "overview" }]
}
