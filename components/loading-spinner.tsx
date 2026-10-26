"use client";

import React from "react";
import { FlickerSpinner, type FlickerGrids } from "flicker-dot";

export const RADAR_GRIDS: FlickerGrids = [
  [false,true,true,true,true,true,false,false,false,true,true,true,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,true,true,false,false,false,true,true,true,true,false,false,false,false,false,true,true,false,false,false,false,false,false,true,false,false,false,false,false,false,false],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,true,true,true,false,false,false,true,true,true,true,true,false],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false],
  [false,false,false,false,false,false,false,true,false,false,false,false,false,false,true,true,false,false,false,false,false,true,true,true,true,false,false,false,true,true,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [true,true,true,false,false,false,false,true,true,true,false,false,false,false,true,true,true,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false]
];

export const CHASER_GRIDS: FlickerGrids = [
  [true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,true,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [true,true,true,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [true,true,true,true,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [false,false,true,true,true,true,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [false,false,false,false,true,true,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,true,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,true,true,true],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,true,true,true,true],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,true,true,true,true,false,false],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,true,true,false,false,false,false],
  [false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false,true,false,false,false,false,false,false]
];

export interface LoadingSpinnerProps {
  size?: number;
  variant?: "7x7" | "5x5";
  pattern?: "radar" | "chaser";
  onColor?: string;
  offColor?: string;
  speed?: number;
  className?: string;
  title?: string;
}

export function LoadingSpinner({
  size = 28,
  variant = "7x7",
  pattern = "radar",
  onColor = "currentColor",
  offColor = "rgba(255, 255, 255, 0.12)",
  speed = 1,
  className,
  title = "Processing...",
}: LoadingSpinnerProps) {
  const grids = pattern === "radar" ? RADAR_GRIDS : CHASER_GRIDS;
  return (
    <FlickerSpinner
      grids={grids}
      variant={variant}
      size={size}
      speed={speed}
      onColor={onColor}
      offColor={offColor}
      title={title}
      className={className}
    />
  );
}

export { FlickerSpinner };
