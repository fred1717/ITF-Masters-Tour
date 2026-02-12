SELECT wr.rank_position, p.player_id, p.first_name, p.last_name, p.country_id, wr.total_points
FROM WeeklyRanking wr
JOIN Players p ON p.player_id = wr.player_id
WHERE wr.ranking_year = 2026
  AND wr.ranking_week = 7
  AND wr.age_category_id = 2
  AND wr.gender_id = 1
ORDER BY wr.rank_position;
