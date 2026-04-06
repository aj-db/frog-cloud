import type { InputHTMLAttributes } from "react";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({
  label,
  error,
  id,
  className = "",
  ...props
}: InputProps) {
  const inputId = id ?? props.name;
  return (
    <div className="w-full">
      {label ? (
        <label htmlFor={inputId} className="ds-label">
          {label}
        </label>
      ) : null}
      <input id={inputId} className={`ds-input ${className}`.trim()} {...props} />
      {error ? (
        <p className="mt-1 text-[12px] font-medium" style={{ color: "var(--red)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
