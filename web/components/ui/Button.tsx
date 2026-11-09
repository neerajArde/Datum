// components/ui/Button.tsx
// The one button style for the whole app. Pick a variant instead of writing classes:
//   primary   - the main action on a screen (Download CSV, Start reviewing)
//   secondary - a lesser action next to it (Spot-check 5)
//   ghost     - a quiet text-style action (Back to table)
// and a size: md (default), lg (a bit bigger), inline (no padding, sits in a line of text)

import type { ComponentProps } from "react";

type Variant = "primary" | "secondary" | "ghost";
type Size = "inline" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-ink-soft",
  secondary: "border border-line-strong bg-surface text-body hover:bg-subtle",
  ghost: "text-soft hover:text-ink",
};

// sizes are separate from className on purpose: two padding classes on one element
// (e.g. px-3 and px-0) don't reliably override each other in Tailwind
const SIZES: Record<Size, string> = {
  inline: "",
  md: "px-3 py-1.5",
  lg: "px-4 py-2",
};

// ComponentProps<"button"> = every normal <button> prop (onClick, disabled, type...) plus ours
type Props = ComponentProps<"button"> & { variant?: Variant; size?: Size };

export default function Button({ variant = "primary", size = "md", className = "", type = "button", ...rest }: Props) {
  return (
    <button
      type={type}
      className={`rounded-md text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      {...rest}
    />
  );
}
