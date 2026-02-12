## 1. Practical sequence##
Flask app first (local), then Terraform: this minimises infrastructure churn and keeps the “website workflow” stable before provisioning AWS.

### 1.1 Flask: define the end-to-end workflow (database → UI → database)
#### 1.1.1 The minimum “production” workflow is:
- Player registration
- Insert a single row into `Entries` (no random generation).
- Enforce entry deadline.
- Draw generation (after deadline)
- Query eligible entries for (`tournament_id`, `age_category_id`, `gender_id`)
- Create `Draws` + `DrawPlayers` using the existing seeding/position logic.
- Match skeleton creation (no results yet)
- Create bracket rows in `Matches` with NULL scores and NULL `winner_id`.
- Either pre-create all rounds (recommended for easier rendering) or create next rounds on-demand.
- Result entry + validation + winner propagation
- Validate score using `validate_tennis_matches.py`.
- Update `Matches` row.
- Advance winner to the correct next-round slot.
- On final completion: set draw status “Completed”.
- Read-only public views
- Tournament list and draw view (bracket rendering from ordered matches).
- Rankings views from `WeeklyRanking`.

#### 1.1.2 Immediate Python changes to support Flask (small, targeted)
**The existing scripts should be refactored into importable functions, so Flask routes can call them:**
- `generate_draw_players.py`: keep draw positioning logic as a library function.
- `generate_matches.py` / `regenerate_matches.py`: add a “create skeleton only” function.

**Add a small service layer (module names indicative):**
- `entry_service.py`
- `draw_service.py`
- `match_service.py` (includes “advance winner”)
This avoids Flask shelling out to scripts.


### 1.2 Terraform second (once Flask behaviour is stable)
Once the local workflow is correct, Terraform should provision infrastructure around a known app.

#### 1.2.1 Minimal AWS architecture for the ITF site
**A cost-controlled, portfolio-friendly baseline:**
- `ALB` (Application Load Balancer) (HTTP(S) entry point)
- `EC2` (Flask + Gunicorn + Nginx) or `ECS Fargate` (optional upgrade)
- `RDS PostgreSQL` (or `MySQL` if already standardised)
- `S3` (static assets, optional evidence/screenshots)
- `Route 53` + `ACM` (AWS Certificate Manager) for TLS
- `VPC` with public + private subnets (and no `NAT` if `endpoints/SSM` approach is preferred)
Terraform then becomes a deployment wrapper, not the place where core application behaviour is discovered.

**When Terraform first makes sense**
Terraform-first only makes sense if the app is already stable and only deployment is missing. 
Here, the missing pieces are still application-side (skeleton matches, result entry, winner propagation), so Flask-first is the higher-leverage step.

**Concrete “next deliverable”**
The next concrete deliverable should be one of the following (choose one path, then proceed):
- A. Flask skeleton: routes + templates + DB calls for the workflow (registration → generate draw → enter result → public draw view).
- B. Service layer first: implement entry_service/draw_service/match_service and keep Flask thin.
If the goal is speed, route-first works; if the goal is maintainability, service-layer-first works.

**What Flask will do in this project:**
Flask is the web application layer that sits between:
- Front end: HTML pages/forms (browser)
- Back end: PostgreSQL tables + Python logic (draw generation, validation, winner propagation, points/rankings recalculation)

Flask is not a “front-end checker”. Flask is the server that:
- serves pages (routes such as `/tournaments`, `/draw/217`, `/admin/result/…`)
- accepts form submissions (POST requests)
- validates inputs (using the existing validation logic, e.g. `validate_tennis_matches.py`)
- writes to the database (insert/update in `Entries`, `Draws`, `DrawPlayers`, `Matches`)
- queries the database and renders the `draw/ranking` views

**What “front end working” means here**
In this architecture, “front end working” means:
- Pages load without error (HTTP 200, not 500)
- Data shown on the page matches the database (correct draw, correct players, correct scores)
- Form submissions succeed and persist data (new entry, new result, etc.)
- Validation blocks invalid inputs (bad score formats, impossible results)
- The bracket updates correctly after a result (winner advances)
So Flask is what makes “front end ↔ database” actually function.

**Will it be obvious when it is working?**
Yes—because Flask produces concrete, testable outcomes.

A) Browser-visible checks
- Visiting a route shows the expected page content (tournament list, draw bracket, rankings).
- Submitting a form shows a success page / redirect and the updated data appears on refresh.

B) Database checks (proof)
Each UI action corresponds to a database change that can be verified with SQL.

**Examples:**
After “register entry”:
```bash
SELECT *
FROM public.entries
WHERE tournament_id = 55
ORDER BY created_at DESC
LIMIT 5;
```

After “enter result”:
```bash
SELECT match_id, draw_id, round_id, player1_id, player2_id, winner_id, match_status_id,
       set1_p1, set1_p2, set2_p1, set2_p2, set3_p1, set3_p2
FROM public.matches
WHERE draw_id = 217
ORDER BY round_id, match_number;
```

After “result entered”, winner propagated:
The next-round match row should now contain the winner in the correct slot.

C) Flask logs (diagnostic)
If something fails, Flask will show:
- a stack trace in development mode, and/or
- structured server logs (when configured)
- That makes failures actionable: route error vs validation error vs database constraint error.

**What Flask will NOT do automatically**
- Flask will not “know” the bracket logic unless that logic is coded (winner propagation, skeleton generation).
- Flask will not validate tennis scoring unless the validator is called.
- Flask will not design a complex front end; it will serve templates (HTML) and accept inputs.

**Practical definition of “working” (minimum acceptance tests)**
A Flask app is “working” for this project when the following are true:
- Tournament list loads from DB.
- A draw view renders the bracket from DB (not hardcoded).
- An admin result form updates a match row.
- The winner advances to the next round automatically.
- The draw can be marked completed when the final is completed.
- Recalculation scripts can be triggered (manual route or CLI) and results appear in PointsHistory / WeeklyRanking.
If those pass, the app is operational end-to-end.

**Note on files**
The currently available source files in this chat are the uploaded `*.py scripts`. 
The `*.pyc` and `__pycache__` artefacts are not used for edits.



**Why B fits this project (service layer first)**
- Correctness first: winner propagation, match skeleton creation, and result validation are the hard parts; UI can be thin.
- Reusability: the same functions can be used by Flask routes, CLI admin commands, and future batch jobs.
- Design later is easy: HTML/templates can be changed without touching the core logic, as long as the service functions’ inputs/outputs stay stable.

**What “design later” means in practice:**
Once entry_service, draw_service, and match_service exist and are tested:
- Templates can be replaced or restyled freely.
- Routes can be reorganised.
- Admin pages can be added without rewriting the computation rules.

**Immediate next step under B**
Create three new modules (names indicative) and keep existing scripts as wrappers:
- `entry_service.py`
- `create_entry(...)` (deadline checks + insert)
- `draw_service.py`
- `generate_draw_from_entries(...)` (create draw + draw players)
- `match_service.py`
- `create_match_skeleton(...)`
- `apply_result_and_advance(...)` (validate + update + propagate)

Then Flask becomes a lightweight layer that calls these functions.


**Install Flask:**
```bash
python3 -m pip install flask
```

**Check if it is installed:**
```bash
python3 -m pip show flask || echo "Flask NOT installed in this venv"
```

**Running Flask:**
```bash
python3 app.py
```
**Checking 3 websites:**
- http://127.0.0.1:5000/tournaments : whole list of tournaments but MT100 Senior Hamburg added in Week 1 2025!
- http://127.0.0.1:5000/draw/217 : working but how come that so many players "withdrew and didn't show"?
- http://127.0.0.1:5000/admin : front UI to create entry, generate draw, create match skeleton, submit result

