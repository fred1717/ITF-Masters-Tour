SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM Entries e
JOIN Players p ON p.player_id = e.player_id
JOIN Tournaments t ON t.tournament_id = e.tournament_id
JOIN AgeCategory ac ON ac.age_category_id = e.age_category_id
WHERE (t.tournament_year - p.birth_year) < ac.min_age
   OR (t.tournament_year - p.birth_year) > ac.max_age;
