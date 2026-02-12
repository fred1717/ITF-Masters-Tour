- You need to reach the required age during the calendar year of the competition (not on January 1st) to enter the competition in a particular age group.

- Each ranking is for one age group only. So, if a player belongs in a superior age group, he/she will not be entered in a lower age category (in that project only, not in real tennis events).

- If a player changes age category, he/she will start with 0 points in the new age category. 
- For example, if a player turns 65 in 2026, the points earned in 60+ will not carry over to the new age category 65+. 

- No player can play 2 matches in the same day (check match_date for each player in Matches table).

- players don't earn any point if they lose their first match. There must be a way to register whether each match is the first match played by either player.

- The entry deadline is every Tuesday at 10:00 UTC, for the tournament starting the following week.

- The draw will be published at the latest on the Friday following the entry deadline, at exactly 19:00 UTC. It can be published earlier, but not later.

- The weekly ranking, published every week on Monday at 20:00 UTC, includes the best 4 results over the previous 52 weeks: 
    - points earned before the previous 52 weeks must be deducted.
    - the number of tournaments played by each player over the last 52 weeks must be counted and sorted by the number of points earned, so the best 4 results in terms of points earned can be added.
    
- Players will be seeded according to the weekly ranking of the week preceding the tournament (for tournament in week 2, seeding according to ranking published on Monday of week 1).

- Byes will be assigned in order to complete the draw (fill in all the positions in the draw skeleton). 2 rules apply:
    - Seeded players: byes are assigned according to entry points.
    - Unseeded players: byes are assigned randomly.
        
    - 6-8 players: 
        - 6 players: 2 byes will be assigned, respectively to Seed 1 and Seed 2 to complete the 8 positions in the draw
        - 7 players: 1 bye will be assigned to Seed 1
        
    - 9-16 players (4 seeded players but the same logic applies). Examples:
        - Only 13 players: 3 byes assigned to Seed 1, Seed 2, Seed 3 in order to fill in the 16 positions
        - Only 10 players. This is an interesting case as there are only 4 seeds when the number of players ranges between 9 and 16. The 6 necessary byes will be assigned in that way:
            - 4 byes to the 4 seeded players
            - 2 byes assigned randomly to 2 unseeded players
            
    - 17-32 players (8 seeded players but the same logic applies). Examples:
        - Only 24 players: 8 byes needed to fill the 32 positions in the draw. Therefore, each of the 8 Seeds will get a bye
        - Only 20 players: 12 byes needed.
            - 8 assigned to each of the 8 seeds
            - 4 assigned randomly to 4 unseeded players
            
    - 33-64 players (16 seeded players but the same logic applies). Examples:
        - Only 48 players: 16 byes needed to fill the 64 positions in the draw. Therefore, each of the 16 Seeds will get a bye
        - Only 45 players: 19 byes needed.
            - 16 assigned to each of the 16 seeds
            - 3 assigned randomly to 3 unseeded players
            
    - For tournament_id 1 and 2: in the absence of seeded players (no weekly ranking available for these tournaments), all necessary byes can only be assigned randomly.
    



- There is an exception to that rule, only for the first 2 tournaments in the Tournaments table, which were held in 2025, Week 2 and 3. 
    The first weekly ranking was published on the Monday of Week 3 in 2025. Consequently, the first time it can really be used for seeding is for tournament_id = 3, week 4 in 2025.
    That means that tournament_id = 1 and tournament_id = 2 will have NO SEEDING.
- The seeding occurs the same week as the weekly ranking. An example would be that, for tournament being played in Week 2:
    - Weekly ranking published on Monday of Week 1, at 20:00 UTC
    - Entry Deadline on Tuesday of Week 1, at 10:00 UTC
    - Final Seeding implemented on the draw, on Friday of Week 1, at 19:00 UTC
    
- There must be at least 6 players in a draw for the tournament to be valid in that age and gender category (in this project only, normally at the discretion of the ITF referee).

- No more than 64 players in the same draw.

- Seeding rules: 
    - 6 to 8 players, 2 seeds. 9 to 16 players, 4 seeds. 17 to 32 players, 8 seeds. 33 to 64 players, 16 seeds. It must be validated against the SeedingRules table.
    - Seeds 1 and 2: the top 2 seeds are in either side of the draw and cannot meet before the final. 
    - Seeds 3 and 4: 
        - Seeds Nr 4 is on the same side of the draw as Seed 1. 
        - Seed 3 is on the same side of the draw as Seed 2. 
        - Seed 1 cannot meet Seed 4 before the semi-finals. 
        - Seed 2 cannot meet Seed 3 before the semi-finals. 
    - Seeds 5 to 8: 
        - Seeds 6 and 7 are on the same side of the draw as Seed 1. 
        - Seeds 5 and 8 are on the same side of the draw as Seed 2. 
        - None of Seeds 5-8 can meet the top 2 seeds before the quarter-finals.
        - None of Seeds 5-8 can meet the Seeds 3 or 4 before the last 16.
    - Seeds 9 to 16: 
        - Seeds 9, 12, 13, 16 are on the same side of the draw as Seed 1. 
        - Seeds 10,11, 14, 15 are on the same side of the draw as Seed 2. 
        - They cannot meet the top 2 seeds before the last 16.
        - They cannot meet Seeds 3-4 before the last 32.
        - They cannot meet Seeds 5 to 8 before the last 64 (in other words, they could meet one of them in the last 64, which could be the first round).
    - If a player withdraws or fails to show up after the draw is made, neither will the draw nor the seeding be modified. The consequence for the player will be the following:
        - he/she will lose the points earned in previous rounds, if any.
        - he/she will not be allowed to compete for the following 2 months (needs validation check)
    - If a player is disqualified:
        - he/she will lose the points earned in previous rounds, if any.
        - he/she will not be allowed to compete for the following 6 months (needs validation check)
   
        
- As soon as a match result is known, the admin (ITF referee or Tournament director) is able to update the draw on the UI front end (the result would appear on the draw skeleton).

- Each set follows standard tennis scoring rules:
  - In the first 2 sets, a player wins a set by winning at least 6 games with a margin of 2 games (e.g., 6-4, 7-5).
  - If the set reaches a 6-6 tie, a tie-break is played:
      - first to 7 points, win by 2. 
      - If both players are tied at 6-6, the tie-break will continue beyond 7 points until one of the two players wins by 2 points (8-6, 9-7, 10-8, 11-9, etc...)
      
- If each player wins a set (player 1 wins the first set, Player 2 the second set, or vice-versa), then a third set must be played. 

- The format of the third set depends on the draw rules, as determined by the value of Draws 'has_supertiebreak':
  - 'has_supertiebreak' = 0 (true in 25% cases): 
      - Normal third set: same rules as the first two sets (first to 6 games with a margin of 2, tie-break at 6-6)
      - This will apply to Men's +60: AgeCategory.age_category_id = 1 and Gender.gender.id = 11
  - If 'has_supertiebreak' = 1  (true in 75% cases): 
      - Super tie-break: instead of a full third set, a super tie-break is played where the first player to reach 10 points with a margin of 2 points wins the match.
      - If both players are tied at 9-9, the super-tiebreak continues until one players has won by 2 points (10-8, 11-9, 12-10, etc...).
      - This will apply to:
          - Men's +65 : AgeCategory.age_category_id = 2 and Gender.gender.id = 1
          - Ladies' +60: AgeCategory.age_category_id = 1 + Gender.gender.id = 2
          - Ladies' +65: AgeCategory.age_category_id = 2 + Gender.gender.id = 2


ADDITIONAL CHECKS: All checks (see above) must be, if possible, enforced at both database level (CHECK constraints) and also in validation scripts (Python files):
- Determine if a player is playing their first match by checking if they have any prior matches in the Matches table: a loss in the first match results in 0 points.
- Every scoring column in the `Matches` table (`set1_player1`, `set1_player2`, etc...) must be NULLABLE as a match can be cancelled or not come to completion (value of `match_status_id`).
- Not allowing a player who was suspended (PlayerStatus_status_id = 4) to compete for either 2 or 6 months: check on the Entries table.
    - 2 months if he/she barely didn't show up: `MatchStatus.match_status_id = 3`. If a player withdraws after the draw has been made, it is treated the same way (MatchStatus.match_status_id = 3).
    - 6 months if he/she was disqualified during the match: `MatchStatus.match_status_id = 6`.
- Ensure that a player who was suspended (`PlayerStatus_status_id = 4`) lose the benefit of the points earned in previous rounds of the same tournaments: 0 points to `PointsHistory` for this tournament.
- Disciplinary action triggers suspension for 2 or 6 months: `MatchStatus.match_status_id = 3` or `MatchStatus.match_status_id = 6`  (`Entries` table check)
- If a player retires during a match:
    - he doesn't lose the benefit of points earned in previous rounds.
    - there must be a check when generating match results:
        - if the player retires in set 1:
            - the score for set 1 could be 4-1 (for example), no score must be generated for the following sets.
            - the score could be 7-6 or 6-7 with a partial tie-break, if one player retires in the tie-break. Again, no score must be generated for the following sets.
        - if the player retires in set 2:
            - set 1 must be completed fully with a valid score.
            - the player could retire either in the middle of the second set (partial score)
            - the player could retire in the middle of the tie-break (7-6 or 6-7 in the second set)
        - if the player retires in the third set:
            - There must be a valid score in the first 2 sets.
            - the player could retire either in the middle of the third set (partial score, like 4-2 for example)
            - the player could retire in the middle of the tie-break (7-6 or 6-7 in the third set)
            - the player could retire in the middle of the super-tiebreak (partial score)



**`is_actual_seeding` (`DrawSeed`): only matters if between Entry deadline and the Draw = between Tuesday 10:00 UTC and Friday 19:00 UTC**
Distinguishes between:
- Planned seeding (based on rankings at entry deadline) - FALSE
- Actual seeding used (after withdrawals/substitutions) - TRUE

Example: Player #1 withdraws → everyone moves up one seed position 
The original seeding has `is_actual_seeding=FALSE`, the adjusted seeding has `is_actual_seeding=TRUE`. 
Preserves audit trail of seeding changes.

**RANDOM CALCULATIONS TO BE OBSERVED FOR ALL MATCHES (with a 5% error margin if the targeted percentage cannot be reached: 10% of 26 matches doesn't exist, that would be 2.6 matches)**
- In 0.1% cases (1 out of 1000), a player will default between the entry deadline and the draw, so the seeding could need to be adjusted (only if that player would have been seeded).

- In 0.5% cases, a player will not show up or defaut after the draw has been made (which will trigger a suspension of 2 months).

- In 0.2% cases, a player will be disqualified during a match (that also means the match started normally with 2 players).

- 2 times out of 3, the better ranked player (see WeeklyRanking) will win the match.

- 1 time out of 4 only, there will be a third set (whether normal or super-tie-break), which means that 2-set wins occur in 75% cases.
- For each normal set, there will be 10% tie-breaks only.
    - For all tie-breaks (first in 7, win by 2 points):
        - in 80% cases, the winner will win in 7 points by 2 points or more, with the following weights:
            - 7-4: 0.3
            - 7-3: 0.25
            - 7-5: 0.2
            - 7-2: 0.15
            - 7-1: 0.05
            - 7-0: 0.05
         - in 20% of cases, both players will be tied at 6-6, so the tie-break will go over 7 points, with the following weights:
             - 8-6: 0.25
             - 9-7: 0.2
             - 10-8: 0.15
             - 11-9: 0.1
             - 12-10: 0.1
             - 13-11: 0.1
             - 14-12: 0.05
             - 15-13: 0.05
    - For each normal set not ending up in a tie-break (90% of cases), the following weights will be observed:
        - 6-3: 0.3
        - 6-4: 0.25
        - 7-5: 0.15
        - 6-2: 0.1
        - 6-1: 0.1
        - 6-0: 0.09
        - retired (injury): 0.01

- For each super-tie-break (75% of all third sets, first in 10, win by 2 points):
        - in 80% cases, the winner will win in 10 points by 2 points or more, with the following weights:
            - 10-7: 0.25
            - 10-6: 0.2
            - 10-8: 0.15
            - 10-5: 0.1
            - 10-4: 0.1
            - 10-3: 0.1
            - 10-2: 0.06
            - 10-1: 0.03
            - 10-0: 0.01
         - in 20% of cases, both players will be tied at 9-9, so the tie-break will go over 10 points, with the following weights:
             - 11-9: 0.25
             - 12-10: 0.2
             - 13-11: 0.15
             - 14-12: 0.1
             - 15-13: 0.1
             - 16-14: 0.1
             - 17-15: 0.05
             - 18-16: 0.05


