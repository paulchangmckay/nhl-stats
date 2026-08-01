import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatSeasonId(seasonId: string | number): string {
  const str = String(seasonId);
  if (!/^\d{8}$/.test(str)) return str;
  return `${str.slice(0, 4)}–${str.slice(6, 8)}`;
}
