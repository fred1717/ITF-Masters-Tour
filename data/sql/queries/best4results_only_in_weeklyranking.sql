WITH wr_with_points AS (
    SELECT
        wr.player_id,
        wr.age_category_id,
        wr.ranking_year,
        wr.ranking_week,
        wr.total_points,
        ph.points_earned,
        ROW_NUMBER() OVER (
            PARTITION BY wr.player_id, wr.age_category_id, wr.ranking_year, wr.ranking_week
            ORDER BY ph.points_earned DESC
        ) AS rn
    FROM WeeklyRanking wr
    JOIN PointsHistory ph
        ON ph.player_id = wr.player_id
        AND ph.age_category_id = wr.age_category_id
    JOIN Tournaments t
        ON t.tournament_id = ph.tournament_id
    WHERE (t.tournament_year * 100 + t.tournament_week)
        >= ((wr.ranking_year - 1) * 100 + wr.ranking_week)
      AND (t.tournament_year * 100 + t.tournament_week)
        < (wr.ranking_year * 100 + wr.ranking_week)
),
best4 AS (
    SELECT
        player_id,
        age_category_id,
        ranking_year,
        ranking_week,
        SUM(points_earned) AS expected_points
    FROM wr_with_points
    WHERE rn <= 4
    GROUP BY player_id, age_category_id, ranking_year, ranking_week
)
SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM WeeklyRanking wr
LEFT JOIN best4 b
    ON b.player_id = wr.player_id
    AND b.age_category_id = wr.age_category_id
    AND b.ranking_year = wr.ranking_year
    AND b.ranking_week = wr.ranking_week
WHERE wr.total_points != COALESCE(b.expected_points, 0);
