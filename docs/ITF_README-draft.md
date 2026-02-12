PROJECTS OBJECTIVES:
Your team is tasked with designing, deploying, and testing a highly durable N-tier application on AWS.
The application should have the following characteristics:
- A simple web front-end (static or dynamic - your choice)
- A MySQL Amazon RDS backend
- Terraform to deploy resources
- High durability and availabilitywith failover to a disaster recovery (DR) region.

ARCHITECTURE REQUIREMENTS:
1. Web Tier
    - Static web page hosted on EC2, S3 (static), or Load Balanced EC2 Auto Scaling Group.
    - Must connect to backend via internal endpoint or API - (optional)

2. Application Tier (optional)
   Lambda function or EC2 instance(s) running application logic (can be simple PHP, Node.js, Python Flask, etc...)

3. Database Tier
    - MySQL RDS instance (or Aurora serverless).
    - Set to Multi-AZ deployment for high availability in the primary region.
    - If separate, must be hosted on EC2, Load Balanced EC2 Auto Scaling Group, or Lambda.

4. Disaster Recovery (DR) Strategy (automatic failover with cross-region replication):
    - Deploy a disaster recovery stack in a secondary AWS region.
    - Implement cross-region replication of your primary MySQL database.
    - Design your DNS failover using Amazon Route 53 with health checks to detect failures in the primary region and route traffic to the DR region when necessary.
    - Web and App tiers must also be deployed and ready to serve traffic in the DR region.
    - Simulate a primary region failure and demonstrate failover with data integrity preserved via replication.

ITF
RDS MySQL or Aurora serverless for DR? > I need automatic failover, serverless, and multi-AZ. Aurora seems to be the only option > how much will it cost?


The work was done in a Docker container with PostgreSQL database, locally on my computer, using Docker, PyCharm and DataGrip.

The Excel file 'ITF-tables.xlsx' is the file I populated myself with all tables. See on GitHub.
Claude completed the Excel file, which became 'ITF-tables-CLEANED.xlsx', by filling in the missing tables. It needed to be checked and amended several times during the following 24 hours, due to wrong outputs. 
See 'sql' folder, PyCharm project.




ARCHITECTURE FOR IMPLEMENTING TOURNAMENT WORKFLOW WITH VALIDATION SCRIPTS
My question:
I would like to know how you will implement the changes for draw_status_id and match_status_id for future tournaments? 
Will it happen on the website with a button triggering a Python file that will change the values of these fields in the database?

Good question - this requires thinking about the live system workflow, not just historical data validation.
Status Transition Strategy
DrawStatus Transitions
Automated (EventBridge scheduled tasks):

Open → Closed: Tuesday 10:00 UTC (entry deadline)

EventBridge trigger → Lambda checks all draws with status_id=1
If num_players >= 6: Update to Closed (2)
If num_players < 6: Update to Cancelled (5)


Generated → Completed: After last match finishes

Triggered by match score entry
Lambda checks: "Are all matches in this draw completed?"
If yes: Update draw to Completed (4)



Manual (Website buttons):
3. Closed → Generated: Referee clicks "Generate Draw" button

Available: Tuesday 10:00 - Friday 23:59
Triggers Lambda that:

Creates DrawPlayers with seeding
Creates Matches (all status_id=1 Scheduled)
Updates draw to Generated (3)



MatchStatus Transitions
Manual (Website interface):

Scheduled → Completed: Scorekeeper enters final score

Form with set scores, tiebreaks, supertiebreak
Triggers Lambda that:

Validates score (using validate_tennis_matches.py logic)
Updates match to Completed (2)
Checks if all draw matches complete → Updates draw status to Completed (4)




Scheduled → Walkover/Retired/Cancelled: Referee action

Dropdown: "Mark as Walkover/Retired/Cancelled"
Lambda updates match status
For Walkover: Auto-advances winner to next round



Implementation Architecture
Website Button → API Gateway → Lambda Function → Update Database
                                      ↓
                              Validation Script
                              (Python logic)
Lambda Functions needed:

close_entries_at_deadline (EventBridge cron)
generate_tournament_draw (Button trigger)
submit_match_score (Form submission)
mark_match_special_status (Walkover/Retired/Cancelled)
check_draw_completion (Called after match updates)

Python validation files role:

Imported as modules into Lambda functions
Provide validation logic (don't directly update DB)
Example: validate_tennis_matches.py → used by submit_match_score Lambda

Key Question for You
Do you want validation scripts to:

Just validate (return True/False + errors) → Lambda handles DB updates
Validate AND update (scripts contain SQL UPDATE statements)

I recommend Option 1 - separation of concerns:

Python scripts: Pure validation logic
Lambda functions: Orchestration + DB updates
Keeps scripts testable and reusable



**ALL VALIDATION FILES:**
**Files to Update (6 total)**
*`validate_tennis_matches.py`* - Master validation for match data
*`generate_entries.py`* - Entry creation with proper deadline logic
*`generate_draw_players.py`* - Draw generation with correct seeding
*`generate_matches.py`* - Match creation with status support
*`calculate_points_history.py`* - Points calculation with first-match detection
*`calculate_weekly_ranking.py`* - Weekly ranking calculation (review only)

**New File to Create (1)**
*`validate_itf_data.py`* - Master validation orchestrator for all data



**How to use all three AI models without hitting quotas**
**Claude Pro**
Main “system architect” and reviewer for long docs, schema, and complex logic.

**ChatGPT Plus**
Fast code and SQL generator for concrete tasks (Lambda functions, stored procedures, test data generators).

**Perplexity Pro**
Targeted research and validation layer: 
- real‑world rules
- best practices
- cost checks
- “does this design match how others do it?” 
- file‑based QA.
​
