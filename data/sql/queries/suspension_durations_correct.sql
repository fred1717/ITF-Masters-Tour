SELECT
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS bad_rows
FROM PlayerSuspensions ps
WHERE (ps.reason_match_status_id = 3 AND ps.suspension_end != ps.suspension_start + INTERVAL '2 months')
   OR (ps.reason_match_status_id = 6 AND ps.suspension_end != ps.suspension_start + INTERVAL '6 months');
