import type { SelectHTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn('w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-500', className)}
      {...props}
    />
  )
}
