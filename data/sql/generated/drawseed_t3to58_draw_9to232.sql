INSERT INTO DrawSeed (draw_id, player_id, seed_number, seeding_points, is_actual_seeding)
SELECT dp.draw_id, dp.player_id, dp.rn, dp.entry_points, TRUE
FROM (
    SELECT draw_id, player_id, entry_points,
           ROW_NUMBER() OVER (PARTITION BY draw_id ORDER BY entry_points DESC) AS rn,
           COUNT(*) OVER (PARTITION BY draw_id) AS num_players
    FROM DrawPlayers
    WHERE draw_id BETWEEN 9 AND 232
) dp
JOIN SeedingRules sr
  ON dp.num_players BETWEEN sr.min_players AND sr.max_players
WHERE dp.rn <= sr.num_seeds;
