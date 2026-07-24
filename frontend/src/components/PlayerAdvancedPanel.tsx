import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { PlayerAdvancedStats } from "@/lib/types";

const STRENGTH_STATES = ["5v5", "5v4", "4v5"] as const;

type FetchState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: PlayerAdvancedStats };

interface PercentileBoxProps {
  label: string;
  value: number | null;
  pctile: number | null;
}

function PercentileBox({ label, value, pctile }: PercentileBoxProps) {
  const color =
    pctile === null ? "bg-muted" : pctile >= 50 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <div className={`rounded-lg p-3 text-center ${color}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">
        {pctile === null ? "-" : Math.round(pctile)}
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {value === null ? "-" : `${value}%`}
      </div>
    </div>
  );
}

interface PlayerAdvancedPanelProps {
  open: boolean;
  playerId: number;
  playerName: string;
  onOpenChange: (open: boolean) => void;
}

export function PlayerAdvancedPanel({
  open,
  playerId,
  playerName,
  onOpenChange,
}: PlayerAdvancedPanelProps) {
  const [state, setState] = useState<FetchState>({ status: "loading" });
  const [strengthState, setStrengthState] = useState<(typeof STRENGTH_STATES)[number]>("5v5");

  useEffect(() => {
    if (!open) return;
    setState({ status: "loading" });
    fetch(`/api/players/${playerId}/advanced`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json();
      })
      .then((data: PlayerAdvancedStats) => setState({ status: "ready", data }))
      .catch((err: Error) => setState({ status: "error", message: err.message }));
  }, [open, playerId]);

  const current = state.status === "ready" ? state.data.strength_states[strengthState] : undefined;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{playerName}</DialogTitle>
        </DialogHeader>

        {state.status === "loading" && <div className="p-4 text-sm">Loading...</div>}
        {state.status === "error" && (
          <div className="p-4 text-sm text-destructive">{state.message}</div>
        )}

        {state.status === "ready" && (
          <div className="flex flex-col gap-4">
            <div className="flex gap-2">
              {STRENGTH_STATES.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant={strengthState === s ? "default" : "outline"}
                  onClick={() => setStrengthState(s)}
                >
                  {s}
                </Button>
              ))}
            </div>

            <div className="grid grid-cols-5 gap-2">
              <PercentileBox label="CF%" value={current?.cf_pct ?? null} pctile={current?.cf_pctile ?? null} />
              <PercentileBox label="FF%" value={current?.ff_pct ?? null} pctile={current?.ff_pctile ?? null} />
              <PercentileBox label="HDCF%" value={current?.hdcf_pct ?? null} pctile={current?.hdcf_pctile ?? null} />
              <PercentileBox
                label="Primary Pts"
                value={current?.primary_points ?? null}
                pctile={current?.primary_points_pctile ?? null}
              />
              <div className="rounded-lg bg-muted p-3 text-center">
                <div className="text-xs text-muted-foreground">PDO</div>
                <div className="text-2xl font-semibold tabular-nums">
                  {state.data.pdo === null ? "-" : state.data.pdo}
                </div>
              </div>
            </div>

            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={state.data.trend}>
                  <XAxis dataKey="season_id" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="cf_pct" stroke="var(--color-sky-500)" dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
