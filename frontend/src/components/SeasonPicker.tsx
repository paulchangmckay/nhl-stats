import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";

export const SEASONS = [
  { id: "20252026", label: "2025–26" },
  { id: "20242025", label: "2024–25" },
  { id: "20232024", label: "2023–24" },
  { id: "20222023", label: "2022–23" },
  { id: "20212022", label: "2021–22" },
  { id: "20202021", label: "2020–21" },
];

function summaryLabel(active: string[]): string {
  if (active.includes("all")) return "All Seasons (Career)";
  if (active.length === 1) {
    return SEASONS.find((s) => s.id === active[0])?.label ?? active[0];
  }
  return `${active.length} Seasons`;
}

interface SeasonPickerProps {
  active: string[];
  onChange: (next: string[]) => void;
}

export function SeasonPicker({ active, onChange }: SeasonPickerProps) {
  const [open, setOpen] = useState(false);

  function toggleAll() {
    onChange(active.includes("all") ? ["20252026"] : ["all"]);
  }

  function toggleSeason(id: string) {
    if (active.includes("all")) {
      onChange([id]);
    } else if (active.includes(id)) {
      if (active.length > 1) onChange(active.filter((s) => s !== id));
      // else: no-op — at least one season must always remain selected
    } else {
      onChange([...active, id]);
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            className="flex min-w-40 items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm"
          >
            {summaryLabel(active)}
          </button>
        }
      />
      <PopoverContent className="w-64 p-2">
        <label className="flex items-center gap-2 rounded px-2 py-1.5 text-sm">
          <Checkbox checked={active.includes("all")} onCheckedChange={toggleAll} />
          <span>All Seasons (Career)</span>
        </label>
        {SEASONS.map((s) => (
          <label key={s.id} className="flex items-center gap-2 rounded px-2 py-1.5 text-sm">
            <Checkbox
              checked={active.includes(s.id)}
              onCheckedChange={() => toggleSeason(s.id)}
            />
            <span>{s.label}</span>
          </label>
        ))}
      </PopoverContent>
    </Popover>
  );
}
