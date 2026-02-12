SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM Matches
WHERE winner_id IS NOT NULL
  AND winner_id != player1_id
  AND winner_id != player2_id;
