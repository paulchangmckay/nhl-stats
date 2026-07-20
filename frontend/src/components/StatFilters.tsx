import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { StatMins } from "@/lib/types";

const FIELDS: { key: keyof StatMins; label: string }[] = [
  { key: "gp", label: "GP≥" },
  { key: "goals", label: "G≥" },
  { key: "assists", label: "A≥" },
  { key: "points", label: "Pts≥" },
];

interface StatFiltersProps {
  value: StatMins;
  onChange: (next: StatMins) => void;
}

export function StatFilters({ value, onChange }: StatFiltersProps) {
  const [localValues, setLocalValues] = useState<StatMins>(value);

  useEffect(() => {
    setLocalValues(value);
  }, [value]);

  const handleChange = (key: keyof StatMins, raw: string) => {
    const newValue = { ...localValues, [key]: raw === "" ? null : Number(raw) };
    setLocalValues(newValue);
    onChange(newValue);
  };

  return (
    <div className="flex items-center gap-3">
      {FIELDS.map(({ key, label }) => (
        <div key={key} className="flex items-center gap-1.5">
          <Label htmlFor={`stat-${key}`}>{label}</Label>
          <Input
            id={`stat-${key}`}
            type="number"
            min={0}
            className="w-16"
            value={localValues[key] ?? ""}
            onChange={(e) => {
              handleChange(key, e.target.value);
            }}
          />
        </div>
      ))}
    </div>
  );
}
