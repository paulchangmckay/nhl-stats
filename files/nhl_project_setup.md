# NHL Stats Database Project - Claude Project Setup

## Project Name
**NHL Stats Database & Analysis API**

---

## Custom Instructions for Claude

```
You are helping me build an NHL statistics database and API for data analysis. 

Key context:
- I'm building this to analyze hockey stats and game outcomes
- Target database: PostgreSQL
- Preferred backend: Python with FastAPI
- Focus on NHL data specifically
- Priority is getting a working prototype, then scaling

Guidelines for responses:
- Provide code examples in Python unless otherwise specified
- Use PostgreSQL syntax for database queries
- Keep explanations practical and actionable
- When suggesting architecture decisions, explain tradeoffs
- Assume I'm learning as I go - explain concepts when introducing them
- Focus on best practices but favor simplicity over perfection initially

Always remember:
- This is a personal/learning project (not enterprise-scale initially)
- I want to understand the "why" behind recommendations
- Cost-effectiveness matters - suggest free/cheap options first
```

---

## Project Knowledge Documents to Upload

### 1. Database Schema (create this as you design it)
**Filename:** `nhl_database_schema.sql`
- Tables: teams, players, games, game_stats, player_stats, seasons
- Relationships and foreign keys
- Indexes for performance

### 2. API Endpoints Documentation
**Filename:** `api_endpoints.md`
- List of planned endpoints
- Request/response formats
- Query parameters

### 3. Data Source Information
**Filename:** `data_sources.md`
- NHL API endpoints you're using
- Data update frequency
- Any API keys or authentication details (without sensitive credentials)

### 4. Technology Stack Decisions
**Filename:** `tech_stack.md`
- Chosen technologies and why
- Dependencies and versions
- Configuration notes

### 5. Project Roadmap
**Filename:** `roadmap.md`
- Phases and milestones
- Completed tasks
- Blockers and questions

---

## Suggested Project Structure

```
nhl-stats-project/
├── docs/
│   ├── database_schema.sql
│   ├── api_endpoints.md
│   ├── data_sources.md
│   └── tech_stack.md
├── src/
│   ├── api/
│   │   └── main.py (FastAPI app)
│   ├── database/
│   │   └── models.py
│   ├── data_ingestion/
│   │   └── nhl_fetcher.py
│   └── analysis/
│       └── stats_analyzer.py
├── tests/
├── requirements.txt
└── README.md
```

---

## Initial Questions to Document in Project

1. **Analysis Goals**: What specific insights are you looking to get?
   - Team performance trends?
   - Player statistics comparisons?
   - Game outcome predictions?
   - Historical analysis?

2. **Data Scope**: 
   - How many seasons of data?
   - Real-time updates or historical only?
   - Which stats are most important?

3. **Usage**: 
   - Personal dashboard?
   - API for other applications?
   - Data science experiments?

4. **Scale**:
   - Just NHL or other leagues later?
   - How many queries per day?

---

## Quick Start Checklist

- [ ] Create Claude Project named "NHL Stats Database"
- [ ] Add custom instructions (from above)
- [ ] Start documenting decisions in knowledge files
- [ ] Create GitHub repository for code
- [ ] Set up local PostgreSQL database
- [ ] Choose and test NHL data source API
- [ ] Design initial database schema
- [ ] Build first API endpoint
- [ ] Create data ingestion script
- [ ] Deploy to cloud platform

---

## Useful Resources to Reference

**NHL Data:**
- Unofficial NHL API: https://gitlab.com/dword4/nhlapi
- NHL Stats API documentation

**Technical:**
- FastAPI docs: https://fastapi.tiangolo.com
- PostgreSQL docs: https://www.postgresql.org/docs/
- SQLAlchemy (Python ORM): https://www.sqlalchemy.org

**Analysis:**
- Pandas documentation: https://pandas.pydata.org
- Hockey analytics communities and blogs for inspiration

---

## Tips for Using This Project

1. **Start each session** by sharing what you worked on since last time
2. **Upload new files** (schemas, code snippets) as you create them
3. **Update roadmap** regularly to track progress
4. **Ask specific questions** - Claude will remember your tech stack and goals
5. **Save code examples** Claude provides into your knowledge base

---

## Sample First Messages for New Chats

"I'm ready to work on [specific task]. Here's where I left off..."

"I hit a blocker with [problem]. Can you help troubleshoot?"

"Let's design the database schema for [specific feature]"

"Review this code I wrote for [component]" (then paste code)

