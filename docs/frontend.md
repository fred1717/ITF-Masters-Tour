## 0. Proposed plan for the front end
- Fix app.py route/dataclass mismatches against `draw_service.py`
- Add missing API routes (player lookup, tournament detail, rankings view)
- Build 4 polished Jinja templates with Tailwind CSS: tournament list, tournament detail, draw bracket, admin panel
- Admin panel: smart dropdowns (players, tournaments from DB), score validation feedback, proper deadline display
- Draw bracket: styled like the nice_mt400 HTML (gradient header, bracket lines, seed indicators)



## 1. Fix app.py route/dataclass mismatches against `draw_service.py`
See the new `app.py`



## 2. Add missing API routes (player lookup, tournament detail, rankings view)
8 new routes added:
- Page routes (2):
    - GET `/tournament/<id>` — detail page with draws + entries (needs `tournament_detail.html` template)
    - GET `/rankings — weekly rankings` with year/week filter (needs `rankings.html` template)

- JSON API routes (6):
    - GET `/api/players/search?q=...` — player autocomplete (min 2 chars, active players only)
    - GET `/api/reference-data` — age categories, genders, match statuses for dropdowns
    - GET `/api/tournament/<id>/info` — metadata + computed deadlines from ranking_window
    - GET `/api/tournament/<id>/entries` — filterable by age_category_id/gender_id
    - GET `/api/tournament/<id>/draws` — draws for a tournament
    - GET `/api/player/<id>/ranking` — latest ranking to auto-fill entry_points



## 3. Build 4 polished Jinja templates with Tailwind CSS: tournament list, tournament detail, draw bracket, admin panel
6 html templates:
- admin.html (with form to add/edit tournaments, entries, results)
- base.html (with Tailwind CSS, header/footer)
- draw.html (for tournament draw/bracket)
- rankings.html (weekly rankings view)
- tournament_details.html (tournament info + entries + draws)
- tournaments.html (list of tournaments with filters)


## 4. Admin panel: smart dropdowns (players, tournaments from DB), score validation feedback, proper deadline display
app.py (18 routes now):
- Added `GET /api/tournaments?recent=N` — single-call tournament list (replaces 15 sequential fetches)
- Added `GET /api/draw/<id>/matches` — match lookup for result form
- All 4 admin POST routes now wrapped in try/except with flash error messages

admin.html JS rewrite:
- Boot: 2 parallel API calls instead of 15 sequential
- Player autocomplete: now auto-selects `gender` + `age category` from `player/ranking` data
- Match picker: enter a `draw_id` → shows pending matches with player names, click to populate
- Client-side score validation (mirrors `validate_tennis_matches.py`):
    - Valid set scores: 6-0..6-4, 7-5, 7-6
    - Tiebreak required when 7-6, validated first-to-7 win-by-2
    - Super tiebreak: first-to-10 win-by-2
    - Split sets require 3rd set or super TB
    - Cannot have both 3rd set and super TB
    - Retired matches allow partial scores
    - Walkover requires no scores


## 5. Draw bracket: styled like the nice_mt400 HTML (gradient header, bracket lines, seed indicators)
Bracket restyled with:
- Connector lines between rounds — CSS ::before/::after pseudo-elements draw horizontal ticks from each match card + vertical merging lines in connector columns between rounds
- Winner highlighting — green gradient row with green monospace score
- Seed badges — gold compact squares (matching `nice_mt400` style)
- Status strips — `retired` (amber), `walkover` (red), `DQ` (red) shown as a thin bar below the match
- Champion banner — gold gradient with shadow, only shown when final has a winner
- Header stats — shows completed/total count and champion name inline
- List view — winner name in green, loser grayed out, clean grid layout
- Empty state — tennis emoji + hint to use admin panel



## 6. Local Flask setup instructions
Here's the plan for local Flask setup:
- Check `db_connection.py` for connection config (host, port, DB name, credentials) and confirm it matches your `Docker PostgreSQL`
- Verify the Python import paths work — src.modules, scripts.services, etc. from the project root
- Create a small `run_local.sh` script that sets env vars and launches Flask
- List any missing `pip` dependencies (`Flask`, `psycopg2`, etc.)
- Document the exact commands to run

### 6.1 Check `db_connection.py` for connection config (host, port, DB name, credentials) and confirm it matches your `Docker PostgreSQL`
Connection config is hardcoded: 
- localhost:5432
- database itf_tournament
- user itfuser
- password itfpwd. 

This should match your Docker PostgreSQL. One thing to confirm:
- Is your Docker PostgreSQL container exposing port 5432 on localhost?
- Are the credentials itfuser / itfpwd correct?

Also noticed: 
DatabaseConnection only has query() and query_params() 
— both call fetchall(). 
- The service layer (entry_service, draw_service, match_service) will need to INSERT/UPDATE rows. 
- Either the services handle their own connections, or there's a missing execute() method.


### 6.2 Make 'db_connection.py` dynamic
**Amendments**
- Created ENV vars for DB config in `db_connection.py` with defaults matching the current hardcoded values.
- Created `.env.example` file with the required ENV vars listed.



### 6.3 Create a `run_local.sh` launch script (on the Root directory)
**Make it executable**
```bash
chmod +x run_local.sh
```

**Run it**
```bash
./run_local.sh
```

Flask is running, so let's open http://127.0.0.1:5000 in the browser: we can see the front end.


### 6.4 List missing pip dependencies
Only two third-party packages needed: 
- `Flask`
- `psycopg2`

Since Flask is already running, both are installed. 
No missing dependencies.


### 6.5 Document the exact commands to run
This is also already covered by `run_local.sh`.

That means that all local setup steps are done. 
We are now ready to start entering tournament 59 players and the results, in order to:
- build out the front end pages
- test the new API routes.



## 7. Entering tournament 59 data
There is no scheduler. 
The deadline is only enforced as a gate — entry_service rejects entries after 10:00 UTC. 
Yet `num_players` is set only when one manually clicks 'Generate Draw' after the deadline.
Clicking on 'Generate Draw' triggers the draw generation logic, which computes `num_players`: the draw can be published before the following Friday, 19:00 UTC.
So the workflow is: 
- entries close automatically at 10:00 
- you click 'Generate Draw' whenever ready after that 
- `num_players` is computed from the entry count at that moment.

**Fix needed**
- Implement additional block not allowing generating the draw until the entry deadline has passed.
- Make sure there is no block allowing generating the draw before Friday 19:00 UTC. There wasn't any block, so it's ok.

### 7.1 Updating weekly ranking for week 7 and 8 of 2026 as it is missing (and creating both sql and excel files for week 7 and 8 of 2026)
```bash
python3 scripts/recalculation/generate_ranking_year2026_weeks7and8.py
```

I pasted the sql and Excel data into the main sql and Excel files.


### 7.2 Running SQL queries to get the weekly ranking for week 7, which will be used for seeding the tournament 59 (on week 8).
This list will be used to choose the players to enter manually for tournament 59.
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/weeklyranking_year2026_week7_men60.sql
```
First, checking rankings for tournament 59 and available players for each draw.
Getting player list from week 7 (tonight), knowing that the tournament is on week 8 and the seeding will be based on the week 7 rankings from tonight (Monday 9 February, 10:00 UTC)

Men's 60:
rank player_id   first_name   last_name         country_id    total_points                
36 |        58 | Matthias   | Hohenfeld       |          4 |          590
37 |        81 | Marcel     | Merckx          |          6 |          590
42 |        94 | Pascal     | Rast            |         10 |          300
45 |        93 | Fabien     | Frenzel         |         10 |          140
46 |        99 | Yvon       | Bardot          |          1 |           70
49 |        98 | Dider      | Pomarel         |          3 |          500
50 |        89 | Richard    | Gullit          |          3 |          590
57 |        51 | David      | Colombelli      |          1 |            0
60 |        54 | Alexandre  | Dumas           |          1 |            0
58 |        52 | Nuno       | Sobreda         |         11 |            0
59 |        53 | Matthew    | Kelly           |          3 |            0

Men's 65:
rank player_id   first_name   last_name         country_id    total_points                
27 |        14 | Julien     | Peyron      |          1 |          770
28 |        45 | Jaime      | Barato      |          2 |          740
30 |        48 | Tiago      | Almada      |         11 |          520
31 |        16 | Antonio    | Banderas    |          2 |          375
40 |         4 | Michel     | Durand      |          1 |            0
41 |         5 | Robert     | Duval       |          1 |            0
42 |         6 | Jacques    | Feuvrier    |          1 |            0
43 |         7 | Helmut     | Grass       |          4 |            0
46 |        10 | Daniel     | Hennig      |          4 |            0

Women's 60:
rank player_id   first_name   last_name         country_id    total_points                
37 |       192 | Anne       | Rijkaardt       |          7 |          730
40 |       195 | Katrin     | Frenzel         |         10 |          400
41 |       196 | Heidi      | Rast            |         10 |          335
42 |       193 | Louise     | Boppart         |          6 |          310
56 |       154 | Marta      | Sobreda         |         11 |            0
57 |       155 | Helen      | Kelly           |          3 |            0

Women's 65:
rank player_id   first_name   last_name         country_id    total_points                
35 |       152 | Julia      | Colombo     |          2 |          280
36 |       151 | Patricia   | Rouxinol    |         11 |          225
37 |       149 | Laura      | Campos      |         11 |          190
38 |       112 | Monika     | Hennig      |          4 |          155
47 |       105 | Sylvie     | Dessange    |          1 |            0
49 |       107 | Francine   | Duval       |          1 |            0
52 |       110 | Susanne    | Derrick     |          4 |            0

### 7.4 Manually entering tournament 59 players and results using the admin panel
First, run `./run_local.sh` to start Flask again ask I couldn't access the site anymore. Then open http://http://127.0.0.1:5000/admin 

Check entering players manually updated the Entries table in the DB correctly. 
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/entries_timestamp_tournament59.sql
```

All draws are displayed correctly on the tournament details page, see at http://127.0.0.1:5000/tournament/59 


## 8. Generate Draw
Apparently, there are 3 bugs in the draw generation logic that would prevent successful draw generation for tournament 59.

### 8.1 Fix `app.py`
The `/admin/generate-draw` route is missing `draw_status_id` and `has_supertiebreak` when constructing `DrawGenerationRequest` (would cause TypeError)


### 8.2 Fix `draw_service.py`
Seeding rules query fetches ALL rules but doesn't filter by player count; the correct rule for the draw's entry count must be selected.
New line inserted, line 105.


### 8.3 Fix `generate_draw_player.py`
It references `rule.get`("draw_size") but SeedingRules schema has no `draw_size` column (only `id`, `min_players`, `max_players`, `num_seeds`); 
draw size (next power of 2) and bye count must be computed from `num_entries`.


### 8.4 Generate the draw and check the results
To do that:
- Restart the Flask app to pick up the changes
- Go to http://127.0.0.1:5000/admin
- In the Generate Draw section, submit 4 times — once per draw

The skeleton is a complete mess.
The men's 60 11 entered players are drawn into a 16-player draw with 5 byes.
The 5 players getting a bye should be the best ranked 5 players, but the seeding rules logic is broken and seeds are not assigned. You even have bye against bye, which is idiotic.
The 5 players should be:
- Matthias Hohenfeld, id=58, ranked 36
- Marcel Merckx, id=81, ranked 37
- Richard Gullit, id=89, ranked 38
- Didier Pomarel, id=98, ranked 39
- Pascal Rast, id=94, ranked 42

All fixes applied, now 4 draws are generated with correct seeds and 4 skeletons too.
All perfect, screenshots taken for the portfolio and saved in '/evidence/screenshots/'



## 9. Planning Rest of project
Logical order:

README — local, finish now
GitHub — push all code, SQL, Excel, screenshots to the repo
AWS deployment — Terraform, Fargate, ALB, RDS, Route53, ACM, DR demo, collect screenshots as evidence
LinkedIn article — written last, since it needs both the GitHub repo link and AWS deployment screenshots

### 9.1 Match results generation by entering results manually in the admin panel
**Plan:**
- Enter all match results manually today (Tuesday 10 February) and evidence the UI works (matches supposed to happen between Monday 16 and Sunday 22 February).
- Update the database, so all match dates match the tournament 59 week (16-22 February). Evidence that with screenshots.

3 bugs:
- scores displayed from perspective of player1, not winner (so score is reversed for player2)
- players getting a bye are not marked as winners of their first round match, so they appear as pending instead of completed with a win for the seeded player. 
    This is a critical bug to fix for the DR demo, otherwise the skeleton will be broken and the DR failover won't work correctly.
- If you choose the wrong player as winner, it is not flagged and the loser goes through to the next round instead of the winner. 


### 9.2 Fix bugs 
- in `/scripts/services/match_service.py` (for the 'bye' fix)
- in `/scripts/services/match_service.py` (validating the correct winner)
- in `/scripts/services/view_service.py` (for the 'score format from the winner's perspective' fix)


### 9.3 Two queries to check past suspensions were applied correctly
```bash sql
SELECT m.match_id, m.draw_id, m.match_status_id, m.player1_id, m.player2_id, m.winner_id
FROM Matches m
WHERE m.match_status_id IN (3, 6)
  AND NOT EXISTS (
      SELECT 1 FROM PlayerSuspensions ps
      WHERE ps.reason_match_status_id = m.match_status_id
        AND ps.player_id = CASE
            WHEN m.winner_id = m.player1_id THEN m.player2_id
            ELSE m.player1_id
        END
  );
```
7 suspensions not applied correctly.

**Amend `/scripts/services/match_service.py` to fix that and restart Flask**
```bash
./run_local.sh
```

### 9.4 Create `/scripts/recalculation/generate_outputs_t59.py` to auto-generate match results with simulated timestamps
**What it does:**
- Reads draws 233–236, `DrawPlayers`, `DrawSeed`, `Entries`, `Matches` from DB
- Calculates `PointsHistory` for tournament 59 (MT400 points rules) and inserts into DB
- Calculates `WeeklyRanking` week 9 (full 52-week window) and inserts into DB
- Exports 7 SQL files + `_run_all_generated_59.sql` to `/data/sql/generated/`
- Exports 7 Excel files + `weeklyranking_year2026_week9.xlsx` to `/data/extracts/generated/`
- Idempotent — skips DB inserts if data already exists

**To run it**
```bash
python3 scripts/recalculation/generate_outputs_t59.py
```

### 9.5 Check the outputs are correct by running 6 queries
Checks to run are:
- `PointsHistory consistency` — winner of each draw got correct MT400 winner points (400), finalist got 280, first-match losers got 0
- Walkover/retirement points — Helen Kelly (Draw 234 walkover winner) got points, not 0; the no-show player got 0
- `WeeklyRanking` week 9 vs week 8 — top players' totals changed logically (tournament 59 winners gained points, others unchanged or dropped if a tournament fell out of the 52-week window)
- All 9 suspensions exist — 7 historical + 2 from tournament 58, none from tournament 59 (0 is expected if no DQ/walkover was entered)
- `DrawSeed` consistency — 12 seeds across 4 draws match the seeding rules (4 seeds for 11-player draws, 2 seeds for 6-player draws)
- Match count per draw — 15 matches for 16-draw (draws 233, 235), 7 matches for 8-draw (draws 234, 236)

#### 9.5.1 Running `points_history_points_correctness.sql`
```sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/points_history_points_correctness.sql
```
This checks 'walkover/retirements' points as well, so no need for an extra query for that. All points correct.

#### 9.5.2 Running `weekly_ranking_week9_vs_week8.sql`
```sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/weeklyranking_week9_vs_week8.sql
```
Seems fine.


#### 9.6 Table `PlayerSuspensions` missing in DataGrip
Updating `PlayerSuspensions` table by renumbering `suspension_id' from 1 to 10 instead of from 50 to 59.
```sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/suspension_id_renumbering.sql
```
Output is fine.


#### 9.7 Validated seed distribution in tournament 59
Checking we got the correct number of seeds in tournament 59, which we did.
```sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/validated_seed_distribution_t59.sql
```
Output is fine.


#### 9.8 Match count per draw in tournament 59
Checking we got the correct number of matches per draw in tournament 59, which we did.
```sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/match_count_per_draw_t59.sql
```
Output is fine.


#### 9.9 Populating `DrawSeed` table for tournament 3 to 58 (draw_id 9 to 232)
```sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/generated/drawseed_t3to58_draw_9to232.sql
```
3584 entries inserted, which is correct for 224 draws with 16 seeds max per draw (some have fewer seeds).

**Creating `drawseed.sql` for tournaments 3 to 59 (draw_id 9 to 236)**
```bash
python3 scripts/recalculation/export_drawseed_draw_9to236.py
```
Also updated `_run_all_generated_59.sql` to include that file, so it can be run in one go for the AWS deployment.


#### 9.10 Exporting all generated Excel files for tournaments 1 to 59
```bash
python3 scripts/recalculation/export_all_generated_xlsx.py
```
**Expected output**
```text
=== Exporting tables to Excel ===
  Entries.xlsx: 10906 rows
  DrawPlayers.xlsx: 10906 rows
  DrawSeed.xlsx: 3596 rows
  Matches.xlsx: 6710 rows
  PlayerSuspensions.xlsx: 10 rows
  PointsHistory.xlsx: 10906 rows
  WeeklyRanking.xlsx: 11236 rows
```









## 10. Cost estimate for the front end work and whole DR project
For 1-2 days only, costs are proportional (per-hour billing). Rough breakdown for 2 regions, 2 days:
Service                                                         2-day cost (×2 regions)
Fargate (0.25 vCPU, 0.5GB)                                      ~$1.50
EC2 t4g.micro                                                   ~$0.80
RDS db.t4g.micro (primary + replica)                            ~$2.00
ALB (×2)                                                        ~$2.00
Route53 hosted zone + health checks                             ~$1.50
ACM                                                             Free
Total (Fargate path)                                            ~$7-8
Total (EC2 path)                                                ~$6-7

For 1-2 days the difference between Fargate and EC2 is about $1. 
So Fargate is actually fine here 
— it looks better on the portfolio and the cost penalty is negligible at this timescale.
- The $30-40/month figure would only apply if it is left running. 
- Tear it down after screenshots and it's well within a $10 budget.
- The README cost chapter would contrast monthly vs short-lived costs and justify Fargate over EC2 specifically for this scenario. Good portfolio content.

This is a DR portfolio project that gets destroyed after evidence collection.
The real showcase is the multi-region failover infrastructure (Route53, RDS cross-region replicas, health checks) — not the compute layer. 
The Flask app is lightweight.


