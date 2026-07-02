import {
  Activity,
  BarChart3,
  Database,
  Inbox,
  LifeBuoy,
  Plug,
  Route,
  Settings,
  SlidersHorizontal,
} from "lucide-react"
import { BrandGlyph } from "@/components/BrandGlyph"

interface NavLinkProps {
  icon: React.ReactNode
  label: string
  active?: boolean
  badge?: string
}

function NavLink({ icon, label, active, badge }: NavLinkProps) {
  return (
    <a
      href="#"
      aria-current={active ? "page" : undefined}
      onClick={(e) => e.preventDefault()}
      className={
        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium tracking-[-0.006em] transition-colors " +
        (active
          ? "bg-accent text-accent-foreground font-semibold"
          : "text-muted-foreground hover:bg-background hover:text-foreground")
      }
    >
      <span className="[&_svg]:size-4 shrink-0">{icon}</span>
      <span>{label}</span>
      {badge && (
        <span className="ml-auto rounded-full bg-primary px-1.5 py-px font-mono text-[10.5px] font-bold text-primary-foreground">
          {badge}
        </span>
      )}
    </a>
  )
}

export function NavRail() {
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
        <NavLink icon={<Activity />} label="Analysis" active badge="1" />
        <NavLink icon={<Inbox />} label="Queue" />
        <NavLink icon={<BarChart3 />} label="Insights" />
        <NavLink icon={<Database />} label="Evidence base" />
      </div>

      <div className="flex flex-col gap-0.5">
        <div className="mb-1.5 px-2.5 font-mono text-[10.5px] font-bold tracking-[0.08em] text-muted-foreground/80 uppercase">
          Configure
        </div>
        <NavLink icon={<Route />} label="Routing rules" />
        <NavLink icon={<SlidersHorizontal />} label="Thresholds" />
        <NavLink icon={<Plug />} label="Integrations" />
      </div>

      <div className="flex-1" />

      <div className="flex flex-col gap-0.5">
        <NavLink icon={<Settings />} label="Settings" />
        <NavLink icon={<LifeBuoy />} label="Support" />
      </div>

      <div className="flex items-center gap-2.5 border-t border-border pt-3.5 pl-2.5">
        <div className="flex size-[26px] shrink-0 items-center justify-center rounded-full bg-accent-foreground font-mono text-[11px] font-bold text-primary-foreground">
          RH
        </div>
        <div className="text-xs font-medium text-muted-foreground">
          <strong className="block text-[12.5px] font-semibold text-foreground">Riley Hale</strong>
          Support lead
        </div>
      </div>
    </nav>
  )
}
