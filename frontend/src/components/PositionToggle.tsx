import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

const POSITIONS = ["C", "L", "R", "D", "G"] as const;

const POSITION_CLASSES: Record<(typeof POSITIONS)[number], string> = {
  C: "text-green-500 aria-pressed:bg-green-500 aria-pressed:text-background",
  L: "text-blue-400 aria-pressed:bg-blue-400 aria-pressed:text-background",
  R: "text-sky-300 aria-pressed:bg-sky-300 aria-pressed:text-background",
  D: "text-purple-300 aria-pressed:bg-purple-300 aria-pressed:text-background",
  G: "text-orange-400 aria-pressed:bg-orange-400 aria-pressed:text-background",
};

interface PositionToggleProps {
  active: Set<string>;
  onChange: (next: Set<string>) => void;
}

export function PositionToggle({ active, onChange }: PositionToggleProps) {
  function toggle(pos: string) {
    const next = new Set(active);
    if (next.has(pos)) next.delete(pos);
    else next.add(pos);
    onChange(next);
  }

  return (
    <ToggleGroup value={Array.from(active)}>
      {POSITIONS.map((pos) => (
        <ToggleGroupItem
          key={pos}
          value={pos}
          aria-label={pos}
          onClick={() => toggle(pos)}
          className={POSITION_CLASSES[pos]}
        >
          {pos}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
