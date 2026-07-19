import React from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'warning' | 'success';
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  const baseStyles = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";
  
  const variants = {
    default: "border-transparent bg-slate-900 text-white hover:bg-slate-900/80",
    secondary: "border-transparent bg-slate-100 text-slate-900 hover:bg-slate-100/80",
    destructive: "border-transparent bg-red-500 text-white hover:bg-red-500/80",
    warning: "border-transparent bg-amber-500 text-white hover:bg-amber-500/80",
    success: "border-transparent bg-emerald-500 text-white hover:bg-emerald-500/80",
    outline: "text-slate-950",
  };

  return (
    <div className={cn(baseStyles, variants[variant], className)} {...props} />
  );
}
