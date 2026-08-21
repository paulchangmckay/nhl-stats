import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { POSITION_COLORS } from "@/lib/positionColors";

const POSITIONS = ["C", "L", "R", "D", "G"] as const;

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
          className={POSITION_COLORS[pos].toggleClass}
        >
          {pos}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
