import { forwardRef, useImperativeHandle } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { PlayerStats, SortDirection } from "@/lib/types";

const ROW_HEIGHT_PX = 38;

interface Column {
  key: string;
  label: string;
  numeric?: boolean;
  goalieOnly?: boolean;
  skaterOnly?: boolean;
}

const COLUMNS: Column[] = [
  { key: "last_name", label: "Last Name" },
  { key: "first_name", label: "First Name" },
  { key: "position_code", label: "Pos" },
  { key: "team_abbrev", label: "Team" },
  { key: "gp", label: "GP", numeric: true },
  { key: "goals", label: "G", numeric: true, skaterOnly: true },
  { key: "assists", label: "A", numeric: true, skaterOnly: true },
  { key: "points", label: "Pts", numeric: true, skaterOnly: true },
  { key: "plus_minus", label: "+/-", numeric: true, skaterOnly: true },
  { key: "pim", label: "PIM", numeric: true },
  { key: "shooting_pct", label: "SH%", numeric: true, skaterOnly: true },
  { key: "avg_toi", label: "Avg TOI", skaterOnly: true },
  { key: "wins", label: "W", numeric: true, goalieOnly: true },
  { key: "losses", label: "L", numeric: true, goalieOnly: true },
  { key: "save_pct", label: "SV%", numeric: true, goalieOnly: true },
  { key: "gaa", label: "GAA", numeric: true, goalieOnly: true },
  { key: "cf_pct_5v5", label: "CF% (5v5)", numeric: true, skaterOnly: true },
  { key: "shots_per60_5v5", label: "Shots/60 (5v5)", numeric: true, skaterOnly: true },
];

function cellValue(col: Column, row: PlayerStats): string {
  const val = (row as unknown as Record<string, unknown>)[col.key];
  if (val === null || val === undefined) return "-";
  if (col.key === "save_pct") return Number(val).toFixed(3);
  if (col.key === "gaa") return Number(val).toFixed(2);
  if (col.key === "shooting_pct") return `${val}%`;
  if (col.key === "cf_pct_5v5") return `${val}%`;
  if (col.key === "shots_per60_5v5") return Number(val).toFixed(2);
  if (col.key === "plus_minus") return Number(val) > 0 ? `+${val}` : String(val);
  return String(val);
}

export interface PlayerTableHandle {
  scrollToPlayer(playerId: number): void;
}

interface PlayerTableProps {
  rows: PlayerStats[];
  sortKey: string;
  sortDir: SortDirection;
  onSort: (key: string) => void;
  onOpenProfile?: (playerId: number) => void;
  scrollContainerRef?: React.RefObject<HTMLDivElement>;
}

export const PlayerTable = forwardRef<PlayerTableHandle, PlayerTableProps>(function PlayerTable(
  { rows, sortKey, sortDir, onSort, onOpenProfile, scrollContainerRef },
  ref
) {
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollContainerRef?.current ?? null,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 10,
  });

  useImperativeHandle(
    ref,
    () => ({
      scrollToPlayer(playerId: number) {
        const index = rows.findIndex((r) => r.player_id === playerId);
        if (index === -1) return;
        virtualizer.scrollToIndex(index, { align: "center", behavior: "auto" });
        requestAnimationFrame(() => {
          const el = document.querySelector(`[data-player-id="${playerId}"]`);
          if (!el) return;
          el.classList.add("row-highlight");
          setTimeout(() => el.classList.remove("row-highlight"), 1500);
        });
      },
    }),
    [rows, virtualizer]
  );

  if (rows.length === 0) {
    return <div className="p-12 text-center text-sm text-muted-foreground">No players found.</div>;
  }

  const hasGoalie = rows.some((r) => r.position_code === "G");
  const columns = COLUMNS.filter((c) => {
    if (c.goalieOnly) return hasGoalie;
    return true;
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const renderedHeight = virtualItems.length * ROW_HEIGHT_PX;
  const spacerHeight = totalSize - renderedHeight;

  return (
    <Table>
      <TableHeader className="sticky top-0 bg-card">
        <TableRow>
          {columns.map((col) => (
            <TableHead
              key={col.key}
              onClick={() => onSort(col.key)}
              className="cursor-pointer select-none"
            >
              {col.label}
              {sortKey === col.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {virtualItems.map((virtualItem, i) => {
          const row = rows[virtualItem.index];
          return (
            <TableRow
              key={row.player_id}
              data-player-id={row.player_id}
              style={{ transform: `translateY(${virtualItem.start - i * ROW_HEIGHT_PX}px)` }}
              tabIndex={onOpenProfile ? 0 : undefined}
              role={onOpenProfile ? "button" : undefined}
              onClick={onOpenProfile ? () => onOpenProfile(row.player_id) : undefined}
              onKeyDown={
                onOpenProfile
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onOpenProfile(row.player_id);
                      }
                    }
                  : undefined
              }
              className={onOpenProfile ? "cursor-pointer hover:bg-muted/50" : undefined}
            >
              {columns.map((col) => (
                <TableCell
                  key={col.key}
                  className={col.numeric ? "text-right tabular-nums" : ""}
                >
                  {col.key === "position_code" ? (
                    <Badge variant="outline">{row.position_code}</Badge>
                  ) : col.skaterOnly && row.position_code === "G" ? (
                    "-"
                  ) : (
                    cellValue(col, row)
                  )}
                </TableCell>
              ))}
            </TableRow>
          );
        })}
        {spacerHeight > 0 && (
          <tr aria-hidden="true">
            <td colSpan={columns.length} style={{ height: spacerHeight, padding: 0, border: "none" }} />
          </tr>
        )}
      </TableBody>
    </Table>
  );
});
