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
import { User } from "lucide-react";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Player, PlayerStats, PlayerAdvancedStats } from "@/lib/types";

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

interface ZScoreBoxProps {
  label: string;
  rate: number | null | undefined;
  z: number | null | undefined;
  nullReason: string;
  tooltip?: string;
}

function ZScoreBox({ label, rate, z, nullReason, tooltip }: ZScoreBoxProps) {
  if (z === null || z === undefined) {
    return (
      <div className="rounded-lg bg-muted p-3 text-center opacity-60" title={nullReason}>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">N/A</div>
      </div>
    );
  }
  const color = z >= 0 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <div className={`rounded-lg p-3 text-center ${color}`} title={tooltip}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{z.toFixed(2)}</div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {rate == null ? "-" : rate.toFixed(2)}
      </div>
    </div>
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

  const isGoalie = (bio?.position_code ?? stats?.position_code) === "G";

  useEffect(() => {
    setPhotoFailed(false);
    setLogoFailed(false);
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

                <div className="grid grid-cols-3 gap-2">
                  <ZScoreBox label="Shots/60"
                    rate={state.data.strength_states["5v5"]?.shots_per60}
                    z={state.data.strength_states["5v5"]?.shots_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Chances/60"
                    rate={state.data.strength_states["5v5"]?.chances_per60}
                    z={state.data.strength_states["5v5"]?.chances_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Rebounds Created/60"
                    rate={state.data.strength_states["5v5"]?.rebounds_created_per60}
                    z={state.data.strength_states["5v5"]?.rebounds_created_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season"
                    tooltip="Heuristic: a shot attempt within 3 seconds of this player's own shot attempt, same team. Not possession-confirmed." />
                  <ZScoreBox label="Deflections/60"
                    rate={state.data.strength_states["5v5"]?.deflections_per60}
                    z={state.data.strength_states["5v5"]?.deflections_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Points/60"
                    rate={state.data.strength_states["5v5"]?.points_per60}
                    z={state.data.strength_states["5v5"]?.points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Primary Points/60"
                    rate={state.data.strength_states["5v5"]?.primary_points_per60}
                    z={state.data.strength_states["5v5"]?.primary_points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
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
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
