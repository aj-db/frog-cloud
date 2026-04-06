import type { HTMLAttributes, ReactNode } from "react";

const variants = {
  success: "ds-alert ds-alert--success",
  error: "ds-alert ds-alert--error",
  info: "ds-alert ds-alert--info",
  warning: "ds-alert ds-alert--warning",
} as const;

export type AlertVariant = keyof typeof variants;

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
  title?: string;
  children: ReactNode;
}

export function Alert({
  variant = "info",
  title,
  children,
  className = "",
  ...props
}: AlertProps) {
  return (
    <div className={`${variants[variant]} ${className}`.trim()} role="status" {...props}>
      {title ? (
        <p className="mb-1 font-soehne text-[13px] font-semibold text-[var(--charcoal)]">
          {title}
        </p>
      ) : null}
      <div className="text-[13px] text-[var(--charcoal)]">{children}</div>
    </div>
  );
}
