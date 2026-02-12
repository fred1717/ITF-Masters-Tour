-- ITF Senior Tournament Management System
-- Database Schema - Exact Match to Excel Structure
-- PostgreSQL 16
-- January 2026

-- Drop all tables
DROP TABLE IF EXISTS WeeklyRanking CASCADE;
DROP TABLE IF EXISTS PointsHistory CASCADE;
DROP TABLE IF EXISTS Matches CASCADE;
DROP TABLE IF EXISTS DrawSeed CASCADE;
DROP TABLE IF EXISTS DrawPlayers CASCADE;
DROP TABLE IF EXISTS Entries CASCADE;
DROP TABLE IF EXISTS PlayerSuspensions CASCADE;
DROP TABLE IF EXISTS Draws CASCADE;
DROP TABLE IF EXISTS Tournaments CASCADE;
DROP TABLE IF EXISTS Players CASCADE;
DROP TABLE IF EXISTS Venue CASCADE;
DROP TABLE IF EXISTS Location CASCADE;
DROP TABLE IF EXISTS PointsRules CASCADE;
DROP TABLE IF EXISTS SeedingRules CASCADE;
DROP TABLE IF EXISTS MatchRounds CASCADE;
DROP TABLE IF EXISTS StageResults CASCADE;
DROP TABLE IF EXISTS TournamentCategory CASCADE;
DROP TABLE IF EXISTS Surfaces CASCADE;
DROP TABLE IF EXISTS DrawStatus CASCADE;
DROP TABLE IF EXISTS MatchStatus CASCADE;
DROP TABLE IF EXISTS PlayerStatus CASCADE;
DROP TABLE IF EXISTS AgeCategory CASCADE;
DROP TABLE IF EXISTS Country CASCADE;
DROP TABLE IF EXISTS Gender CASCADE;

-- Reference Tables
CREATE TABLE Gender (
    gender_id INT PRIMARY KEY,
    code VARCHAR(10),
    description VARCHAR(100)
);

CREATE TABLE Country (
    country_id INT PRIMARY KEY,
    code VARCHAR(10),
    description VARCHAR(100)
);

CREATE TABLE AgeCategory (
    age_category_id INT PRIMARY KEY,
    code VARCHAR(10),
    description VARCHAR(100),
    min_age INT,
    max_age INT
);

CREATE TABLE PlayerStatus (
    status_id INT PRIMARY KEY,
    status_description VARCHAR(100)
);

CREATE TABLE MatchStatus (
    match_status_id INT PRIMARY KEY,
    code VARCHAR(20),
    description VARCHAR(100)
);

CREATE TABLE DrawStatus (
    status_id INT PRIMARY KEY,
    status_name VARCHAR(100),
    description VARCHAR(200)
);

CREATE TABLE Surfaces (
    surface_id INT PRIMARY KEY,
    surface_name VARCHAR(100)
);

CREATE TABLE TournamentCategory (
    category_id INT PRIMARY KEY,
    description VARCHAR(100)
);

CREATE TABLE StageResults (
    id INT PRIMARY KEY,
    code VARCHAR(20),
    description VARCHAR(100),
    display_order INT
);

CREATE TABLE MatchRounds (
    round_id INT PRIMARY KEY,
    code VARCHAR(20),
    label VARCHAR(100)
);

CREATE TABLE SeedingRules (
    id INT PRIMARY KEY,
    min_players INT,
    max_players INT,
    num_seeds INT
);

CREATE TABLE PointsRules (
    points_id INT PRIMARY KEY,
    category_id INT,
    stage_result_id INT,
    points INT
);

CREATE TABLE Location (
    location_id INT PRIMARY KEY,
    country_id INT,
    city VARCHAR(100)
);

CREATE TABLE Venue (
    venue_id INT PRIMARY KEY,
    location_id INT,
    venue_name VARCHAR(200)
);

-- Core Entity Tables
CREATE TABLE Players (
    player_id INT PRIMARY KEY,
    gender_id INT,
    country_id INT,
    status_id INT,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    birth_year INT
);

CREATE TABLE Tournaments (
    tournament_id INT PRIMARY KEY,
    name VARCHAR(200),
    start_date DATE,
    end_date DATE,
    tournament_year INT,
    tournament_week INT,
    venue_id INT,
    category_id INT,
    surface_id INT
);

CREATE TABLE Draws (
    draw_id INT PRIMARY KEY,
    tournament_id INT,
    age_category_id INT,
    gender_id INT,
    draw_status_id INT,
    num_players INT,
    has_supertiebreak BOOLEAN,
    draw_generated_at TIMESTAMP
);

CREATE TABLE Entries (
    entry_id INT PRIMARY KEY,
    player_id INT,
    tournament_id INT,
    age_category_id INT,
    gender_id INT,
    entry_points INT,
    entry_timestamp TIMESTAMP,
    withdrawn_at TIMESTAMP,
    withdrawal_type VARCHAR(20),

    CONSTRAINT entries_withdrawal_ck CHECK (
        (withdrawn_at IS NULL AND withdrawal_type IS NULL)
        OR
        (withdrawn_at IS NOT NULL AND withdrawal_type IN ('BEFORE_DRAW','AFTER_DRAW'))
    )
);

CREATE TABLE PlayerSuspensions (
    suspension_id INT PRIMARY KEY,
    player_id INT NOT NULL,
    tournament_id INT NOT NULL,
    reason_match_status_id INT NOT NULL,
    suspension_start DATE NOT NULL,
    suspension_end DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT ps_reason_ck CHECK (reason_match_status_id IN (3, 6)),
    CONSTRAINT ps_player_fk FOREIGN KEY (player_id)
        REFERENCES Players(player_id),
    CONSTRAINT ps_tournament_fk FOREIGN KEY (tournament_id)
        REFERENCES Tournaments(tournament_id),
    CONSTRAINT ps_reason_fk FOREIGN KEY (reason_match_status_id)
        REFERENCES MatchStatus(match_status_id)
);

CREATE TABLE DrawPlayers (
    draw_id INT,
    player_id INT,
    draw_position INT,
    has_bye BOOLEAN,
    entry_points INT,
    entry_timestamp TIMESTAMP,
    PRIMARY KEY (draw_id, player_id)
);

CREATE TABLE DrawSeed (
    draw_id INT,
    player_id INT,
    seed_number INT,
    seeding_points INT,
    is_actual_seeding BOOLEAN,
    PRIMARY KEY (draw_id, player_id)
);

CREATE TABLE Matches (
    match_id INT PRIMARY KEY,
    draw_id INT,
    round_id INT,
    player1_id INT,
    player2_id INT,
    match_number INT,
    match_date DATE,
    winner_id INT,
    match_status_id INT,
    set1_player1 INT,
    set1_player2 INT,
    set1_tiebreak_player1 INT,
    set1_tiebreak_player2 INT,
    set2_player1 INT,
    set2_player2 INT,
    set2_tiebreak_player1 INT,
    set2_tiebreak_player2 INT,
    set3_player1 INT,
    set3_player2 INT,
    set3_tiebreak_player1 INT,
    set3_tiebreak_player2 INT,
    set3_supertiebreak_player1 INT,
    set3_supertiebreak_player2 INT,

    -- Tennis scoring business rules
    -- Rule 1: Set 1 tie-break required when score is 7-6 or 6-7
    CONSTRAINT chk_set1_tiebreak CHECK (
        match_status_id IN (4, 6) OR (
        ((set1_player1 = 7 AND set1_player2 = 6) OR (set1_player1 = 6 AND set1_player2 = 7))
        = (set1_tiebreak_player1 IS NOT NULL AND set1_tiebreak_player2 IS NOT NULL))
    ),

    -- Rule 2: Set 2 tie-break required when score is 7-6 or 6-7
    CONSTRAINT chk_set2_tiebreak CHECK (
        match_status_id IN (4, 6) OR (
        ((set2_player1 = 7 AND set2_player2 = 6) OR (set2_player1 = 6 AND set2_player2 = 7))
        = (set2_tiebreak_player1 IS NOT NULL AND set2_tiebreak_player2 IS NOT NULL))
    ),

    -- Rule 3: Set 3 tie-break required when score is 7-6 or 6-7 (for normal sets)
    CONSTRAINT chk_set3_tiebreak CHECK (
        match_status_id IN (4, 6) OR (
        ((set3_player1 = 7 AND set3_player2 = 6) OR (set3_player1 = 6 AND set3_player2 = 7))
        = (set3_tiebreak_player1 IS NOT NULL AND set3_tiebreak_player2 IS NOT NULL))
    ),

    -- Rule 4: Set 3 format must be either normal set OR super tie-break, not both
    CONSTRAINT chk_set3_format CHECK (
        NOT (set3_player1 IS NOT NULL AND set3_supertiebreak_player1 IS NOT NULL)
    ),

    -- Rule 5: Third set required when sets are split (each player wins one set)
    CONSTRAINT chk_third_set_required CHECK (
        match_status_id IN (4, 6) OR (
        ((set1_player1 > set1_player2 AND set2_player1 < set2_player2) OR
         (set1_player1 < set1_player2 AND set2_player1 > set2_player2))
        = ((set3_player1 IS NOT NULL AND set3_player2 IS NOT NULL) OR
           (set3_supertiebreak_player1 IS NOT NULL AND set3_supertiebreak_player2 IS NOT NULL)))
    )
);

CREATE TABLE PointsHistory (
    id INT PRIMARY KEY,
    player_id INT,
    tournament_id INT,
    age_category_id INT,
    stage_result_id INT,
    points_earned INT,
    tournament_end_date DATE,
    created_at TIMESTAMP
);

CREATE TABLE WeeklyRanking (
    player_id INT,
    age_category_id INT,
    gender_id INT,
    ranking_year INT,
    ranking_week INT,
    total_points INT,
    rank_position INT,
    PRIMARY KEY (player_id, age_category_id, ranking_year, ranking_week)
);

-- Indexes for Performance
CREATE INDEX idx_players_country ON Players(country_id);
CREATE INDEX idx_players_gender ON Players(gender_id);
CREATE INDEX idx_players_name ON Players(last_name, first_name);

CREATE INDEX idx_tournaments_date ON Tournaments(start_date, end_date);
CREATE INDEX idx_tournaments_year_week ON Tournaments(tournament_year, tournament_week);

CREATE INDEX idx_draws_tournament ON Draws(tournament_id);
CREATE INDEX idx_entries_player ON Entries(player_id);
CREATE INDEX idx_entries_tournament ON Entries(tournament_id);

CREATE INDEX idx_matches_draw ON Matches(draw_id);
CREATE INDEX idx_matches_players ON Matches(player1_id, player2_id);
CREATE INDEX idx_matches_date ON Matches(match_date);

CREATE INDEX idx_points_player ON PointsHistory(player_id);
CREATE INDEX idx_ranking_year_week ON WeeklyRanking(ranking_year, ranking_week);

-- Summary: 24 tables created matching Excel structure exactly
