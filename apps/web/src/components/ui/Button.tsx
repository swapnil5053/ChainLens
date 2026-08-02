/** Primary (filled accent) or quiet (text). Press nudges 1px; no scale bounce. */
import type { ButtonHTMLAttributes } from "react";

export function Button({
  variant = "quiet",
  disabledReason,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "quiet";
  disabledReason?: string;
}) {
  const base =
    "inline-flex min-h-9 items-center justify-center gap-2 rounded-sm px-3.5 text-body " +
    "font-medium transition-[background-color,color,transform] duration-(--duration) ease-(--ease) " +
    "active:translate-y-px disabled:cursor-not-allowed disabled:opacity-45";
  const skin =
    variant === "primary"
      ? "bg-accent text-ground hover:bg-accent-strong"
      : "text-accent hover:bg-panel";
  return (
    <button
      type="button"
      className={`${base} ${skin} ${className}`}
      title={props.disabled ? disabledReason : undefined}
      {...props}
    />
  );
}
