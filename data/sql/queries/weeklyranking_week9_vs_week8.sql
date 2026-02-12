SELECT w9.player_id, p.first_name, p.last_name,
       w9.age_category_id, w9.gender_id,
       w8.total_points AS week8_pts, w9.total_points AS week9_pts,
       w9.total_points - COALESCE(w8.total_points, 0) AS diff,
       w9.rank_position AS w9_rank, w8.rank_position AS w8_rank
FROM WeeklyRanking w9
JOIN Players p ON p.player_id = w9.player_id
LEFT JOIN WeeklyRanking w8
  ON w8.player_id = w9.player_id
  AND w8.age_category_id = w9.age_category_id
  AND w8.ranking_year = 2026 AND w8.ranking_week = 8
WHERE w9.ranking_year = 2026 AND w9.ranking_week = 9
ORDER BY w9.age_category_id, w9.gender_id, w9.rank_position;
