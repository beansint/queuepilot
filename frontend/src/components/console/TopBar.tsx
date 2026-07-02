import { Plus } from "lucide-react"

interface TopBarProps {
  onNewAnalysis: () => void
  subtitle: string
}

export function TopBar({ onNewAnalysis, subtitle }: TopBarProps) {
  return (
    <div className="mb-6.5 flex items-center justify-between gap-4">
      <div>
        <div className="text-[19px] font-bold tracking-[-0.02em]">Ticket analysis</div>
        <div className="mt-0.5 text-[13px] text-muted-foreground">{subtitle}</div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onNewAnalysis}
          className="group flex items-center gap-1.5 rounded-lg border border-primary bg-primary px-3.5 py-2.5 pl-4 text-[13.5px] font-semibold tracking-[-0.006em] text-primary-foreground shadow-sm transition-all hover:-translate-y-px hover:bg-hero hover:border-hero hover:shadow-md focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
        >
          <Plus className="size-[15px]" />
          New analysis
          <span className="ml-0.5 rounded border border-white/20 bg-white/15 px-1.5 py-px font-mono text-[10.5px] opacity-85">
            ⌘↵
          </span>
        </button>
        <div className="flex size-9 items-center justify-center rounded-full border-2 border-white bg-accent-foreground font-mono text-[13px] font-bold text-primary-foreground shadow-sm">
          VP
        </div>
      </div>
    </div>
  )
}
