SELECT 'Entries' AS t, COUNT(*) FROM Entries
UNION ALL SELECT 'DrawPlayers', COUNT(*) FROM DrawPlayers
UNION ALL SELECT 'Matches', COUNT(*) FROM Matches
UNION ALL SELECT 'PlayerSuspensions', COUNT(*) FROM PlayerSuspensions
UNION ALL SELECT 'PointsHistory', COUNT(*) FROM PointsHistory
UNION ALL SELECT 'WeeklyRanking', COUNT(*) FROM WeeklyRanking;
