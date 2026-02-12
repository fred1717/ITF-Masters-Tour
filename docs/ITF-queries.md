To clear tables in DataGrip:
```bash
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

Create scripts and sql folders in PyCharm project:
```bash
mkdir scripts sql
```

Move files to sql folder:
```bash
mv create_itf_schema.sql sql/
mv load_itf_data.sql sql/
```

Move Python validation script to scripts folder:
```bash
mv validate_tennis_matches.py scripts/
```




After restarting the computer, I must restart the Docker container, so in PyCharm terminal:
```bash
docker start itf-postgres
```

Activate the virtual environment:
```bash
source venv/bin/activate
```


**Reset the database + Load the Schema and data:**
```bash
docker exec -i itf-postgres psql -U itfuser -d itf_tournament < data/sql/schema/create_itf_schema.sql
docker exec -i itf-postgres psql -U itfuser -d itf_tournament < data/sql/prerequisites/_run_all_prerequisites.sql
```
or
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
```

So the commands mean:
docker exec = run a command inside the container
-i = keep input open (so we can send SQL)
itf-postgres = name of the container
psql = PostgreSQL command-line tool
-U itfuser = connect as user "itfuser"
-d itf_tournament = connect to database "itf_tournament"
-p parent + don't error if the directory already exists.

Last command didn't work, so other command after confirming port mapping for PostgreSQL is 5432:
```bash
docker port itf-postgres
```
**Example output:**
```text
5432/tcp -> 0.0.0.0:5432
5432/tcp -> [::]:5432
```

**Running `_run_all_prerequisites.sql` to load prerequisite data into tables**
```bash
psql -h localhost -p 5432 -U itfuser -d itf_tournament -f data/sql/prerequisites/_run_all_prerequisites.sql
```

**Populate all tables with prerequisite data (in 17 tables) by running `_run_all_prerequisites.sql`:**
Indeed, `_run_all_prerequisites.sql` contains all 17 prerequisite tables.
```bash
\i data/sql/prerequisites/agecategory_prerequisites.sql
\i data/sql/prerequisites/gender_prerequisites.sql
\i data/sql/prerequisites/playerstatus_prerequisites.sql
\i data/sql/prerequisites/matchstatus_prerequisites.sql
\i data/sql/prerequisites/matchrounds_prerequisites.sql
\i data/sql/prerequisites/stageresults_prerequisites.sql
\i data/sql/prerequisites/seedingrules_prerequisites.sql
\i data/sql/prerequisites/drawstatus_prerequisites.sql
\i data/sql/prerequisites/country_prerequisites.sql
\i data/sql/prerequisites/location_prerequisites.sql
\i data/sql/prerequisites/venue_prerequisites.sql
\i data/sql/prerequisites/surfaces_prerequisites.sql
\i data/sql/prerequisites/tournamentcategories_prerequisites.sql
\i data/sql/prerequisites/pointsrules_prerequisites.sql
\i data/sql/prerequisites/players_prerequisites.sql
\i data/sql/prerequisites/tournaments_prerequisites.sql
\i data/sql/prerequisites/draws_prerequisites.sql
```
Each of the 17 commands above populates 1 table with prerequisite data (INSERT statements).
or better:
```bash
docker exec -i itf-postgres pg_dump \
  -U itfuser -d itf_tournament \
  --data-only \
  --column-inserts \
  --disable-triggers \
  --no-owner \
  --no-privileges \
  > data/sql/load_itf_data.sql
```
**Notes**
- `--data-only` ensures schema is not dumped (schema remains in `create_itf_schema.sql`).
- `--column-inserts` makes INSERTs explicit per column (readable, resilient to column order changes).
- `--disable-triggers` avoids FK issues during reload ordering.
- `--no-owner --no-privileges` avoids environment-specific noise.




**Cleanup commands:**
Command 1:
```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
```
What it does:
- `find .` : Scans from the current directory downward..
- `-type f` : Restricts matches to regular files.
- `-name "__pycache__"` : Matches directories named exactly `__pycache__`.
- `-prune` : Prevents find from descending into that matched directory (efficiency, and avoids listing files inside it).
- `-exec rm -rf {} +` : Deletes the matched directories:
- `{}` : is replaced by each matched path.
- `rm -rf` : removes the directory recursively and does not prompt.
- `+` : batches multiple matches into fewer `rm` calls (more efficient than `\;`).
Effect: every `__pycache__` folder under the current directory is deleted.

Command 2:
```bash
find . -type f -name "*.pyc" -delete
```
What it does:
- `find .` : Scans starting from the current directory (.) and all subdirectories.
- `-type d` : Restricts matches to directories only.
- `-name "*.pyc"` : Matches files ending in `.pyc` (compiled Python bytecode).
- `-delete` : Deletes each matched file.
Effect: any stray `.pyc` files anywhere in the tree are deleted (including those not inside `__pycache__`).

**Safety notes**
- Both commands operate relative to the current directory. Running them from the repository root confines deletions to the repo.
- Only cache artefacts are targeted (`__pycache__` directories and `.pyc` files). Source files (`*.py`) are not targeted.


**What `__pycache__` is:**
- `__pycache__` is a Python bytecode cache folder created automatically by the Python interpreter.
- It contains `*.pyc` files (compiled bytecode) such as `calculate_points_history.cpython-312.pyc`.

**Purpose:** faster imports / faster subsequent runs.
It is environment-specific and disposable: safe to delete at any time; Python will recreate it.

**What should be done with `__pycache__` and `*.pyc` in this project**
These are dev-only artefacts and should not be committed to Git.

**Git ignore rules (recommended)**
Add (or ensure) the following entries exist in `.gitignore`:
```text
__pycache__/
*.pyc
```

**One operational convention to prevent surprises when running from different working directories**
REPLACE
```bash
python3 scripts/recalculation/apply_sanctions.py
python3 scripts/recalculation/recalculate_points.py
python3 scripts/recalculation/recalculate_rankings.py
```
WITH
```bash
PYTHONPATH="$(pwd)" python3 scripts/recalculation/apply_sanctions.py
PYTHONPATH="$(pwd)" python3 scripts/recalculation/recalculate_points.py
PYTHONPATH="$(pwd)" python3 scripts/recalculation/recalculate_rankings.py
```





VALIDATION CHECKS
✅ Database Schema (create_itf_schema.sql) - Now includes 5 CHECK constraints on the Matches table:

Set 1 tie-break required when score is 7-6 or 6-7
Set 2 tie-break required when score is 7-6 or 6-7
Set 3 tie-break required when score is 7-6 or 6-7
Set 3 must be EITHER normal set OR super tie-break (not both)
Third set required when first two sets are split

✅ Validation Script (validate_tennis_matches.py) - Python class that validates ALL tennis scoring rules:

Set scores must be valid (6-0, 6-1... 7-6)
Tie-break scores (first to 7, win by 2)
Super tie-break scores (first to 10, win by 2)
Third set logic
Format exclusivity

Location: Both files are in /mnt/user-data/outputs/
This demonstrates:

Database-level data integrity (CHECK constraints)
Application-level validation (Python script)
Professional portfolio-quality architecture!

Check the number of rows in Players, Matches, WeeklyRanking tables to ensure data loaded correctly:
```bash
docker exec -i itf-postgres psql -U itfuser -d itf_tournament -c "SELECT COUNT(*) FROM Players; SELECT COUNT(*) FROM Matches; SELECT COUNT(*) FROM WeeklyRanking;"
```
 count 
-------
   204
(1 row)

 count 
-------
  2769
(1 row)

 count 
-------
  9155
(1 row)



First query to get Men 60 rankings on 19 January 2026:
```bash
SELECT p.player_id, p.last_name, p.first_name, wr.rank_position, wr.total_points
FROM WeeklyRanking wr
JOIN Players p ON wr.player_id = p.player_id
WHERE wr.ranking_year = 2026 
    AND wr.ranking_week = 4
    AND wr.age_category_id = 1
    AND wr.gender_id = 1
ORDER BY wr.rank_position;
``` 

Women 60 rankings on 19 January 2026:
```bash
SELECT p.player_id, p.last_name, p.first_name, wr.rank_position, wr.total_points
FROM WeeklyRanking wr
JOIN Players p ON wr.player_id = p.player_id
WHERE wr.ranking_year = 2026 
    AND wr.ranking_week = 4
    AND wr.age_category_id = 1
    AND wr.gender_id = 2
ORDER BY wr.rank_position;
```

Men 65 rankings on 1 February 2026:
```bash
SELECT p.player_id, p.last_name, p.first_name, wr.rank_position, wr.total_points
FROM WeeklyRanking wr
JOIN Players p ON wr.player_id = p.player_id
WHERE wr.ranking_year = 2026 
    AND wr.ranking_week = 6
    AND wr.age_category_id = 2
    AND wr.gender_id = 1
ORDER BY wr.rank_position;
```
Women 65 rankings on 1 February 2026:
```bash
SELECT p.player_id, p.last_name, p.first_name, wr.rank_position, wr.total_points
FROM WeeklyRanking wr
JOIN Players p ON wr.player_id = p.player_id
WHERE wr.ranking_year = 2026 
    AND wr.ranking_week = 6
    AND wr.age_category_id = 2
    AND wr.gender_id = 2
ORDER BY wr.rank_position;
```


Nice MT700 Open, Men 60 results, week 2 of 2025:
```bash
SELECT 
    p.player_id,
    p.last_name,
    p.first_name,
    sr.description as result,
    ph.points_earned
FROM Entries e
JOIN Players p ON e.player_id = p.player_id
JOIN Tournaments t ON e.tournament_id = t.tournament_id
JOIN PointsHistory ph ON ph.player_id = e.player_id 
    AND ph.tournament_id = e.tournament_id 
    AND ph.age_category_id = e.age_category_id
JOIN StageResults sr ON ph.stage_result_id = sr.id
WHERE t.name = 'Nice MT700 Open 2025'
    AND e.age_category_id = 1
    AND e.gender_id = 1
ORDER BY sr.display_order;
```

Nice MT400 Senior, Men 60 results, week 3 of 2025:
```bash
SELECT 
    p.player_id,
    p.last_name,
    p.first_name,
    sr.description as result,
    ph.points_earned
FROM Entries e
JOIN Players p ON e.player_id = p.player_id
JOIN Tournaments t ON e.tournament_id = t.tournament_id
JOIN PointsHistory ph ON ph.player_id = e.player_id 
    AND ph.tournament_id = e.tournament_id 
    AND ph.age_category_id = e.age_category_id
JOIN StageResults sr ON ph.stage_result_id = sr.id
WHERE t.name = 'Miami MT1000 Open 2025'
    AND e.age_category_id = 1
    AND e.gender_id = 1
ORDER BY sr.display_order;
```


Total points (calculate for the last 52 weeks, from 1 February 2026 / Alain Bouvier, +65, should have 1250 points)
It worked: 500+330+210+210=1250 (10 Feb 2025 / 21 April 2025 / 29 Dec 2025 / 08 Sept 2025)
```bash
SELECT 
    t.name as tournament_name,
    ph.points_earned,
    ph.created_at as points_added_date
FROM PointsHistory ph
JOIN Tournaments t ON ph.tournament_id = t.tournament_id
JOIN Players p ON ph.player_id = p.player_id
WHERE p.first_name = 'Alain' 
    AND p.last_name = 'Bouvier'
    AND ph.age_category_id = 2
    AND ph.created_at BETWEEN '2025-02-03' AND '2026-02-02'
ORDER BY ph.points_earned DESC, ph.created_at DESC;
```




**Next steps after running 'python3 regenerate_matches.py':**
1. Review the CSV file
2. Replace Matches sheet in your Excel file with this data
3. Regenerate PointsHistory (run recalculate_points.py)
4. Regenerate WeeklyRanking (run recalculate_rankings.py)
5. Regenerate load_itf_data.sql
6. Reload database




**Created recalculate_points.py.**
Complete workflow to fix all data:

Run regenerate_matches.py → Creates Matches with correct round_ids
Run recalculate_points.py → Creates PointsHistory from actual match results
Run recalculate_rankings.py → Creates WeeklyRanking from corrected PointsHistory

Each script:

Exports CSV for review
Asks for confirmation before updating database
Automatically stops at completed tournaments (tournament 54, ended yesterday)



**Exact SQL to fix draw 208:**
```bash
docker exec -i itf-postgres psql -U itfuser -d itf_tournament -c "
UPDATE DrawPlayers dp
SET has_bye = NOT EXISTS (
  SELECT 1
  FROM DrawPlayers opp
  WHERE opp.draw_id = dp.draw_id
    AND opp.draw_position = CASE
      WHEN (dp.draw_position % 2) = 0 THEN dp.draw_position - 1
      ELSE dp.draw_position + 1
    END
)
WHERE dp.draw_id = 208;
"
```
**Result for draw 208:**
- `has_bye=true` only for positions 2 and 6 (because positions 1 and 5 are missing)
- `has_bye=false` for positions 3, 4, 7, 8

After that, `python3 app.py` can be run as usual, and `/draw/208` should no longer show 4 byes in QF.

