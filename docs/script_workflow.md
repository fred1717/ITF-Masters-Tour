## 1. Immediate implications of “Rules.md is the only truth”
- All generation logic must be centralised, so that every script (generate + regenerate + recalculations) consumes the same rule engine, 
rather than embedding ad-hoc probabilities in multiple places.
- Validation scripts must be treated as gates: generation must target “passes validations”, not “looks plausible”.



## 2. Required generation scope (as stated)
- To be entirely generated according to Rules.md (including match_date constraints and weighted score distributions): `Matches.xlsx`.
- To be generated fully or partially per `Rules.md` (with the explicit tournament/week ranges already stated):
    - `Draws.xlsx`
    - `DrawPlayers.xlsx`
    - `DrawSeed.xlsx`
    - `Entries.xlsx`
    - `PointsHistory.xlsx`
    - `WeeklyRanking.xlsx`
- To be treated as fixed reference data and not to be regenerated: CSV files.



## 3. Why capitalised table names were not “case-sensitive” in PostgreSQL
In `create_itf_schema.sql`, tables are created without double quotes (e.g., `CREATE TABLE Gender (...))`. 
In PostgreSQL, unquoted identifiers are folded to lowercase, so the database objects are not case-sensitive in the way `Gender` would be.
However, capitalised file naming (CSV/Excel) remains a valid convention for consistency and readability.






## 4. Inserting generated data into the database by running a single file with all the generated data.
It is better than running each file separately, so we can avoid missing dependencies.
See `create_itf_schema.sql`

The Docker method didn't work, so, after installing `psql`:
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
```



## 5. Testing files
### 5.1 First test series
**Parsing `rules_engine.py`**
```bash
python3 -m py_compile src/modules/rules_engine.py
```

**Parsing `entry_service.py`**
```bash
python3 -m py_compile src/modules/rules_engine.py scripts/services/entry_service.py
```
For both files, nothing returned means they are correct!

**Parsing `generate_outputs_t1_58.py`**
```bash
python3 -m py_compile reports/exports/generate_outputs_t1_58.py
```
Same: nothing returned, so the file is correct.

**Now running `generate_outputs_t1_58.py`**
```bash
PYTHONPATH="$(pwd)" python3 reports/exports/generate_outputs_t1_58.py
```
Thanks to Claude Opus 4.5, everything works.


### 5.2 Second test series
```bash
docker exec -i itf-postgres psql -U itfuser -d itf_tournament < data/sql/schema/create_itf_schema.sql
docker exec -i itf-postgres psql -U itfuser -d itf_tournament < data/sql/prerequisites/_run_all_prerequisites.sql
```
or
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
```
**Creating `_run_all_generated_1to58.sql`:**
- Generated data for tournaments 1-58
- Run AFTER _run_all_prerequisites.sql
- Order follows the generation pipeline

```bash
\i data/sql/generated/entries.sql
\i data/sql/generated/drawplayers.sql
\i data/sql/generated/matches.sql
\i data/sql/generated/playersuspensions.sql
\i data/sql/generated/pointshistory.sql
\i data/sql/generated/weeklyranking.sql
```
**Let's try the `psql` method (in our case, the first 2 commands have already been run):**
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/schema/create_itf_schema.sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/generated/_run_all_generated_1to58.sql
```
**Example output** INSERT 0 1 (countless times)


### 5.3 Counting how many rows were inserted
Expected: 10873, 10873, 6666, 2, 10873, 10576.
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -c "
SELECT 'Entries' AS t, COUNT(*) FROM Entries
UNION ALL SELECT 'DrawPlayers', COUNT(*) FROM DrawPlayers
UNION ALL SELECT 'Matches', COUNT(*) FROM Matches
UNION ALL SELECT 'PlayerSuspensions', COUNT(*) FROM PlayerSuspensions
UNION ALL SELECT 'PointsHistory', COUNT(*) FROM PointsHistory
UNION ALL SELECT 'WeeklyRanking', COUNT(*) FROM WeeklyRanking;
"
```
**Expected output:**
```text
Entries           | 10873
 DrawPlayers       | 10873
 Matches           |  6585
 PlayerSuspensions |     2
 PointsHistory     | 10873
 WeeklyRanking     | 10576
```
5 out of 6 match perfectly. Matches is off by 81 (6585 vs 6666). 


### 5.4 Investigating the gap in output for the Matches table
#### 5.4.1 First query
```bash
grep -c "^INSERT INTO Matches" data/sql/generated/matches.sql
```
**Expected output:** 6666

This will tell us whether the gap is in the file or happened during import, 
for example duplicate match_id PK rejections not noticed among the thousands of INSERT 0 1 lines).

#### 5.4.2 Second query
This clears and re-inserts, capturing only the error lines, so we can know exactly which constraints are failing.
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -c "DELETE FROM Matches;"
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/generated/matches.sql 2>&1 | grep -i error
```
**Example output:** 81 lines of errors (678 to 758)
```text
psql:data/sql/generated/matches.sql:70: ERROR:  new row for relation "matches" violates check constraint "chk_set2_tiebreak"
................... 81 times
```
The problem is the constraints in the database schema


### 5.5 Recreating `create_itf_schema.sql` by modifying constraints, so retired players get their matches validated
One the new file has been created:
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/schema/create_itf_schema.sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/generated/_run_all_generated_1to58.sql
```
Then again, counting how many rows were inserted (expected = 10873, 10873, 6666, 2, 10873, 10576). Hopefully, we will get the 6666 matches!
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/counting_rows_inserted_in6tables.sql
```
**Expected output:**
```text
Entries           | 10873
DrawPlayers       | 10873
Matches           |  6666
PlayerSuspensions |     2
PointsHistory     | 10873
WeeklyRanking     | 741
```
This time, it is WeeklyRanking that is missing nearly 10,000 rows.
It was stale data, now there are 10576 rows



## 6. Database checks
10 checks to cover key business rules.

### 6.1 Check 1 - First-match losers must get 0 points (Rules.md)
In DataGrip: run `first_match_losers_0points.sql` 

**Expected output:**
result, bad_rows
PASS,   0


### 6.2 Check 2 — WeeklyRanking uses best 4 results only (Rules.md)
In DataGrip: run `best4results_only_in_weeklyranking.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/best4results_only_in_weeklyranking.sql
```
**Expected output:**
result, bad_rows
FAIL,   6467
(1 row)

**Diagnosing failures**
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/diag_wr.sql
```

### 6.3 Check 3 — Disqualified and No-Show get 0 points (Rules.md)
This verifies that any player who lost via walkover (3) or disqualification (6) received 0 points.
In DataGrip: run `dq_noshow_0points.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/dq_noshow_0points.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.4 Check 4 — Suspension durations correct (Rules.md)
This verifies that suspension durations are respectively 2 months (no show) and 6 months (disqualified).
In DataGrip: run `suspension_durations_correct.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/suspension_durations_correct.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.5 Check 5 — Every DrawPlayers row has a matching Entry (pipeline integrity)
In DataGrip: run `each_drawplayer_matching_entry.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/each_drawplayer_matching_entry.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.6 Check 6 — Rank positions are sequential (no gaps) within each category/week
In DataGrip: run `rank_positions_no_gap_within_cat_and_week.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/rank_positions_no_gap_within_cat_and_week.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.7 Check 7 — Match winner must be player1 or player2
In DataGrip: run `match_winner_is_player1_or_2.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/match_winner_is_player1_or_2.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.8 Check 8 — Completed match winner won exactly 2 sets (status 1 = completed)
In DataGrip: run `completed_match_winner_won_2sets.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/completed_match_winner_won_2sets.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.9 Check 9 — Tiebreak winner matches set winner (for completed matches with 7-6 sets)
In DataGrip: run `tiebreak_winner_completed_matches_set_winner.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/tiebreak_winner_completed_matches_set_winner.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


### 6.10 Check 10 — Entries only contain age-eligible players (Rules.md: 60+ and 65+ categories)
In DataGrip: run `entries_with_only_age_eligible_players.sql` 

```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/queries/entries_with_only_age_eligible_players.sql
```
**Expected output:**
PASS (1 row), 0 bad rows


