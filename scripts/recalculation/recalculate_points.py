#!/usr/bin/env python3
"""
Recalculate PointsHistory Table
================================

This script recalculates points earned by players based on actual match results
and updates the PointsHistory table.

Uses the corrected calculate_points_history.py logic that:
- Determines stage reached from actual Matches table
- Applies first-match loss = 0 points rule correctly
- Maps round_id to stage_result_id properly

Author: Malik Hamdane
Date: January 2026
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import csv
from datetime import datetime, timedelta
from collections import defaultdict

from src.modules.db_connection import DatabaseConnection
from src.modules.calculate_points_history import calculate_points_history

from src.modules.ranking_window import (
    IsoWeek,
    iso_week_of,
    iso_week_monday,
    iso_week_sunday,
    add_iso_weeks,
    ranking_publication_dt,
    ranking_window_dt,
    ranking_week_for_tournament_week,
    entry_deadline_dt_for_tournament_week,
    draw_publication_dt_for_tournament_week,
    tournament_week_range,
)



def recalculate_all_points():
    """
    Recalculate PointsHistory for all completed tournaments.
    
    A tournament is completed if it has Matches records.
    
    Returns:
        List of all calculated PointsHistory records
    """
    db = DatabaseConnection()
    
    if not db.connect():
        print("✗ Failed to connect to database")
        return None
    
    print("=" * 80)
    print("RECALCULATING POINTSHISTORY")
    print("=" * 80)
    
    # Load all data
    print("\n1. Loading data from database...")
    tournaments = db.query("SELECT * FROM Tournaments ORDER BY tournament_id")
    draws = db.query("SELECT * FROM Draws ORDER BY draw_id")
    matches = db.query("SELECT * FROM Matches ORDER BY draw_id, round_id, match_number")
    draw_players = db.query("SELECT * FROM DrawPlayers ORDER BY draw_id")
    points_rules_list = db.query("SELECT * FROM PointsRules")
    
    print(f"   Loaded {len(tournaments)} tournaments")
    print(f"   Loaded {len(draws)} draws")
    print(f"   Loaded {len(matches)} matches")
    print(f"   Loaded {len(draw_players)} draw players")
    print(f"   Loaded {len(points_rules_list)} points rules")
    
    # Create lookup dictionaries
    points_rules = {
        (pr['category_id'], pr['stage_result_id']): pr['points']
        for pr in points_rules_list
    }
    
    tournaments_dict = {t['tournament_id']: t for t in tournaments}
    draws_dict = {d['draw_id']: d for d in draws}
    
    # Group data by draw_id
    matches_by_draw = defaultdict(list)
    for match in matches:
        matches_by_draw[match['draw_id']].append(match)
    
    players_by_draw = defaultdict(list)
    for dp in draw_players:
        players_by_draw[dp['draw_id']].append(dp['player_id'])
    
    # Calculate points for each draw that has matches
    print("\n2. Calculating points...")
    all_points_history = []
    next_ph_id = 1
    draws_processed = 0
    
    for draw_id, draw_matches in matches_by_draw.items():
        draw = draws_dict.get(draw_id)
        if not draw:
            continue
        
        tournament = tournaments_dict.get(draw['tournament_id'])
        if not tournament:
            continue
        
        player_ids = players_by_draw.get(draw_id, [])
        if not player_ids:
            continue
        
        # Calculate points for this draw
        points_history = calculate_points_history(
            draw_id=draw_id,
            tournament_id=tournament['tournament_id'],
            age_category_id=draw['age_category_id'],
            category_id=tournament['category_id'],
            points_rules=points_rules,
            tournament_end_date=tournament['end_date'],
            matches=draw_matches,
            player_ids=player_ids,
            next_ph_id=next_ph_id
        )
        
        all_points_history.extend(points_history)
        next_ph_id += len(points_history)
        draws_processed += 1
        
        print(f"   Draw {draw_id}: Calculated points for {len(points_history)} players")
    
    print(f"\n   Total: {len(all_points_history)} PointsHistory records across {draws_processed} draws")

    # Renumber IDs sequentially
    for idx, ph in enumerate(all_points_history, 1):
        ph['id'] = idx

    # Export to CSV
    print("\n3. Exporting to CSV...")
    csv_filename = f'points_history_recalculated_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    with open(csv_filename, 'w', newline='') as f:
        if all_points_history:
            fieldnames = list(all_points_history[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_points_history)
    
    print(f"   ✓ Exported to {csv_filename}")
    
    db.disconnect()
    
    return all_points_history, csv_filename


def update_database(points_history):
    """
    Update PointsHistory table in database with corrected values.
    
    Args:
        points_history: List of PointsHistory records to insert
    """
    db = DatabaseConnection()
    
    if not db.connect():
        print("✗ Failed to connect to database")
        return False
    
    print("\n4. Updating database...")
    
    try:
        cursor = db.connection.cursor()
        
        # Delete old points history
        print("   Deleting old PointsHistory records...")
        cursor.execute("DELETE FROM PointsHistory")
        deleted_count = cursor.rowcount
        print(f"   Deleted {deleted_count} old records")
        
        # Insert new points history
        print("   Inserting corrected PointsHistory records...")
        insert_sql = """
            INSERT INTO PointsHistory 
            (id, player_id, tournament_id, age_category_id, stage_result_id, 
             points_earned, tournament_end_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        for ph in points_history:
            cursor.execute(insert_sql, (
                ph['id'],
                ph['player_id'],
                ph['tournament_id'],
                ph['age_category_id'],
                ph['stage_result_id'],
                ph['points_earned'],
                ph['tournament_end_date'],
                ph['created_at']
            ))
        
        db.connection.commit()
        print(f"   ✓ Inserted {len(points_history)} corrected records")
        
        cursor.close()
        db.disconnect()
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error updating database: {e}")
        db.connection.rollback()
        db.disconnect()
        return False


def main():
    """Main execution."""
    
    # Recalculate points
    result = recalculate_all_points()
    
    if not result:
        print("\n✗ Failed to recalculate points history")
        return
    
    points_history, csv_file = result
    
    # Ask user if they want to update database
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"\n✓ Corrected PointsHistory exported to: {csv_file}")
    print(f"✓ Total records: {len(points_history)}")
    print("\nPlease review the CSV file to verify correctness.")
    print("Check that first-match losers have 0 points.")
    print("Check that winners have correct points based on stage reached.")
    
    response = input("\nUpdate database with corrected PointsHistory? (yes/no): ").strip().lower()
    
    if response == 'yes':
        success = update_database(points_history)
        if success:
            print("\n" + "=" * 80)
            print("✓✓✓ DATABASE UPDATED SUCCESSFULLY ✓✓✓")
            print("=" * 80)
            print("\nNext: Run recalculate_rankings.py to fix WeeklyRanking")
        else:
            print("\n✗ Database update failed")
    else:
        print("\nDatabase not updated. CSV file saved for review.")


if __name__ == '__main__':
    main()
