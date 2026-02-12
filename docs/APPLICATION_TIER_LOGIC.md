# ITF Tournament Business Logic - Application Tier Implementation

## Overview
This document explains the business logic that will be implemented in the **application tier** (Lambda functions) rather than in the database schema. The schema already supports all these features.

---

## Frontend Architecture

### Static Website (S3)

The frontend is a simple static website hosted on S3:

**Stack:** HTML + CSS + JavaScript (vanilla or React)

**Key Pages:**
- `/index.html` - Home page with tournament list
- `/tournaments.html` - Available tournaments
- `/players.html` - Player search and profiles
- `/rankings.html` - Current rankings by category
- `/draws.html` - Tournament draws

**API Integration:**
```javascript
// Example: Player enrollment
async function enrollInTournament(tournamentId, playerId) {
  const response = await fetch(`https://api.awscloudcase.com/tournaments/${tournamentId}/enter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: playerId })
  });
  return response.json();
}
```

**S3 Configuration:**
- Static website hosting enabled
- Bucket policy allows public read
- Connected to API Gateway via CORS

### CloudFront (Optional CDN) ⚠️

**Status: OPTIONAL - Recommended for production only**

**Without CloudFront (Portfolio/Demo):**
```
Users → Route 53 → S3 Static Website → API calls to API Gateway
```
- ✅ Simpler setup
- ✅ Lower cost ($5/month savings)
- ✅ Sufficient for demonstration
- ❌ No global CDN
- ❌ Slower for international users

**With CloudFront (Production):**
```
Users → Route 53 → CloudFront (Edge Locations) → S3 Static Website
                                               → API Gateway
```
- ✅ Global CDN (faster worldwide)
- ✅ HTTPS/SSL at edge locations
- ✅ DDoS protection (AWS Shield Standard)
- ✅ Caching reduces S3 costs at scale
- ✅ Custom domain with SSL certificate (ACM)
- ❌ Additional $5/month cost
- ❌ Slightly more complex setup

**CloudFront Configuration (if using):**
```hcl
# Terraform snippet
resource "aws_cloudfront_distribution" "website" {
  origin {
    domain_name = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.website.id}"
  }
  
  enabled             = true
  default_root_object = "index.html"
  
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.website.id}"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }
  
  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.cert.arn
    ssl_support_method  = "sni-only"
  }
}
```

**Recommendation:**
- **For this portfolio project:** Skip CloudFront initially
- **For production / if showcasing CDN knowledge:** Add CloudFront

---

## 1. Points Addition Timing

### Rule
Points are added on the **Monday following the tournament end date**, regardless of whether the tournament ended Friday, Saturday, or Sunday.

### Implementation Strategy

**Option A: Scheduled Lambda (Recommended)**
```python
# Lambda triggered every Monday at 00:01 UTC via EventBridge
def process_weekly_points(event, context):
    # Get all tournaments that ended in previous week (Mon-Sun)
    last_monday = get_last_monday()
    previous_sunday = last_monday - timedelta(days=1)
    week_start = previous_sunday - timedelta(days=6)
    
    # Query tournaments
    tournaments = db.execute("""
        SELECT tournament_id, end_date, category_id
        FROM Tournaments
        WHERE end_date BETWEEN %s AND %s
        AND points_processed = FALSE
    """, (week_start, previous_sunday))
    
    for tournament in tournaments:
        # Process all matches from this tournament
        process_tournament_points(tournament)
        
        # Mark as processed
        db.execute("""
            UPDATE Tournaments 
            SET points_processed = TRUE 
            WHERE tournament_id = %s
        """, (tournament['tournament_id'],))
```

**Schema Addition Needed**:
```sql
ALTER TABLE Tournaments ADD COLUMN points_processed BOOLEAN DEFAULT FALSE;
```

**EventBridge Schedule**: `cron(1 0 ? * MON *)`  
*(Runs every Monday at 00:01 UTC)*

---

## 1b. Weekly Ranking Publication

### Rule
Official weekly rankings are published every **Monday at 20:00 GMT**, calculated from the best 4 results over the last 12 months.

### Implementation Strategy

**Scheduled Lambda**
```python
# Lambda triggered every Monday at 20:00 UTC via EventBridge
def publish_weekly_rankings(event, context):
    """
    Generates and publishes official weekly rankings.
    Uses PlayerCurrentPoints view which automatically calculates best 4.
    """
    current_date = datetime.now(timezone.utc)
    ranking_year = current_date.year
    ranking_week = current_date.isocalendar()[1]  # ISO week number
    
    # Get all age categories and genders
    categories = db.execute("SELECT age_category_id FROM AgeCategory")
    genders = db.execute("SELECT gender_id FROM Gender")
    
    for category in categories:
        for gender in genders:
            # Get current rankings using the view
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
    
    return {
        'statusCode': 200,
        'body': f'Rankings published for week {ranking_week}, year {ranking_year}'
    }
```

**EventBridge Schedule**: `cron(0 20 ? * MON *)`  
*(Runs every Monday at 20:00 UTC)*

---

## 2. Seeding Rules Clarification

### Actual ITF Rules
- **8-player draw**: 2 seeds
- **16-player draw**: 4 seeds
- **32-player draw**: 8 seeds
- **64-player draw**: 16 seeds
- **128-player draw**: 32 seeds

**Formula**: `num_seeds = draw_size ÷ 4`

### Correct Data for SeedingRules Table
```sql
INSERT INTO SeedingRules VALUES
(1, 1, 8, 2),      -- Up to 8 players → 8-draw → 2 seeds
(2, 9, 16, 4),     -- 9-16 players → 16-draw → 4 seeds
(3, 17, 32, 8),    -- 17-32 players → 32-draw → 8 seeds
(4, 33, 64, 16),   -- 33-64 players → 64-draw → 16 seeds
(5, 65, 128, 32);  -- 65-128 players → 128-draw → 32 seeds
```

The existing `CalculateDrawSeeding()` stored procedure already implements this correctly.

---

## 3. Draw Generation - Symmetric Bracket Rules

### Tennis Draw Symmetry Rules

A tennis draw is symmetric and follows specific placement rules to ensure top seeds cannot meet before their designated round.

#### Standard Seed Placement (for 32-draw with 8 seeds)

```
Position 1:  Seed 1    ┐
Position 2:  Unseeded  │── Seeds 1 & 2 can only meet in Final
...                    │
Position 16: Unseeded  ┘

Position 17: Unseeded  ┐
...                    │── Seeds 1 & 2 can only meet in Final  
Position 31: Unseeded  │
Position 32: Seed 2    ┘

Within top half:
Position 1:  Seed 1    ┐
...                    │── Seeds 1 & 3/4 can only meet in Semi
Position 8:  Unseeded  ┘

Position 9:  Seed 3/4  ┐  ← RANDOM: Either seed 3 or 4
...                    │── Seeds 1 & 3/4 can only meet in Semi
Position 16: Unseeded  ┘

Within bottom half:
Position 17: Seed 4/3  ┐  ← RANDOM: The other seed (4 or 3)
...                    │── Seeds 2 & 3/4 can only meet in Semi
Position 24: Unseeded  ┘

Position 25: Unseeded  ┐
...                    │── Seeds 2 & 3/4 can only meet in Semi
Position 32: Seed 2    ┘
```

### Implementation in Python

```python
def generate_draw_positions(draw_id, draw_size, seeds):
    """
    Generate symmetric draw positions.
    
    Args:
        draw_id: Draw identifier
        draw_size: 8, 16, 32, 64, or 128
        seeds: List of (player_id, seed_number, entry_points) tuples
    """
    positions = {}  # {position: player_id}
    
    # Step 1: Place fixed seeds (1 and 2)
    positions[1] = seeds[0][0]  # Seed 1 at position 1
    positions[draw_size] = seeds[1][0]  # Seed 2 at position draw_size
    
    # Step 2: Place seeds 3-4 (if 4+ seeds)
    if len(seeds) >= 4:
        # Randomly decide which half gets seed 3
        if random.choice([True, False]):
            positions[draw_size // 2] = seeds[2][0]  # Seed 3
            positions[draw_size // 2 + 1] = seeds[3][0]  # Seed 4
        else:
            positions[draw_size // 2] = seeds[3][0]  # Seed 4
            positions[draw_size // 2 + 1] = seeds[2][0]  # Seed 3
    
    # Step 3: Place seeds 5-8 (if 8+ seeds)
    if len(seeds) >= 8:
        quarter_positions = [
            draw_size // 4,
            draw_size // 4 + 1,
            3 * draw_size // 4,
            3 * draw_size // 4 + 1
        ]
        # Randomly shuffle seeds 5-8 into these positions
        random_seeds_5_8 = random.sample(seeds[4:8], 4)
        for pos, seed_info in zip(quarter_positions, random_seeds_5_8):
            positions[pos] = seed_info[0]
    
    # Step 4: Place seeds 9-16 (if 16+ seeds)
    if len(seeds) >= 16:
        eighth_positions = [
            draw_size // 8, 
            draw_size // 8 + 1,
            # ... calculate all 8 eighth positions
        ]
        random_seeds_9_16 = random.sample(seeds[8:16], 8)
        for pos, seed_info in zip(eighth_positions, random_seeds_9_16):
            positions[pos] = seed_info[0]
    
    # Step 5: Randomly place unseeded players
    unseeded_players = get_unseeded_players(draw_id)
    available_positions = [p for p in range(1, draw_size + 1) if p not in positions]
    random.shuffle(available_positions)
    
    for player_id, position in zip(unseeded_players, available_positions):
        positions[position] = player_id
    
    # Step 6: Update database
    for position, player_id in positions.items():
        db.execute("""
            UPDATE DrawPlayers
            SET draw_position = %s
            WHERE draw_id = %s AND player_id = %s
        """, (position, draw_id, player_id))
    
    # Step 7: Assign byes if needed
    num_players = len(seeds) + len(unseeded_players)
    if num_players < draw_size:
        assign_byes(draw_id, draw_size, num_players)
    
    return positions
```

### Bye Assignment Logic

```python
def assign_byes(draw_id, draw_size, num_players):
    """
    Assign byes to top seeds when draw is not full.
    
    ITF Rule: Top seeds get byes in first round.
    Number of byes = draw_size - num_players
    """
    num_byes = draw_size - num_players
    
    # Get top seeds
    top_seeds = db.execute("""
        SELECT player_id, seed_number
        FROM DrawSeed
        WHERE draw_id = %s
        ORDER BY seed_number ASC
        LIMIT %s
    """, (draw_id, num_byes))
    
    # Mark them as having byes
    for seed in top_seeds:
        db.execute("""
            UPDATE DrawPlayers
            SET has_bye = TRUE
            WHERE draw_id = %s AND player_id = %s
        """, (draw_id, seed['player_id']))
    
    # Create first round matches with NULL opponent
    for seed in top_seeds:
        create_bye_match(draw_id, seed['player_id'])
```

---

## 4. Random Seed Placement Examples

### Example 1: 32-Draw with 8 Seeds

**Seeds 1-2**: Fixed positions
- Seed 1 → Position 1
- Seed 2 → Position 32

**Seeds 3-4**: Random within halves
- **Option A**: Seed 3 → Pos 16, Seed 4 → Pos 17
- **Option B**: Seed 4 → Pos 16, Seed 3 → Pos 17

**Seeds 5-8**: Random within quarters
- 4 quarter positions: 8, 9, 24, 25
- Seeds 5-8 randomly shuffled into these

### Example 2: 16-Draw with 4 Seeds

**Seeds 1-2**: Fixed
- Seed 1 → Position 1
- Seed 2 → Position 16

**Seeds 3-4**: Random within halves
- **Option A**: Seed 3 → Pos 8, Seed 4 → Pos 9
- **Option B**: Seed 4 → Pos 8, Seed 3 → Pos 9

---

## 5. Complete Draw Generation Workflow

```python
def complete_draw_generation(draw_id):
    """
    Full workflow for generating a tournament draw.
    """
    # 1. Get draw details
    draw = get_draw_details(draw_id)
    
    # 2. Determine draw_size based on num_players
    draw_size = calculate_draw_size(draw['num_players'])
    update_draw_size(draw_id, draw_size)
    
    # 3. Calculate seeding (already done via stored procedure)
    # CALL CalculateDrawSeeding(draw_id) - executed earlier
    
    # 4. Get seeds
    seeds = get_draw_seeds(draw_id)
    
    # 5. Generate positions
    positions = generate_draw_positions(draw_id, draw_size, seeds)
    
    # 6. Create first round matches
    create_first_round_matches(draw_id, draw_size, positions)
    
    # 7. Mark draw as generated
    db.execute("""
        UPDATE Draws
        SET draw_generated_at = NOW(),
            draw_status = 'In Progress'
        WHERE draw_id = %s
    """, (draw_id,))
    
    return True

def calculate_draw_size(num_players):
    """Calculate next power of 2 >= num_players."""
    sizes = [8, 16, 32, 64, 128]
    for size in sizes:
        if num_players <= size:
            return size
    return 128
```

---

## 6. SMS Notification Integration

### When to Send Notifications

1. **Draw published**: Notify all players of their position and opponent
2. **Match result entered**: Notify both players
3. **Next round match**: Notify players of next opponent
4. **Tournament completion**: Notify of final result and points earned

### Implementation with SNS via VPC Endpoint

**Important**: Lambda functions are in private subnets with **NO internet access**. Instead of using a NAT Gateway, we use an **SNS VPC Endpoint** which is more cost-effective and secure.

#### VPC Endpoint Configuration

```python
# Lambda accesses SNS through VPC endpoint - no internet required
# The VPC endpoint is configured in Terraform:
# - Interface endpoint for SNS service
# - Deployed in private subnets
# - Connected via AWS PrivateLink (AWS backbone network)
```

#### SNS Integration Code

```python
import boto3

# SNS client - automatically uses VPC endpoint when Lambda is in VPC
sns = boto3.client('sns', region_name='us-east-1')

def send_draw_notification(player_id, draw_id):
    """
    Send SMS when draw is published.
    Uses SNS VPC endpoint - no NAT Gateway needed.
    """
    # Get player details
    player = get_player_details(player_id)
    draw_info = get_player_draw_info(draw_id, player_id)
    
    # Validate phone number exists
    if not player.get('phone_number'):
        print(f"Player {player_id} has no phone number")
        return
    
    message = f"""
ITF Tournament Draw Published!

Tournament: {draw_info['tournament_name']}
Your Position: {draw_info['position']}
Seed: {draw_info['seed_number'] if draw_info['is_seeded'] else 'Unseeded'}
First Match: vs {draw_info['opponent_name']}

Good luck!
"""
    
    # Send via SNS (routed through VPC endpoint)
    try:
        response = sns.publish(
            PhoneNumber=player['phone_number'],  # Format: +33612345678
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'  # Higher priority delivery
                }
            }
        )
        print(f"SMS sent to {player_id}: {response['MessageId']}")
    except Exception as e:
        print(f"Failed to send SMS to {player_id}: {str(e)}")

def send_result_notification(match_id):
    """
    Send SMS when match result is entered.
    """
    match = get_match_details(match_id)
    
    for player_id in [match['player1_id'], match['player2_id']]:
        player = get_player_details(player_id)
        
        if not player.get('phone_number'):
            continue
        
        is_winner = (player_id == match['winner_id'])
        message = f"""
Match Result Recorded

Tournament: {match['tournament_name']}
Result: {'You won!' if is_winner else 'Match lost'}
Score: {match['score']}
"""
        
        try:
            sns.publish(
                PhoneNumber=player['phone_number'],
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
        except Exception as e:
            print(f"Failed to send SMS: {str(e)}")

def send_ranking_publication_notification():
    """
    Optional: Notify top players when rankings are published.
    """
    # Get top 10 in each category
    top_players = db.execute("""
        SELECT player_id, rank_position
        FROM WeeklyRanking
        WHERE ranking_year = YEAR(CURDATE())
        AND ranking_week = WEEK(CURDATE())
        AND rank_position <= 10
    """)
    
    for player in top_players:
        player_details = get_player_details(player['player_id'])
        
        if player_details.get('phone_number'):
            message = f"""
ITF Rankings Updated!

Your current rank: #{player['rank_position']}

Congratulations!
"""
            try:
                sns.publish(
                    PhoneNumber=player_details['phone_number'],
                    Message=message
                )
            except Exception as e:
                print(f"Failed to send ranking SMS: {str(e)}")
```

#### Lambda IAM Policy for SNS via VPC Endpoint

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Network Architecture for SMS

```
Lambda (Private Subnet)
    ↓
SNS VPC Endpoint (Interface Endpoint in Private Subnet)
    ↓
AWS PrivateLink (AWS Backbone Network - not internet)
    ↓
SNS Service
    ↓
SMS to Player's Phone
```

**Key Points:**
- ✅ No NAT Gateway needed
- ✅ No internet access required
- ✅ More secure (traffic stays on AWS network)
- ✅ Lower cost (~$7.20/month for SNS endpoint vs ~$32/month for NAT Gateway)
- ✅ Better latency (AWS backbone faster than internet)

#### Player Phone Number Schema

You'll need to add phone numbers to the Players table:

```sql
ALTER TABLE Players ADD COLUMN phone_number VARCHAR(20);
-- Format: E.164 standard (e.g., +33612345678 for France)
```

#### SNS Cost Breakdown

**VPC Endpoint Cost:**
- Interface endpoint: $0.01/hour = $7.20/month
- Data processing: $0.01/GB (minimal for SMS)

**SMS Delivery Cost:**
- Transactional SMS: $0.00645/message (US/France)
- Varies by destination country

**Example Monthly Cost:**
- 100 SMS notifications: $0.65
- VPC endpoint: $7.20
- **Total: ~$7.85/month**

vs NAT Gateway approach:
- NAT Gateway: $32.40/month
- Data transfer: ~$5/month
- **Total: ~$37/month**

**Savings: ~$29/month using VPC endpoint!**

---

## Summary

### Schema is Complete ✅
No changes needed. The schema already supports:
- Tournament end dates for timing calculations
- Draw sizes and positions
- Seeding rules
- Player phone numbers (add if missing)

### Application Tier Needs ✅
1. **Lambda for weekly points processing** (Monday trigger)
2. **Lambda for draw generation** (with randomization logic)
3. **Lambda for SNS notifications** (SMS via AWS SNS)
4. **API endpoints** for:
   - Player entry
   - Match result entry
   - Draw display
   - Ranking display

### Next Steps
1. Deploy schema to RDS MySQL
2. Build Lambda functions for business logic
3. Create API Gateway endpoints
4. Set up SNS for notifications
5. Deploy to DR region
6. Build failover automation

The schema is ready. Now we build the application tier!
