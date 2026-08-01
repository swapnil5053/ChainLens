/**
 * A press is acknowledged by a 1px translate, not a scale bounce.
 *
 * Disabled buttons say why: `disabledReason` becomes the title, and callers with room
 * render it as adjacent text too, because a greyed control with no explanation is a dead
 * end.
 */
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
    "inline-flex min-h-8 items-center gap-2 rounded-[2px] border px-3 text-small " +
    "transition-[background-color,border-color,transform] duration-(--duration-hover) " +
    "ease-(--ease-enter) active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60";
  const skin =
    variant === "primary"
      ? "border-ink bg-ink text-ground hover:bg-ink-muted"
      : "border-rule-control bg-transparent text-ink hover:bg-panel-raised";
  return (
    <button
      type="button"
      className={`${base} ${skin} ${className}`}
      title={props.disabled ? disabledReason : undefined}
      {...props}
    />
  );
}
