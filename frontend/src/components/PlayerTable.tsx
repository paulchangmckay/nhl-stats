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
];

function cellValue(col: Column, row: PlayerStats): string {
  const val = (row as unknown as Record<string, unknown>)[col.key];
  if (val === null || val === undefined) return "-";
  if (col.key === "save_pct") return Number(val).toFixed(3);
  if (col.key === "gaa") return Number(val).toFixed(2);
  if (col.key === "shooting_pct") return `${val}%`;
  if (col.key === "plus_minus") return Number(val) > 0 ? `+${val}` : String(val);
  return String(val);
}

interface PlayerTableProps {
  rows: PlayerStats[];
  sortKey: string;
  sortDir: SortDirection;
  onSort: (key: string) => void;
}

export function PlayerTable({ rows, sortKey, sortDir, onSort }: PlayerTableProps) {
  if (rows.length === 0) {
    return <div className="p-12 text-center text-sm text-muted-foreground">No players found.</div>;
  }

  const hasGoalie = rows.some((r) => r.position_code === "G");
  const columns = COLUMNS.filter((c) => {
    if (c.goalieOnly) return hasGoalie;
    return true;
  });

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
        {rows.map((row) => (
          <TableRow key={row.player_id} data-player-id={row.player_id}>
            {columns.map((col) => (
              <TableCell key={col.key} className={col.numeric ? "text-right tabular-nums" : ""}>
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
        ))}
      </TableBody>
    </Table>
  );
}
