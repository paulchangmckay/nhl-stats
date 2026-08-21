import type { RankedPlayer } from "@/lib/leaderboards";

interface LeaderboardProps {
  title: string;
  players: RankedPlayer[];
  onSelectPlayer: (playerId: number) => void;
}

export function Leaderboard({ title, players, onSelectPlayer }: LeaderboardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {players.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">No qualifying players.</p>
      ) : (
        <ol className="flex flex-col gap-1">
          {players.map((p, i) => (
            <li key={p.player_id}>
              <button
                type="button"
                onClick={() => onSelectPlayer(p.player_id)}
                className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
              >
                <span>
                  <span className="mr-2 text-muted-foreground">{i + 1}.</span>
                  {p.name}
                  <span className="ml-2 text-muted-foreground">{p.team_abbrev}</span>
                </span>
                <span className="font-mono text-muted-foreground">{p.score.toFixed(2)}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
