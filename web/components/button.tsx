"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

const variantClass: Record<"primary" | "secondary" | "ghost", string> = {
  primary: "ds-btn ds-btn--primary",
  secondary: "ds-btn ds-btn--secondary",
  ghost: "ds-btn ds-btn--ghost",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  children,
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type={type}
      disabled={isDisabled}
      className={`${variantClass[variant]} ${className}`.trim()}
      {...props}
    >
      {loading ? <span className="ds-btn-spinner" aria-hidden /> : null}
      {children}
    </button>
  );
}
