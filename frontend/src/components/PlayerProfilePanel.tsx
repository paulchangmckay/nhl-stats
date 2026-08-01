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
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { User } from "lucide-react";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Player, PlayerStats, PlayerAdvancedStats } from "@/lib/types";
import { METRIC_DEFINITIONS, type MetricKey } from "@/lib/metricDefinitions";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";

const STRENGTH_STATES = ["5v5", "5v4", "4v5"] as const;

const LINE_COLORS = [
  "var(--color-sky-500)", "var(--color-amber-500)", "var(--color-emerald-500)",
  "var(--color-rose-500)", "var(--color-violet-500)", "var(--color-cyan-500)",
];

type FetchState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: PlayerAdvancedStats };

interface PercentileBoxProps {
  metricKey: MetricKey;
  label: string;
  value: number | null;
  pctile: number | null;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
}

function PercentileBox({ metricKey, label, value, pctile, selected, onToggle }: PercentileBoxProps) {
  const color =
    pctile === null ? "bg-muted" : pctile >= 50 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle} colorClass={color}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">
        {pctile === null ? "-" : Math.round(pctile)}
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {value === null ? "-" : `${value}%`}
      </div>
    </SelectableStatBox>
  );
}

interface ZScoreBoxProps {
  metricKey: MetricKey;
  label: string;
  rate: number | null | undefined;
  z: number | null | undefined;
  nullReason: string;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
}

function ZScoreBox({ metricKey, label, rate, z, nullReason, selected, onToggle }: ZScoreBoxProps) {
  if (z === null || z === undefined) {
    return (
      <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle}
        colorClass="bg-muted opacity-60" extraNote={nullReason}>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">N/A</div>
      </SelectableStatBox>
    );
  }
  const color = z >= 0 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle} colorClass={color}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{z.toFixed(2)}</div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {rate == null ? "-" : rate.toFixed(2)}
      </div>
    </SelectableStatBox>
  );
}

interface SelectableStatBoxProps {
  metricKey: MetricKey;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
  colorClass: string;
  extraNote?: string;
  children: React.ReactNode;
}

function SelectableStatBox({ metricKey, selected, onToggle, colorClass, extraNote, children }: SelectableStatBoxProps) {
  const def = METRIC_DEFINITIONS[metricKey];
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div
            role="button"
            tabIndex={0}
            aria-pressed={selected}
            aria-label={def.label}
            onClick={() => onToggle(metricKey)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onToggle(metricKey);
              }
            }}
            className={`rounded-lg p-3 text-center cursor-pointer ${colorClass} ${selected ? "ring-2 ring-sky-400" : ""}`}
          />
        }
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>
        <div className="font-medium">{def.name}</div>
        <div>{def.description}</div>
        <div className="text-muted-foreground">{def.formula}</div>
        {extraNote && <div className="text-muted-foreground italic">{extraNote}</div>}
      </TooltipContent>
    </Tooltip>
  );
}

interface StatCellProps {
  label: string;
  value: string;
}

function StatCell({ label, value }: StatCellProps) {
  return (
    <div>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="tabular-nums">{value}</div>
    </div>
  );
}

function computeAge(birthDate: string): number | null {
  if (!birthDate) return null;
  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const notYetHadBirthdayThisYear =
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (notYetHadBirthdayThisYear) age -= 1;
  return age;
}

function draftLabel(bio: Player | undefined): string {
  if (!bio || bio.draft_year === null) return "Undrafted";
  const team = bio.draft_team_abbrev ? `, ${bio.draft_team_abbrev}` : "";
  return `Rd ${bio.draft_round}, Pick ${bio.draft_pick} (${bio.draft_year}${team})`;
}

function birthplaceLabel(bio: Player | undefined): string {
  if (!bio) return "";
  return [bio.birth_city, bio.birth_state_province, bio.birth_country].filter(Boolean).join(", ");
}

function formatSavePct(val: number | null): string {
  return val === null ? "-" : val.toFixed(3);
}

function formatGaa(val: number | null): string {
  return val === null ? "-" : val.toFixed(2);
}

function formatPlusMinus(val: number | null): string {
  if (val === null) return "-";
  return val > 0 ? `+${val}` : String(val);
}

interface PlayerProfilePanelProps {
  open: boolean;
  playerId: number;
  bio: Player | undefined;
  stats: PlayerStats | undefined;
  onOpenChange: (open: boolean) => void;
}

export function PlayerProfilePanel({
  open,
  playerId,
  bio,
  stats,
  onOpenChange,
}: PlayerProfilePanelProps) {
  const [state, setState] = useState<FetchState>({ status: "loading" });
  const [strengthState, setStrengthState] = useState<(typeof STRENGTH_STATES)[number]>("5v5");
  const [photoFailed, setPhotoFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const [selectedMetrics, setSelectedMetrics] = useState<Set<MetricKey>>(() => new Set(["cf_pct"]));

  function toggleMetric(key: MetricKey) {
    setSelectedMetrics((prev) => {
      const first = prev.values().next().value as MetricKey | undefined;
      const currentFamily = first ? METRIC_DEFINITIONS[first].family : null;
      const newFamily = METRIC_DEFINITIONS[key].family;
      if (currentFamily !== null && currentFamily !== newFamily) {
        return new Set([key]);
      }
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  const isGoalie = (bio?.position_code ?? stats?.position_code) === "G";

  useEffect(() => {
    setPhotoFailed(false);
    setLogoFailed(false);
    setSelectedMetrics(new Set(["cf_pct"]));
  }, [playerId]);

  useEffect(() => {
    if (!open || isGoalie) return;
    setState({ status: "loading" });
    fetch(`/api/players/${playerId}/advanced`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json();
      })
      .then((data: PlayerAdvancedStats) => setState({ status: "ready", data }))
      .catch((err: Error) => setState({ status: "error", message: err.message }));
  }, [open, playerId, isGoalie]);

  const current = state.status === "ready" ? state.data.strength_states[strengthState] : undefined;
  const primaryMetricKey = selectedMetrics.values().next().value as MetricKey;
  const graphStrengthState = METRIC_DEFINITIONS[primaryMetricKey].strengthAware ? strengthState : "5v5";
  const chartData = state.status === "ready"
    ? state.data.trend.filter((row) => row.strength_state === graphStrengthState)
    : [];
  const playerName = stats
    ? `${stats.first_name} ${stats.last_name}`
    : bio
      ? `${bio.first_name} ${bio.last_name}`
      : "";
  const teamAbbrev = bio?.team_abbrev ?? stats?.team_abbrev ?? "";
  const positionCode = bio?.position_code ?? stats?.position_code ?? "";
  const colors = teamColors(teamAbbrev);
  const age = bio ? computeAge(bio.birth_date) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader
          className="pl-3"
          style={colors ? { borderLeft: `4px solid ${colors.primary}` } : undefined}
        >
          <div className="flex items-center gap-4">
            {bio?.headshot_url && !photoFailed ? (
              <img
                src={bio.headshot_url}
                alt={playerName}
                className="h-16 w-16 rounded-full object-cover bg-muted"
                onError={() => setPhotoFailed(true)}
              />
            ) : (
              <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                <User className="h-8 w-8 text-muted-foreground" aria-hidden />
              </div>
            )}
            <div className="flex-1">
              <DialogTitle className="flex items-center gap-2">
                {playerName}
                {bio?.sweater_number != null && (
                  <span className="text-muted-foreground font-normal">#{bio.sweater_number}</span>
                )}
              </DialogTitle>
              <div className="text-sm text-muted-foreground">
                {positionCode}
                {teamAbbrev ? ` · ${teamAbbrev}` : ""}
              </div>
            </div>
            {teamAbbrev && colors && !logoFailed && (
              <img
                src={logoUrl(teamAbbrev)}
                alt={`${teamAbbrev} logo`}
                className="h-10 w-10"
                onError={() => setLogoFailed(true)}
              />
            )}
          </div>
        </DialogHeader>

        {bio && (
          <div className="text-sm text-muted-foreground">
            <div>
              {age !== null ? `${age} yrs` : ""}
              {bio.height ? ` · ${bio.height}` : ""}
              {bio.weight_pounds != null ? ` · ${bio.weight_pounds} lb` : ""}
              {bio.shoots_catches ? ` · Shoots: ${bio.shoots_catches}` : ""}
            </div>
            <div>{birthplaceLabel(bio)}</div>
            <div>Drafted: {draftLabel(bio)}</div>
          </div>
        )}

        {stats &&
          (isGoalie ? (
            <div className="grid grid-cols-4 gap-2 text-center text-sm">
              <StatCell label="GP" value={stats.gp?.toString() ?? "-"} />
              <StatCell label="W" value={stats.wins?.toString() ?? "-"} />
              <StatCell label="L" value={stats.losses?.toString() ?? "-"} />
              <StatCell label="OTL" value={stats.ot_losses?.toString() ?? "-"} />
              <StatCell label="SV%" value={formatSavePct(stats.save_pct)} />
              <StatCell label="GAA" value={formatGaa(stats.gaa)} />
              <StatCell label="SO" value={stats.shutouts?.toString() ?? "-"} />
            </div>
          ) : (
            <div className="grid grid-cols-6 gap-2 text-center text-sm">
              <StatCell label="GP" value={stats.gp?.toString() ?? "-"} />
              <StatCell label="G" value={stats.goals?.toString() ?? "-"} />
              <StatCell label="A" value={stats.assists?.toString() ?? "-"} />
              <StatCell label="P" value={stats.points?.toString() ?? "-"} />
              <StatCell label="+/-" value={formatPlusMinus(stats.plus_minus)} />
              <StatCell label="PIM" value={stats.pim?.toString() ?? "-"} />
            </div>
          ))}

        {!isGoalie && (
          <>
            {state.status === "loading" && (
              <div className="p-4 text-sm">Loading advanced stats...</div>
            )}
            {state.status === "error" && (
              <div className="p-4 text-sm text-destructive">{state.message}</div>
            )}

            {state.status === "ready" && (
              <TooltipProvider delay={300}>
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
                  <PercentileBox metricKey="cf_pct" selected={selectedMetrics.has("cf_pct")} onToggle={toggleMetric}
                    label="CF%" value={current?.cf_pct ?? null} pctile={current?.cf_pctile ?? null} />
                  <PercentileBox metricKey="ff_pct" selected={selectedMetrics.has("ff_pct")} onToggle={toggleMetric}
                    label="FF%" value={current?.ff_pct ?? null} pctile={current?.ff_pctile ?? null} />
                  <PercentileBox metricKey="hdcf_pct" selected={selectedMetrics.has("hdcf_pct")} onToggle={toggleMetric}
                    label="HDCF%" value={current?.hdcf_pct ?? null} pctile={current?.hdcf_pctile ?? null} />
                  <PercentileBox metricKey="primary_points" selected={selectedMetrics.has("primary_points")} onToggle={toggleMetric}
                    label="Primary Pts" value={current?.primary_points ?? null} pctile={current?.primary_points_pctile ?? null} />
                  <SelectableStatBox metricKey="pdo" selected={selectedMetrics.has("pdo")} onToggle={toggleMetric} colorClass="bg-muted">
                    <div className="text-xs text-muted-foreground">PDO</div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {state.data.pdo === null ? "-" : state.data.pdo}
                    </div>
                  </SelectableStatBox>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <ZScoreBox metricKey="shots_per60" selected={selectedMetrics.has("shots_per60")} onToggle={toggleMetric}
                    label="Shots/60"
                    rate={state.data.strength_states["5v5"]?.shots_per60}
                    z={state.data.strength_states["5v5"]?.shots_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="chances_per60" selected={selectedMetrics.has("chances_per60")} onToggle={toggleMetric}
                    label="Chances/60"
                    rate={state.data.strength_states["5v5"]?.chances_per60}
                    z={state.data.strength_states["5v5"]?.chances_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="rebounds_created_per60" selected={selectedMetrics.has("rebounds_created_per60")} onToggle={toggleMetric}
                    label="Rebounds Created/60"
                    rate={state.data.strength_states["5v5"]?.rebounds_created_per60}
                    z={state.data.strength_states["5v5"]?.rebounds_created_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="deflections_per60" selected={selectedMetrics.has("deflections_per60")} onToggle={toggleMetric}
                    label="Deflections/60"
                    rate={state.data.strength_states["5v5"]?.deflections_per60}
                    z={state.data.strength_states["5v5"]?.deflections_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="points_per60" selected={selectedMetrics.has("points_per60")} onToggle={toggleMetric}
                    label="Points/60"
                    rate={state.data.strength_states["5v5"]?.points_per60}
                    z={state.data.strength_states["5v5"]?.points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="primary_points_per60" selected={selectedMetrics.has("primary_points_per60")} onToggle={toggleMetric}
                    label="Primary Points/60"
                    rate={state.data.strength_states["5v5"]?.primary_points_per60}
                    z={state.data.strength_states["5v5"]?.primary_points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                </div>

                <div className="flex flex-col gap-1">
                  <div className="flex gap-3 text-xs text-muted-foreground">
                    {Array.from(selectedMetrics).map((key, i) => (
                      <span key={key} className="flex items-center gap-1">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: LINE_COLORS[i % LINE_COLORS.length] }}
                        />
                        {METRIC_DEFINITIONS[key].label}
                      </span>
                    ))}
                  </div>
                  <div className="h-40 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <XAxis dataKey="season_id" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <RechartsTooltip />
                        {Array.from(selectedMetrics).map((key, i) => (
                          <Line key={key} type="monotone" dataKey={key} stroke={LINE_COLORS[i % LINE_COLORS.length]} dot />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
              </TooltipProvider>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
