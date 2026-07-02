# NHL Stats Database - Project Roadmap

## Project Goal
Build an NHL statistics database with API access for custom analysis of team performance, player stats, and game outcomes.

---

## Phase 1: Foundation (Week 1-2)
**Goal:** Get basic infrastructure working locally

### Tasks
- [ ] **Research & Planning**
  - [ ] Choose data source (NHL API vs SportRadar vs other)
  - [ ] Define key analysis questions
  - [ ] List must-have vs nice-to-have features
  
- [ ] **Local Setup**
  - [ ] Install PostgreSQL locally
  - [ ] Set up Python virtual environment
  - [ ] Install core dependencies (FastAPI, psycopg2, requests, pandas)
  
- [ ] **Database Design**
  - [ ] Design schema (teams, players, games, stats tables)
  - [ ] Create initial migration script
  - [ ] Load sample data for testing

- [ ] **Data Ingestion**
  - [ ] Build script to fetch data from NHL API
  - [ ] Transform and load into database
  - [ ] Test with one season of data

**Milestone:** Can successfully fetch NHL data and store it locally

---

## Phase 2: API Development (Week 2-3)
**Goal:** Build working API endpoints

### Tasks
- [ ] **Basic API Setup**
  - [ ] Initialize FastAPI project structure
  - [ ] Connect to database
  - [ ] Implement health check endpoint
  
- [ ] **Core Endpoints**
  - [ ] GET /teams - List all teams
  - [ ] GET /teams/{id}/games - Get team's games
  - [ ] GET /players/{id}/stats - Get player statistics
  - [ ] GET /games - Query games with filters (date, team, season)
  
- [ ] **Testing**
  - [ ] Write basic tests for endpoints
  - [ ] Test query performance with larger datasets
  - [ ] Document API endpoints

**Milestone:** Can query database through API endpoints locally

---

## Phase 3: Analysis Features (Week 3-4)
**Goal:** Add analytical capabilities

### Tasks
- [ ] **Statistical Analysis**
  - [ ] Team performance trends over season
  - [ ] Player performance comparisons
  - [ ] Home vs away statistics
  
- [ ] **Advanced Queries**
  - [ ] Aggregations (averages, totals by team/player)
  - [ ] Time-series analysis
  - [ ] Custom filters and sorting
  
- [ ] **Data Visualization** (optional)
  - [ ] API endpoints returning chart-ready data
  - [ ] Simple dashboard (if desired)

**Milestone:** Can answer meaningful analytical questions through API

---

## Phase 4: Deployment (Week 4-5)
**Goal:** Move to production environment

### Tasks
- [ ] **Cloud Infrastructure**
  - [ ] Set up database on Supabase/Railway
  - [ ] Deploy API to Render/Railway
  - [ ] Configure environment variables
  
- [ ] **Automation**
  - [ ] Schedule daily data updates (cron job)
  - [ ] Set up error notifications
  - [ ] Create backup strategy
  
- [ ] **Documentation**
  - [ ] API documentation (Swagger/OpenAPI)
  - [ ] Setup instructions
  - [ ] Usage examples

**Milestone:** Live API accessible from anywhere

---

## Phase 5: Enhancement (Ongoing)
**Goal:** Improve and expand functionality

### Future Ideas
- [ ] Add more advanced statistics (Corsi, Fenwick, xG)
- [ ] Predictive modeling features
- [ ] Support for historical seasons (pre-2020)
- [ ] Player comparison tools
- [ ] Export capabilities (CSV, JSON)
- [ ] Rate limiting and authentication
- [ ] Caching for frequently accessed data

---

## Current Status

**Phase:** [Planning / Phase 1 / etc.]

**Last Updated:** [Date]

**Recent Progress:**
- [What you accomplished recently]

**Next Steps:**
- [Immediate next tasks]

**Blockers:**
- [Any issues preventing progress]

---

## Decision Log

### [Date] - Data Source Selection
**Decision:** [Chosen option]
**Reasoning:** [Why]

### [Date] - Database Host Choice
**Decision:** [Chosen platform]
**Reasoning:** [Why]

### [Date] - [Other Major Decision]
**Decision:** [What you decided]
**Reasoning:** [Why]

---

## Questions to Resolve

1. [Open question 1]
2. [Open question 2]

---

## Resources & References

- [Links to helpful tutorials, docs, examples]
- [Community resources or forums]
- [Hockey analytics blogs for inspiration]
