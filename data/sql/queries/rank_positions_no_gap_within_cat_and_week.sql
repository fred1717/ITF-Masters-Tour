SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM (
    SELECT age_category_id, gender_id, ranking_year, ranking_week,
        MAX(rank_position) AS max_rank,
        COUNT(*) AS num_players
    FROM WeeklyRanking
    GROUP BY age_category_id, gender_id, ranking_year, ranking_week
) sub
WHERE max_rank != num_players;
