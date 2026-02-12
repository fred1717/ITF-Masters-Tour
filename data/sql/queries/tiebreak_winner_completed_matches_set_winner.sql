SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM Matches m
WHERE m.match_status_id = 1
  AND (
    (m.set1_player1 = 7 AND m.set1_player2 = 6 AND m.set1_tiebreak_player1 <= m.set1_tiebreak_player2)
    OR (m.set1_player1 = 6 AND m.set1_player2 = 7 AND m.set1_tiebreak_player1 >= m.set1_tiebreak_player2)
    OR (m.set2_player1 = 7 AND m.set2_player2 = 6 AND m.set2_tiebreak_player1 <= m.set2_tiebreak_player2)
    OR (m.set2_player1 = 6 AND m.set2_player2 = 7 AND m.set2_tiebreak_player1 >= m.set2_tiebreak_player2)
    OR (m.set3_player1 = 7 AND m.set3_player2 = 6 AND m.set3_tiebreak_player1 <= m.set3_tiebreak_player2)
    OR (m.set3_player1 = 6 AND m.set3_player2 = 7 AND m.set3_tiebreak_player1 >= m.set3_tiebreak_player2)
  );
