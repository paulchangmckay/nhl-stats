import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import type { Team } from "@/lib/types";

function logoUrl(abbrev: string) {
  return `https://assets.nhle.com/logos/nhl/svg/${abbrev}_light.svg`;
}

interface TeamPickerProps {
  teams: Team[];
  active: string;
  onChange: (abbrev: string) => void;
}

export function TeamPicker({ teams, active, onChange }: TeamPickerProps) {
  const [open, setOpen] = useState(false);
  const activeTeam = teams.find((t) => t.abbrev === active);
  const label = activeTeam ? activeTeam.common_name : "All Teams";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            className="flex min-w-40 items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm"
          >
            {label}
          </button>
        }
      />
      <PopoverContent className="w-64 p-0">
        <Command>
          <CommandList>
            <CommandGroup>
              <CommandItem
                onSelect={() => {
                  onChange("");
                  setOpen(false);
                }}
              >
                All Teams
              </CommandItem>
              {teams.map((t) => (
                <CommandItem
                  key={t.abbrev}
                  onSelect={() => {
                    onChange(t.abbrev);
                    setOpen(false);
                  }}
                >
                  <img src={logoUrl(t.abbrev)} alt="" className="h-4 w-4" />
                  {t.common_name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
