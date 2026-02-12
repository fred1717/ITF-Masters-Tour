# ITF Tournament Timing Rules & Automation Requirements

## Timeline Summary

### Tournament Week Timing (Example: Tournament starts Monday, Jan 20)

```
WEEK BEFORE TOURNAMENT (Week of Jan 13-19):
├─ Tuesday, Jan 14, 10:00 GMT
│  └─ Entry Deadline (last chance to register)
│     └─ Final Entry List Published immediately
│        - No more wildcards after this
│        - For simplicity in your project
│
└─ Friday, Jan 17, 20:00 GMT (SAME WEEK as Tuesday)
   └─ Draw Published
      - Seeding completed
      - Positions assigned  
      - Players notified via SMS

TOURNAMENT WEEK (Week of Jan 20-26):
├─ Monday, Jan 20 - Tournament Starts
├─ Tuesday-Saturday - Matches played
└─ Friday/Saturday/Sunday - Tournament Ends (any day in this week)

FOLLOWING WEEK (Week of Jan 27+):
├─ Monday, Jan 27, 00:01 GMT
│  └─ Points Added to Ranking
│     - Automated via Lambda
│     - Best 4 results calculated
│     - PointsHistory updated
│
└─ Monday, Jan 27, 19:00 GMT
   └─ Weekly Ranking Published
      - WeeklyRanking table updated
      - Players ordered by total_points (best 4)
      - Separate rankings per age category & gender
      - Available on website
```

## Automation Schedule

### 1. Entry Deadline Check (Tuesday 10:00 GMT)

**EventBridge Schedule**: `cron(0 10 ? * TUE *)`

**Lambda Function**: `check_entry_deadline()`

```python
def check_entry_deadline(event, context):
    """
    Runs every Tuesday at 10:00 GMT
    - Closes entries for tournaments with deadline = today
    - Publishes final entry list
    - Triggers seeding calculation
    """
    current_datetime = datetime.now(timezone.utc)
    
    # Find all draws with entry_deadline = today at 10:00
    draws = db.execute("""
        SELECT draw_id, tournament_id, age_category, gender
        FROM Draws
        WHERE DATE(entry_deadline) = DATE(%s)
        AND HOUR(entry_deadline) = 10
        AND draw_status = 'Scheduled'
    """, (current_datetime,))
    
    for draw in draws:
        # 1. Mark draw as ready for seeding
        db.execute("""
            UPDATE Draws
            SET draw_status = 'Entry Closed'
            WHERE draw_id = %s
        """, (draw['draw_id'],))
        
        # 2. Calculate seeding
        db.execute("CALL CalculateDrawSeeding(%s)", (draw['draw_id'],))
        
        # 3. Publish entry list (send notifications)
        publish_entry_list(draw['draw_id'])
        
        # 4. Schedule draw publication for Friday
        schedule_draw_publication(draw['draw_id'])
```

### 2. Draw Publication (Friday 19:00 GMT)

**EventBridge Schedule**: `cron(0 20 ? * FRI *)`

**Lambda Function**: `publish_draws()`

```python
def publish_draws(event, context):
    """
    Runs every Friday at 20:00 GMT
    - Publishes draws for tournaments starting NEXT WEEK (Monday-Sunday)
    - Generates draw positions
    - Sends SMS notifications to all players
    """
    current_datetime = datetime.now(timezone.utc)
    
    # Calculate next week's range (Monday-Sunday)
    # If today is Friday, Jan 17, next week starts Monday, Jan 20
    days_until_next_monday = (7 - current_datetime.weekday()) if current_datetime.weekday() < 6 else 1
    next_monday = current_datetime.date() + timedelta(days=days_until_next_monday)
    next_sunday = next_monday + timedelta(days=6)
    
    # Find tournaments starting next week
    tournaments = db.execute("""
        SELECT t.tournament_id, t.start_date, d.draw_id
        FROM Tournaments t
        JOIN Draws d ON t.tournament_id = d.tournament_id
        WHERE t.start_date BETWEEN %s AND %s
        AND d.draw_status = 'Entry Closed'
    """, (next_monday, next_sunday))
    
    for tournament in tournaments:
        # 1. Generate draw positions
        generate_draw_positions_complete(tournament['draw_id'])
        
        # 2. Create first round matches
        create_first_round_matches(tournament['draw_id'])
        
        # 3. Update draw status
        db.execute("""
            UPDATE Draws
            SET draw_status = 'In Progress',
                draw_generated_at = %s
            WHERE draw_id = %s
        """, (current_datetime, tournament['draw_id']))
        
        # 4. Send SMS to all players
        notify_all_players_draw_published(tournament['draw_id'])
```

### 3. Points Processing (Monday 0:01 UTC)

**EventBridge Schedule**: `cron(1 0 ? * MON *)`

**Lambda Function**: `process_weekly_points()`

```python
def process_weekly_points(event, context):
    """
    Runs every Monday at 0:01 UTC
    - Processes all tournaments that ended in previous week
    - Adds points to PointsHistory
    - Marks best 4 results for each player
    """
    # Calculate previous week range (Mon-Sun)
    today = datetime.now(timezone.utc).date()
    last_monday = today - timedelta(days=today.weekday() + 7)
    previous_sunday = last_monday + timedelta(days=6)
    
    # Find completed tournaments from last week
    tournaments = db.execute("""
        SELECT tournament_id, end_date, category_id
        FROM Tournaments
        WHERE end_date BETWEEN %s AND %s
        AND points_processed = FALSE
    """, (last_monday, previous_sunday))
    
    for tournament in tournaments:
        # Get all draws for this tournament
        draws = get_tournament_draws(tournament['tournament_id'])
        
        for draw in draws:
            # Process all matches and award points
            process_draw_points(draw['draw_id'], tournament)
        
        # Mark tournament as processed
        db.execute("""
            UPDATE Tournaments
            SET points_processed = TRUE
            WHERE tournament_id = %s
        """, (tournament['tournament_id'],))
    
    # Update best 4 status for all players
    update_all_players_best_4()
```

### 4. Weekly Ranking Publication (Monday 20:00 GMT)

**EventBridge Schedule**: `cron(0 20 ? * MON *)`

**Lambda Function**: `publish_weekly_rankings()`

```python
def publish_weekly_rankings(event, context):
    """
    Runs every Monday at 20:00 UTC
    - Generates official weekly rankings
    - Inserts into WeeklyRanking table
    - Orders players by total_points (best 4 results)
    - Separate rankings per age category & gender
    """
    current_date = datetime.now(timezone.utc)
    ranking_year = current_date.year
    ranking_week = current_date.isocalendar()[1]  # ISO week number
    
    # Get all age categories and genders
    categories = db.execute("SELECT age_category_id FROM AgeCategory")
    genders = db.execute("SELECT gender_id FROM Gender")
    
    for category in categories:
        for gender in genders:
            # Get current points for all players in this category/gender
            rankings = db.execute("""
                SELECT 
                    pcp.player_id,
                    pcp.age_category_id,
                    p.gender,
                    pcp.total_points,
                    RANK() OVER (ORDER BY pcp.total_points DESC) as rank_position
                FROM PlayerCurrentPoints pcp
                JOIN Players p ON pcp.player_id = p.player_id
                WHERE pcp.age_category_id = %s
                AND p.gender = %s
                ORDER BY pcp.total_points DESC
            """, (category['age_category_id'], gender['gender_id']))
            
            # Insert into WeeklyRanking table
            for ranking in rankings:
                db.execute("""
                    INSERT INTO WeeklyRanking 
                    (player_id, age_category_id, gender_id, ranking_year, 
                     ranking_week, total_points, rank_position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    total_points = VALUES(total_points),
                    rank_position = VALUES(rank_position)
                """, (
                    ranking['player_id'],
                    ranking['age_category_id'],
                    gender['gender_id'],
                    ranking_year,
                    ranking_week,
                    ranking['total_points'],
                    ranking['rank_position']
                ))
    
    # Optional: Send notification that rankings are published
    send_ranking_publication_notification()
    
    return {
        'statusCode': 200,
        'body': f'Rankings published for week {ranking_week}, year {ranking_year}'
    }
```

## Database Fields Required

### Already in Schema ✅
- `Draws.entry_deadline` (DATETIME)
- `Draws.draw_generated_at` (DATETIME)
- `Draws.draw_status` (ENUM)

### Need to Add ✅
```sql
ALTER TABLE Tournaments ADD COLUMN points_processed BOOLEAN DEFAULT FALSE;
```

## Calculation Examples

### Example 1: Tournament Jan 20-26 (starts Monday, ends Saturday)

| Event | Date/Time | Notes |
|-------|-----------|-------|
| Entry Deadline | Tue, Jan 14, 10:00 GMT | Week before tournament |
| Seeding Complete | Tue, Jan 14, 10:05 GMT | Automatic after deadline |
| Draw Published | Fri, Jan 17, 19:00 GMT | **Same week** as Tuesday |
| Tournament Starts | Mon, Jan 20 | First matches |
| Tournament Ends | Sat, Jan 26 | Finals completed |
| Points Processed | Mon, Jan 27, 00:01 GMT | Best 4 calculated |
| Rankings Published | Mon, Jan 27, 20:00 GMT | Official rankings live |

**Week Timeline:**
- Week of Jan 13-19: Entry closes Tuesday, Draw published Friday
- Week of Jan 20-26: Tournament runs
- Week of Jan 27+: Points added Monday 00:01, Rankings published Monday 20:00

### Example 2: Tournament Feb 3-9 (starts Monday, ends Sunday)

| Event | Date/Time | Notes |
|-------|-----------|-------|
| Entry Deadline | Tue, Jan 28, 10:00 GMT | Week before tournament |
| Seeding Complete | Tue, Jan 28, 10:05 GMT | Automatic |
| Draw Published | Fri, Jan 31, 19:00 GMT | **Same week** as Tuesday |
| Tournament Starts | Mon, Feb 3 | Competition begins |
| Tournament Ends | Sun, Feb 9 | Finals |
| Points Processed | Mon, Feb 10, 00:01 GMT | Best 4 calculated |
| Rankings Published | Mon, Feb 10, 20:00 GMT | Official rankings live |

**Week Timeline:**
- Week of Jan 27-Feb 2: Entry closes Tuesday, Draw published Friday
- Week of Feb 3-9: Tournament runs  
- Week of Feb 10+: Points added Monday 00:01, Rankings published Monday 20:00

## Helper Functions

### Calculate Entry Deadline from Tournament Start

```python
def calculate_entry_deadline(tournament_start_date):
    """
    Entry deadline is Tuesday 10:00 GMT of the week before tournament starts.
    
    Args:
        tournament_start_date: Date when tournament starts (usually Monday)
    
    Returns:
        datetime: Tuesday 10:00 GMT of previous week
    """
    # Get Monday of tournament week
    days_since_monday = tournament_start_date.weekday()
    tournament_monday = tournament_start_date - timedelta(days=days_since_monday)
    
    # Go back to previous week's Tuesday
    previous_tuesday = tournament_monday - timedelta(days=6)  # 6 days before Monday
    
    # Set time to 10:00 GMT
    entry_deadline = datetime.combine(
        previous_tuesday,
        time(10, 0, 0),
        tzinfo=timezone.utc
    )
    
    return entry_deadline

# Example usage:
tournament_start = date(2026, 1, 20)  # Monday, Jan 20
deadline = calculate_entry_deadline(tournament_start)
# Returns: 2026-01-14 10:00:00 GMT (Tuesday, Jan 14)
```

### Calculate Draw Publication Time from Tournament Start

```python
def calculate_draw_publication_time(tournament_start_date):
    """
    Draw is published Friday 20:00 GMT of the week before tournament starts.
    
    Args:
        tournament_start_date: Date when tournament starts
    
    Returns:
        datetime: Friday 20:00 GMT of previous week
    """
    # Get Monday of tournament week
    days_since_monday = tournament_start_date.weekday()
    tournament_monday = tournament_start_date - timedelta(days=days_since_monday)
    
    # Go back to previous week's Friday
    previous_friday = tournament_monday - timedelta(days=3)  # 3 days before Monday
    
    # Set time to 20:00 GMT
    draw_publication = datetime.combine(
        previous_friday,
        time(20, 0, 0),
        tzinfo=timezone.utc
    )
    
    return draw_publication

# Example usage:
tournament_start = date(2026, 1, 20)  # Monday, Jan 20
publication = calculate_draw_publication_time(tournament_start)
# Returns: 2026-01-17 20:00:00 GMT (Friday, Jan 17)
```

## When Creating New Tournaments

```python
def create_tournament_with_draw(
    name, start_date, end_date, venue_id, category_id,
    age_category_id, gender_id
):
    """
    Creates a tournament and its draw with proper timing.
    """
    # 1. Create tournament
    tournament_id = db.execute("""
        INSERT INTO Tournaments 
        (name, start_date, end_date, venue_id, category_id, ...)
        VALUES (%s, %s, %s, %s, %s, ...)
    """, (name, start_date, end_date, venue_id, category_id, ...))
    
    # 2. Calculate deadlines
    entry_deadline = calculate_entry_deadline(start_date)
    
    # 3. Create draw with deadline
    draw_id = db.execute("""
        INSERT INTO Draws 
        (tournament_id, age_category, gender, entry_deadline, draw_status, ...)
        VALUES (%s, %s, %s, %s, 'Scheduled', ...)
    """, (tournament_id, age_category_id, gender_id, entry_deadline, ...))
    
    return tournament_id, draw_id
```

## Summary

**Schema Changes Needed**: Just add `points_processed` to Tournaments

**Automation Required**: 4 EventBridge schedules:
1. Tuesday 10:00 GMT - Entry deadline & seeding
2. Friday 19:00 GMT - Draw publication  
3. Monday 00:01 GMT - Points processing
4. Monday 20:00 GMT - Weekly ranking publication

**All timing is handled in application tier** - the schema just stores the timestamps!
