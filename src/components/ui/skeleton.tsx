import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }

// Specialized skeleton components
export function MessageSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}

export function ChatSkeleton() {
  return (
    <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6 max-w-6xl mx-auto w-full">
      <div className="flex justify-start">
        <div className="max-w-[85%]">
          <MessageSkeleton />
        </div>
      </div>
      <div className="flex justify-end">
        <div className="max-w-[85%]">
          <MessageSkeleton />
        </div>
      </div>
      <div className="flex justify-start">
        <div className="max-w-[85%]">
          <MessageSkeleton />
        </div>
      </div>
    </div>
  )
}

export function MessageBubbleSkeleton() {
  return (
    <div className="flex justify-start">
      <div className="flex w-full md:max-w-[85%] items-start space-x-3">
        <div className="border rounded-lg p-3 md:p-4 w-full bg-card">
          <div className="space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <div className="flex gap-2 pt-2">
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-6 w-16" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function TemplateCardSkeleton() {
  return (
    <div className="border rounded-lg p-4 bg-card">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-5 rounded-full" />
          <Skeleton className="h-5 w-32" />
        </div>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-6 w-24" />
        </div>
      </div>
    </div>
  );
}
