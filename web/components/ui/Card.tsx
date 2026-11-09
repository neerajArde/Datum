// components/ui/Card.tsx
// The one "box" style: white surface, thin border, rounded corners.
// `as` picks the HTML tag (section, aside, div) so the page stays meaningful to screen readers.

import type { ReactNode } from "react";

type Props = {
  as?: "section" | "aside" | "div";
  className?: string;
  children: ReactNode;
};

export default function Card({ as: Tag = "div", className = "", children }: Props) {
  return <Tag className={`rounded-xl border border-line bg-surface ${className}`}>{children}</Tag>;
}
