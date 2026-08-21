import { buildHeroGradient } from "@/lib/heroGradient";

export default function Home() {
  return (
    <div>
      <section
        data-testid="hero"
        className="flex flex-col items-center justify-center gap-3 px-4 py-24 text-center text-white"
        style={{ backgroundImage: buildHeroGradient() }}
      >
        <h1 className="text-4xl font-bold sm:text-5xl">Dig Into Every Player's Numbers</h1>
        <p className="max-w-xl text-base text-white/90 sm:text-lg">
          Deep player and team analytics for every skater and goalie in the league.
        </p>
      </section>
      {/* News feed (#118) renders here inline once built — Home has no separate /news route. */}
      <p className="px-4 py-12 text-center text-sm text-muted-foreground">
        League news coming soon.
      </p>
    </div>
  );
}
