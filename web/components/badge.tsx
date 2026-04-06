import type { HTMLAttributes } from "react";

const variants = {
  success: "ds-badge ds-badge--success",
  error: "ds-badge ds-badge--error",
  warning: "ds-badge ds-badge--warning",
  info: "ds-badge ds-badge--info",
  neutral: "ds-badge ds-badge--neutral",
} as const;

export type BadgeVariant = keyof typeof variants;

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({
  variant = "neutral",
  className = "",
  ...props
}: BadgeProps) {
  return (
    <span
      className={`${variants[variant]} ${className}`.trim()}
      {...props}
    />
  );
}
