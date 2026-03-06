# NHL Data Sources

## Primary Data Source

**Status:** [To be decided]

### Option 1: Unofficial NHL API
- **URL:** https://statsapi.web.nhl.com/api/v1/
- **Cost:** Free
- **Documentation:** https://gitlab.com/dword4/nhlapi
- **Pros:** Free, comprehensive, real-time data
- **Cons:** Unofficial, could change without notice, rate limits unknown
- **Data Available:** 
  - Game schedules and scores
  - Player stats
  - Team information
  - Live game feeds
  - Historical data back to 1917

### Option 2: SportRadar NHL API
- **URL:** https://developer.sportradar.com/
- **Cost:** Starts at $150/month (trial available)
- **Pros:** Official, reliable, guaranteed uptime, support
- **Cons:** Expensive for personal project
- **Data Available:** Similar to NHL API plus additional analytics

### Option 3: API-Hockey (RapidAPI)
- **URL:** https://rapidapi.com/api-sports/api/api-hockey
- **Cost:** Free tier: 100 requests/day, Paid: $10-50/month
- **Pros:** Structured API, multiple leagues
- **Cons:** Rate limits on free tier

---

## Decision: [YOUR CHOICE HERE]

**Reasoning:**

---

## Key Endpoints (update based on chosen source)

### Games
```
GET /api/v1/schedule?season=20232024
GET /api/v1/game/{gameId}/feed/live
```

### Teams
```
GET /api/v1/teams
GET /api/v1/teams/{teamId}
GET /api/v1/teams/{teamId}/roster
```

### Players
```
GET /api/v1/people/{playerId}
GET /api/v1/people/{playerId}/stats?stats=statsSingleSeason&season=20232024
```

### Standings
```
GET /api/v1/standings?season=20232024
```

---

## Data Update Strategy

**Frequency:** [Daily / Hourly / Real-time]

**Method:** [Cron job / Manual / Event-driven]

**Historical Data Load:**
- Seasons: [e.g., 2020-2024]
- Initial load approach: [Bulk import / Incremental]

---

## Authentication & Rate Limits

**API Key Required:** [Yes/No]

**Rate Limits:** [Document here]

**Error Handling Strategy:** [How to handle rate limit errors]

---

## Notes & Observations

[Add any findings, issues, or important notes about the data source here]
