SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM Matches m
WHERE m.match_status_id = 1
  AND (
    SELECT COUNT(*) FROM (VALUES
        (CASE WHEN m.set1_player1 > m.set1_player2 THEN m.player1_id
              WHEN m.set1_player2 > m.set1_player1 THEN m.player2_id END),
        (CASE WHEN m.set2_player1 > m.set2_player2 THEN m.player1_id
              WHEN m.set2_player2 > m.set2_player1 THEN m.player2_id END),
        (CASE WHEN m.set3_player1 > m.set3_player2 THEN m.player1_id
              WHEN m.set3_player2 > m.set3_player1 THEN m.player2_id END)
    ) AS sets(winner) WHERE sets.winner = m.winner_id
  ) != 2;
