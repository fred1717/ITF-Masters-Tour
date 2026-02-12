#!/usr/bin/env python3
"""
Regenerate Matches for Completed Tournaments
============================================

This script generates matches for all tournaments that have completed,
stopping at the last tournament that ended (tournament 54, Jan 18, 2026).

After this, matches will be entered manually via the website.

Author: Malik Hamdane
Date: January 2026
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import csv
import argparse
from datetime import datetime

from src.modules.db_connection import DatabaseConnection
from scripts.generation.generate_matches import generate_knockout_matches


def regenerate_all_matches():
    """
    Generate matches for all completed tournaments.

    A tournament is completed if it has DrawPlayers records.

    Returns:
        Tuple: (List of all generated matches, csv_filename)
    """
    db = DatabaseConnection()

    if not db.connect():
        print("✗ Failed to connect to database")
        return None

    print("=" * 80)
    print("REGENERATING MATCHES FOR COMPLETED TOURNAMENTS")
    print("=" * 80)

    # Load data
    print("\n1. Loading data from database...")
    tournaments = db.query("SELECT * FROM Tournaments ORDER BY tournament_id")
    draws = db.query("SELECT * FROM Draws ORDER BY draw_id")
    draw_players = db.query("SELECT * FROM DrawPlayers ORDER BY draw_id, draw_position")

    print(f"   Loaded {len(tournaments)} tournaments")
    print(f"   Loaded {len(draws)} draws")
    print(f"   Loaded {len(draw_players)} draw players")

    # Group draw players by draw_id
    players_by_draw = {}
    for dp in draw_players:
        draw_id = dp['draw_id']
        if draw_id not in players_by_draw:
            players_by_draw[draw_id] = []
        players_by_draw[draw_id].append(dp)

    # Generate matches for each draw that has players
    print("\n2. Generating matches.")
    all_matches = []
    next_match_id = 1
    draws_processed = 0

    for draw in draws:
        draw_id = draw['draw_id']

        # Check if draw has players (completed)
        if draw_id not in players_by_draw or len(players_by_draw[draw_id]) == 0:
            continue

        # Get tournament info
        tournament = next((t for t in tournaments if t['tournament_id'] == draw['tournament_id']), None)
        if not tournament:
            continue

        # Sort players by draw_position
        draw_player_list = sorted(players_by_draw[draw_id], key=lambda x: x['draw_position'])

        # Generate matches
        matches = generate_knockout_matches(
            draw_id=draw_id,
            draw_players=draw_player_list,
            tournament_start_date=tournament['start_date'],
            has_supertiebreak=draw['has_supertiebreak'],
            next_match_id=next_match_id
        )

        all_matches.extend(matches)
        next_match_id += len(matches)
        draws_processed += 1

        print(f"   Draw {draw_id}: Generated {len(matches)} matches")

    print(f"\n   Total: {len(all_matches)} matches across {draws_processed} draws")

    # Export to CSV
    print("\n3. Exporting to CSV...")
    csv_filename = f'matches_regenerated_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    with open(csv_filename, 'w', newline='') as f:
        if all_matches:
            fieldnames = list(all_matches[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_matches)

    print(f"   ✓ Exported to {csv_filename}")

    db.disconnect()

    return all_matches, csv_filename


def update_database(matches):
    """
    Update Matches table in database with regenerated matches.

    Args:
        matches: List of match records to insert
    """
    db = DatabaseConnection()

    if not db.connect():
        print("✗ Failed to connect to database")
        return False

    print("\n4. Updating database.")

    try:
        cursor = db.connection.cursor()

        # Delete old matches
        print("   Deleting old Matches records.")
        cursor.execute("DELETE FROM Matches")
        deleted_count = cursor.rowcount
        print(f"   Deleted {deleted_count} old records")

        # Insert new matches
        print("   Inserting regenerated Matches records.")
        insert_sql = """
            INSERT INTO Matches
            (match_id, draw_id, round_id, match_number, player1_id, player2_id,
             match_date, match_status_id, winner_id,
             set1_player1, set1_player2, set1_tiebreak_player1, set1_tiebreak_player2,
             set2_player1, set2_player2, set2_tiebreak_player1, set2_tiebreak_player2,
             set3_player1, set3_player2, set3_tiebreak_player1, set3_tiebreak_player2,
             set3_supertiebreak_player1, set3_supertiebreak_player2)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for match in matches:
            cursor.execute(insert_sql, (
                match['match_id'],
                match['draw_id'],
                match['round_id'],
                match['match_number'],
                match['player1_id'],
                match['player2_id'],
                match['match_date'],
                match['match_status_id'],
                match['winner_id'],
                match['set1_player1'],
                match['set1_player2'],
                match['set1_tiebreak_player1'],
                match['set1_tiebreak_player2'],
                match['set2_player1'],
                match['set2_player2'],
                match['set2_tiebreak_player1'],
                match['set2_tiebreak_player2'],
                match['set3_player1'],
                match['set3_player2'],
                match['set3_tiebreak_player1'],
                match['set3_tiebreak_player2'],
                match['set3_supertiebreak_player1'],
                match['set3_supertiebreak_player2']
            ))

        db.connection.commit()
        print(f"   ✓ Inserted {len(matches)} corrected records")

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
    parser = argparse.ArgumentParser(description="Regenerate Matches for completed tournaments.")
    parser.add_argument("--update-db", action="store_true", help="Replace Matches table content after generation.")
    args = parser.parse_args()

    result = regenerate_all_matches()

    if not result:
        print("\n✗ Failed to regenerate matches")
        return

    matches, csv_file = result

    if args.update_db:
        ok = update_database(matches)
        if not ok:
            print("\n✗ Database update failed")
            return

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(f"\n✓ Generated {len(matches)} matches")
    print(f"✓ Exported to: {csv_file}")
    if not args.update_db:
        print("\nDatabase update was not requested (run with --update-db to replace Matches).")


if __name__ == '__main__':
    main()
