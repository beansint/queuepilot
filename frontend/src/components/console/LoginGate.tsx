import { InviteGate } from "@/components/console/InviteGate"

interface LoginGateProps {
  /** Called after a successful login so the caller can re-check auth status and reveal the console. */
  onAuthed: () => void
}

/**
 * Full-screen invite-code gate shown when `GET /auth/status` reports `required && !authenticated`
 * (Slice E — D16). Renders the reusable `InviteGate` card (also used inside the landing page's
 * "Get started" modal) centered on the console's dark `bg-hero` background.
 */
export function LoginGate({ onAuthed }: LoginGateProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <InviteGate onAuthed={onAuthed} />
    </div>
  )
}
