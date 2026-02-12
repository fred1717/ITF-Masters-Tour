# ITF Masters Tour — Senior Tournament Management System

## 1. Project Overview

This is a fantasy tennis project that replicates the organisation of the ITF (International Tennis Federation) Masters Tour, limited to 2 age categories (60+ and 65+), men and women, singles only. 

All player names are entirely fictitious; any resemblance to real individuals is purely coincidental.

The system handles the full tournament lifecycle: 
- player registration
- entry deadline enforcement
- automated draw generation with seeding and bye assignment
- match skeleton creation
- live result entry with score validation
- points calculation
- weekly ranking publication
- player suspension tracking.

The project serves as a portfolio demonstration of full-stack development, relational database design, and cloud architecture. 

The local application is a Flask web app backed by PostgreSQL (Docker), with a planned short-lived AWS deployment for disaster recovery evidence collection.

All business logic is governed by three sources of truth: 
- `Rules.md` (ITF tournament rules)
- `create_itf_schema.sql` (database schema with CHECK constraints)
- `repository_structure.md` (canonical file layout). 

Every Python script implements the rules defined in these files.


## 2. Architecture

### 2.1 Local Stack

```
Browser → Flask (`app.py`, 20 routes) → Service Layer → PostgreSQL 16 (Docker)
```

The Flask application runs locally via `run_local.sh`. 
It connects to a PostgreSQL 16 instance running in a Docker container (`itf-postgres`). 
The service layer  encapsulates all business logic, keeping Flask routes thin.

It includes the following modules:
- `entry_service.py`
- `draw_service.py`
- `match_service.py`
- `view_service.py`


### 2.2 Planned AWS Deployment

```
Route53 (aws.cloudcase.com) → ALB → Fargate (Flask) → RDS PostgreSQL
```

The infrastructure spans two AWS regions for disaster recovery demonstration. 

Cross-region RDS replication with Route53 health-check failover proves data integrity survives a simulated primary region failure. 

The deployment will remain online for a maximum of 2 days — long enough to collect screenshot evidence — before teardown. 

Terraform manages all resources. 

Results are stored on GitHub and S3.


### 2.3 Development Tools

| Tool | Purpose |
|------|---------|
| PyCharm Professional | Python development, debugging, project navigation |
| DataGrip | SQL queries, database inspection, data verification |
| Docker Desktop | PostgreSQL container (`itf-postgres`) |
| WSL2 | Linux environment on Windows |
| Flask | Web application framework |
| psql | Command-line SQL execution for bulk imports |



## 3. Key Business Rules

The complete rule set is defined in `Rules.md`. Below is a summary of the most significant rules enforced by the system.

### 3.1 Age Eligibility

A player qualifies for an age category (60+ or 65+) if the required age is reached during the calendar year of the competition. 

Each ranking is category-specific: a player changing category starts with zero points in the new one.


### 3.2 Entry and Scheduling

The entry deadline is every Tuesday at 10:00 UTC for the tournament starting the following week. 

A minimum of 6 players per draw is required; the maximum is 64. 

Tournaments run Monday to Sunday.


### 3.3 Draw Generation and Seeding

Draw sizes are powers of 2 (8, 16, 32, 64). 

Byes fill the remaining positions: 
- seeded players receive byes first (in seed order)
- unseeded players receive byes randomly. 

Seeding is based on the weekly ranking published the Monday before the entry deadline.

Seeding brackets: 
- 6–8 players → 2 seeds; 
- 9–16 → 4 seeds; 
- 17–32 → 8 seeds; 
- 33–64 → 16 seeds. 

Seeds are placed so that the top 2 cannot meet before the final, seeds 3–4 not before the semi-finals, and so on. 

Tournaments 1 and 2 have no seeding (no ranking existed yet).


### 3.4 Scoring

Each set is won at 6 games with a 2-game margin, or via a tiebreak at 6–6 (first to 7 points, win by 2). 

If the match is split at one set each, a third set is played. 

The format of the third set depends on `Draws.has_supertiebreak`: 
- when `TRUE` (75% of draws), a super-tiebreak replaces the third set (first to 10 points, win by 2); 
- when `FALSE` (25%), a normal third set is played.


### 3.5 Points and Rankings

Points are allocated by tournament category and stage result (see `PointsRules`). 

First-match losers receive zero points regardless of the stage. 

The weekly ranking, published every Monday at 20:00 UTC, sums each player's best 4 results over the previous 52 weeks.


### 3.6 Suspensions
There are two types of suspensions:
- a no-show or post-draw withdrawal (`match_status_id = 3`) triggers a 2-month suspension. 
- a disqualification during a match (`match_status_id = 6`) triggers a 6-month suspension. 

In both cases, all points earned in that tournament are forfeited. 

A retirement (`match_status_id = 4`) carries no suspension and no point forfeiture — partial scores are preserved.


## 4. Data Pipeline

The database is populated in two phases, and the project uses two distinct workflows:
- **Tournaments 1–58 (script-generated):** All entries, draw players, matches, points, and rankings were produced by Python scripts enforcing the rules from `Rules.md`. 
    This bulk historical data establishes 54 weeks of realistic tournament history.
- **Tournament 59 (manually entered):** Entries, draws, and match results were entered via the Flask admin panel. 
    Scripts were only used for debugging and for updating match dates to align with the tournament 59 week. 
    This workflow demonstrates the live application as it would operate in production.
- **Tournament 60 onward (fully manual):** No generation scripts are needed. 
    Entries, draws, and results entered via the frontend automatically update all linked tables (`PointsHistory`, `WeeklyRanking`, `PlayerSuspensions`).

Prerequisite (reference) data was created manually; generated data was produced by scripts.

### 4.1 Prerequisite Data (15 tables — static reference)

These tables contain manually curated reference data: 
- `AgeCategory`
- `Country`
- `DrawStatus`
- `Gender`
- `Location`
- `MatchRounds`
- `MatchStatus`
- `Players`
- `PlayerStatus`
- `PointsRules`
- `SeedingRules`
- `StageResults`
- `Surfaces`
- `TournamentCategory`
- `Venue`
- `Tournaments`
- `Draws` for tournament_id 1–58.

Excel source files are in `data/extracts/prerequisites/`. 

SQL insert scripts are in `data/sql/prerequisites/`.


### 4.2 Generated Data (8 tables — computed by scripts)

These tables are populated by the generation and recalculation pipeline: 
- `Entries`
- `DrawPlayers`
- `DrawSeed`
- `Draws` (from tournament_id 59 onward)
- `Matches`
- `PlayerSuspensions`
- `PointsHistory`
- `WeeklyRanking`.

Excel exports are in `data/extracts/generated/`. 

SQL insert scripts are in `data/sql/generated/`.


### 4.3 Execution Order

From the project root, with Docker PostgreSQL running:

```bash
# Step 1 — Create schema (24 tables)
psql -h localhost -p 5432 -U <username> -d itf_tournament -f data/sql/schema/create_itf_schema.sql

# Step 2 — Load prerequisite data
psql -h localhost -p 5432 -U <username> -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql

# Step 3 — Load generated data (tournaments 1–58)
psql -h localhost -p 5432 -U <username> -d itf_tournament -f data/sql/generated/_run_all_generated_1to58.sql

# Step 4 — Load generated data (tournament 59)
psql -h localhost -p 5432 -U <username> -d itf_tournament  -f data/sql/generated/_run_all_generated_59.sql
```

### 4.4 Row Counts (after full load)

| Table | Rows |
|-------|------|
| Entries | 10,906 |
| DrawPlayers | 10,906 |
| DrawSeed | 3,596 |
| Matches | 6,710 |
| PlayerSuspensions | 10 |
| PointsHistory | 10,906 |
| WeeklyRanking | 11,236 |


## 5. Flask Application

### 5.1 Routes (20 total)

**Page routes (6):** tournament list, tournament detail, draw bracket view, rankings, admin panel, home redirect.

**Admin POST routes (4):** create entry, generate draw, create match skeleton, submit result.

**JSON API routes (10):** player search, reference data, tournament list, tournament info, tournament entries, tournament draws, draw info, draw matches, player ranking, plus supporting endpoints.

### 5.2 Service Layer

| Module | Responsibility |
|--------|---------------|
| `entry_service.py` | Deadline enforcement, entry insertion, entry-point snapshot |
| `draw_service.py` | Draw creation, seeding, bye assignment, DrawPlayers + DrawSeed population |
| `match_service.py` | Skeleton creation, score validation, result application, winner propagation, suspension creation |
| `view_service.py` | Score formatting (winner perspective), bracket rendering data |

### 5.3 Admin Workflow (Tournament 59 example)

1. **Enter players** — admin panel → entries close at Tuesday 10:00 UTC
2. **Generate draw** — admin clicks "Generate Draw" after the deadline → seeds assigned, byes placed, skeleton created
3. **Submit results** — admin enters scores per match → validation runs, winner advances to next round
4. **Recalculate** — `generate_outputs_t59.py` computes PointsHistory and WeeklyRanking for the completed tournament

### 5.4 Templates

Six Jinja2 templates styled with Tailwind CSS: `base.html`, `tournaments.html`, `tournament_detail.html`, `draw.html` (bracket with connector lines, seed badges, champion banner), `rankings.html`, `admin.html` (smart dropdowns, client-side score validation).


## 6. Database

### 6.1 Schema Summary

24 fully normalised tables (3NF) with composite primary keys where appropriate (`DrawSeed`, `DrawPlayers`, `WeeklyRanking`), comprehensive foreign keys, and CHECK constraints enforcing tennis scoring rules directly at the database level. See `data/sql/schema/create_itf_schema.sql`.

Notable constraints on `Matches`: tiebreak fields are required if and only if a set score is 7–6; the third set cannot have both a normal set score and a super-tiebreak; a third set is required if and only if the first two sets are split. Retired and disqualified matches (`match_status_id IN (4, 6)`) are exempt from these constraints to accommodate partial scores.

### 6.2 Validation Checks (10 queries)

All queries are in `data/sql/queries/`. Each returns `PASS` with 0 bad rows when the data is correct.

| # | Check | Query file |
|---|-------|-----------|
| 1 | First-match losers get 0 points | `first_match_losers_0points.sql` |
| 2 | WeeklyRanking uses best 4 results only | `best4results_only_in_weeklyranking.sql` |
| 3 | DQ and no-show get 0 points | `dq_noshow_0points.sql` |
| 4 | Suspension durations correct (2 or 6 months) | `suspension_durations_correct.sql` |
| 5 | Every DrawPlayers row has a matching Entry | `each_drawplayer_matching_entry.sql` |
| 6 | Rank positions sequential (no gaps) per category/week | `rank_positions_no_gap_within_cat_and_week.sql` |
| 7 | Match winner is player1 or player2 | `match_winner_is_player1_or_2.sql` |
| 8 | Completed match winner won exactly 2 sets | `completed_match_winner_won_2sets.sql` |
| 9 | Tiebreak winner matches set winner | `tiebreak_winner_completed_matches_set_winner.sql` |
| 10 | Entries contain only age-eligible players | `entries_with_only_age_eligible_players.sql` |


## 7. Repository Structure

```
ITF-Masters-Tour/
├── app.py                          # Flask entry point (20 routes)
├── run_local.sh                    # Local launch script
├── .env.example                    # Environment variable template
│
├── data/
│   ├── extracts/
│   │   ├── prerequisites/          # 15 reference Excel files
│   │   └── generated/              # 8 generated Excel files
│   └── sql/
│       ├── schema/                 # create_itf_schema.sql
│       ├── prerequisites/          # 15 INSERT scripts + _run_all_prerequisites.sql
│       ├── generated/              # 8 INSERT scripts + aggregate runners
│       ├── queries/                # 30+ validation and diagnostic queries
│       └── views/
│
├── docs/                           # Architecture docs, ER diagrams, rules
│   └── diagrams/                   # SVG and HTML ER diagrams
│
├── evidence/
│   └── screenshots/                # Portfolio evidence (draw skeletons, match lists)
│
├── reports/
│   ├── analysis/
│   └── exports/                    # generate_outputs_t1_58.py
│
├── scripts/
│   ├── generation/                 # generate_entries, draw_players, draw_seed, matches
│   ├── recalculation/              # points, rankings, exports, outputs_t59
│   ├── services/                   # entry, draw, match, view services
│   └── validation/                 # validate_itf_data, tennis_matches, draw_players
│
├── src/
│   └── modules/                    # Core engines: rules, seeding, scoring, ranking, scheduling
│
├── templates/                      # 6 Jinja2 templates (Tailwind CSS)
├── terraform/                      # AWS infrastructure (planned)
└── tests/
```


## 8. Local Setup

### 8.1 Prerequisites

- Python 3.12+
- Docker Desktop (for PostgreSQL)
- `pip install flask psycopg2-binary`
- PyCharm Professional (recommended) and DataGrip (recommended) for development and database inspection


### 8.2 Start PostgreSQL

```bash
docker run -d --name itf-postgres \
  -e POSTGRES_USER=<username> \
  -e POSTGRES_PASSWORD=<password> \
  -e POSTGRES_DB=itf_tournament \
  -p 5432:5432 \
  postgres:16
```

### 8.3 Load Data

Run the four SQL steps described in section 4.3.

### 8.4 Configure Environment

Copy `.env.example` to `.env` and set credentials to match the Docker container above:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=itf_tournament
DB_USER=<username>
DB_PASSWORD=<password>
```

### 8.5 Launch Flask

```bash
chmod +x run_local.sh
./run_local.sh
```

### 8.6 Browse

| URL | Page |
|-----|------|
| `http://127.0.0.1:5000/tournaments` | Tournament list |
| `http://127.0.0.1:5000/tournament/59` | Tournament 59 detail (entries + draws) |
| `http://127.0.0.1:5000/draw/233` | Draw 233 bracket (Men's 60, Tournament 59) |
| `http://127.0.0.1:5000/rankings` | Weekly rankings |
| `http://127.0.0.1:5000/admin` | Admin panel (entry, draw, skeleton, results) |


## 9. Challenges

Building this system over approximately 3 weeks surfaced several categories of problems.

### 9.1 Schema Constraints vs. Real Tennis Scenarios

The initial CHECK constraints on the `Matches` table enforced strict scoring validation:
- tiebreak required at 7–6
- third set required when sets are split. 

This worked for completed matches but rejected retired and disqualified matches outright, since those legitimately contain partial scores. 
The fix was adding `match_status_id IN (4, 6)` exemptions to every constraint, then re-importing 6,666 match rows. 
The debugging cycle involved isolating exactly 81 failing INSERT statements from thousands of lines of output, diagnosing the constraint name from each error, and iterating on the schema.


### 9.2 Tiebreak and Super-Tiebreak Enforcement

Early generated data contained impossible tiebreak scores in normal third sets (e.g., 10–5 or 11–6 where the maximum is 7 without an extended tiebreak). 
The root cause was that the generation logic was not consulting `Draws.has_supertiebreak` to decide the third-set format. 
Fixing this required tracing 27 individual match_id violations, correcting the score generator to respect the draw-level flag, and re-validating the full dataset.


### 9.3 Weekly Ranking Calculations

The "best 4 results over the previous 52 weeks" rolling window required precise ISO week arithmetic. 
Initial implementations miscounted week boundaries around year transitions, producing 6,467 incorrect ranking rows. 
The fix involved aligning the window start/end to ISO weeks rather than calendar dates and re-running the full ranking pipeline.


### 9.4 Draw Generation Bugs (Tournament 59)

Three bugs prevented successful draw generation for the live tournament: 
- a missing `draw_status_id` parameter in the Flask route
- a seeding rules query that fetched all rules without filtering by player count
- a reference to a non-existent `draw_size` column in `SeedingRules`. 

Each required tracing through the full call chain from Flask route → `draw_service.py` → `generate_draw_players.py`. 
The result was bye-against-bye placements and missing seeds — visible immediately on the bracket UI.


### 9.5 Score Display and Winner Propagation

Match scores were initially displayed from the perspective of player1 rather than the winner, producing confusing reversed scores on the bracket. 
Separately, players receiving a bye were not being marked as first-round winners, breaking bracket progression. 
Both were service-layer bugs in `match_service.py` and `view_service.py`.


### 9.6 AI-Generated Data Quality

Using ChatGPT, Claude Sonnet 4.5, Gemini, there were many problems first with creating the schema, then debugging scripts.
It is noticeable that AI often struggles with large projects (24 tables), missing tables, hardcoding values in place of an extra table and the use of foreign keys.
Scripts were repeatedly using wrong column names, which seemed rather avoidable.

Having built tons of normalised databases in the past, some errors were easy to spot, others less. 
I can only imagine how difficult it would be for anyone to build a similar project from scratch without prior experience of building large databases.
One could imagine that proper prompting and iteration - see @danmartell or @adfasdf ..... 
In theory, yes, you are as good as your prompting. It makes a lot of sense but practice contradicts the theory.
This is another topic but you wonder whether some AI models are not geared towards making you pay for more usage by producing deliberate mistakes (see some dubious business models).
They repeatedly ignore your prompting as it is overriden by their internal logic and training data.
Then comes a message like "Apologies, that was wasteful" or "Yes, that's on me, your instructions were clear. It won't happen again". You bet! 
Apologies are often strategy to burn more of your precious quotas. At least, it looks that way. You can limit the damage but not much more. 
Waiting for a huge customer revolt: follow the money, that is where the power lies.


## 10. Cost Analysis

### 10.1 Why Fargate

This is a disaster recovery portfolio project, not a long-running production system. 
The compute layer (Fargate vs. EC2) matters less than the DR infrastructure it demonstrates (Route53 failover, cross-region RDS replication, health checks). 
At a 2-day timescale, the cost difference between Fargate and EC2 is approximately $1. 
Fargate is the better portfolio choice: it demonstrates container orchestration without EC2 instance management.


### 10.2 Two-Day Cost Estimate (2 regions)

| Service | 2-day cost |
|---------|-----------|
| Fargate (0.25 vCPU, 0.5 GB × 2 regions) | ~$1.50 |
| RDS db.t4g.micro (primary + replica) | ~$2.00 |
| ALB (× 2 regions) | ~$2.00 |
| Route53 (hosted zone + health checks) | ~$1.50 |
| ACM | Free |
| **Total** | **~$7–8** |

The monthly cost would be $30–40 if left running. The infrastructure is destroyed after screenshot collection, keeping the total well under $10. VPC Endpoints are used instead of NAT Gateways, saving approximately $15/month ($21.90 vs. $36–50).


## 11. GitHub

The complete codebase — Python scripts, SQL files, Excel extracts, Jinja2 templates, ER diagrams, and screenshot evidence — is pushed to a GitHub repository. 
This serves as the permanent record of the project after AWS teardown.

A `.gitignore` file excludes files that should not be committed, to be finalised before the first push — candidates include:
- `.env`
- `__pycache__/`
- `*.pyc`
- `.idea/`
- any local Docker volumes.

The repository includes:
- All source code and configuration files
- SQL schema, prerequisite data, and generated data (both `.sql` and `.xlsx`)
- 30+ validation and diagnostic queries
- Screenshot evidence of the working application (draw skeletons, match lists, admin panel)
- Documentation (`Rules.md`, architecture docs, ER diagrams)

### 11.1 Install GitHub on WSL
```bash
sudo apt install gh
gh auth login
gh repo delete <username>/ITF-Project --yes
```

**"delete-repo scope" needed to delete the repository**
```bash
gh auth refresh -h github.com -s delete_repo
```
Then follow the prompts, enter the code in https://github.com/login/device > re-run the delete command > confirm deletion on the web interface.


### 11.2 




## 12. Planned Next Steps

1. **AWS deployment** — Terraform provisions Fargate + ALB + RDS PostgreSQL + Route53 + ACM across 2 regions on `aws.cloudcase.com`. Simulate primary region failure and demonstrate failover with data integrity.
2. **Evidence collection** — screenshots of the running application, DR failover, and Route53 health check transitions.
3. **Teardown** — destroy all AWS resources after evidence collection (max 2 days online).
4. **LinkedIn article** — technical write-up covering the database design, Flask application, AWS DR architecture, and cost decisions. Published after both the GitHub repo and AWS screenshots are available.

---

*Designed and implemented by Malik Hamdane — January–February 2026*