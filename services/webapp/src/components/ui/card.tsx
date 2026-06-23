import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-xl border border-slate-800 bg-slate-950/80 p-4 shadow-[0_0_0_1px_rgba(14,165,233,0.04)]', className)}
      {...props}
    />
  )
}
