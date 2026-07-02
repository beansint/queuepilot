import { useId } from "react"

/**
 * QueuePilot brand mark — a gradient "Q" whose tail is a routing arrow (queue → routed).
 * Sky→blue gradient so it pops on the ink brand tile. `useId` gives each instance a unique
 * gradient id so multiple marks on one page don't collide.
 */
export function BrandGlyph({ className }: { className?: string }) {
  const id = useId()
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={id} x1="4" y1="4" x2="20" y2="20" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7DD3FC" />
          <stop offset="1" stopColor="#0EA5E9" />
        </linearGradient>
      </defs>
      <path
        fill={`url(#${id})`}
        fillRule="evenodd"
        d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4.6a4.4 4.4 0 1 1 0 8.8 4.4 4.4 0 0 1 0-8.8Z"
      />
      <path
        fill="none"
        stroke={`url(#${id})`}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m14 14 5 5m0-3.2V19h-3.2"
      />
    </svg>
  )
}
