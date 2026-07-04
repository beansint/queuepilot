export interface NavItemProps {
  icon: React.ReactNode
  label: string
  active?: boolean
  disabled?: boolean
  disabledHint?: string
  badge?: string
  onClick: () => void
  /** Bumps the row to a ≥44px touch target for the mobile drawer; desktop stays compact. */
  touch?: boolean
}

/** Shared nav-row button used by both the desktop NavRail and the mobile drawer. */
export function NavItem({ icon, label, active, disabled, disabledHint, badge, onClick, touch }: NavItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-current={active ? "page" : undefined}
      title={disabled ? disabledHint : undefined}
      className={
        "flex w-full items-center gap-2.5 rounded-lg px-2.5 text-left text-[13.5px] font-medium tracking-[-0.006em] transition-colors focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 " +
        (touch ? "min-h-11 py-2.5 " : "py-2 ") +
        (active
          ? "bg-accent text-accent-foreground font-semibold"
          : disabled
            ? "cursor-not-allowed text-muted-foreground/40"
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
    </button>
  )
}
