import { Skeleton } from "@/components/ui/skeleton"

export function ResultSkeleton() {
  return (
    <div aria-busy="true" aria-live="polite" className="flex flex-col gap-5">
      <Skeleton className="h-[132px] w-full rounded-2xl" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Skeleton className="h-[76px] rounded-xl" />
        <Skeleton className="h-[76px] rounded-xl" />
        <Skeleton className="h-[76px] rounded-xl" />
        <Skeleton className="h-[92px] rounded-xl sm:col-span-3" />
      </div>
      <Skeleton className="h-[180px] w-full rounded-2xl" />
      <Skeleton className="h-[220px] w-full rounded-2xl" />
      <span className="sr-only">Analyzing ticket…</span>
    </div>
  )
}
