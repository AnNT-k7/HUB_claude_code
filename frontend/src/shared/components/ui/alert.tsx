import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/shared/utils/classnames";

type AlertTone = "info" | "success" | "warning" | "danger";

interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  tone?: AlertTone;
  title?: string;
  children: ReactNode;
}

const toneClasses: Record<AlertTone, string> = {
  info: "border-blue-200 bg-blue-50 text-blue-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-900",
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
  ...props
}: AlertProps) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("rounded-xl border px-4 py-3 text-sm", toneClasses[tone], className)}
      {...props}
    >
      {title ? <p className="mb-1 font-bold">{title}</p> : null}
      <div className="leading-6">{children}</div>
    </div>
  );
}
