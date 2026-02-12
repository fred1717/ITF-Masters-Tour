#!/usr/bin/env python3
"""
Database Connection Module
==========================

Handles PostgreSQL database connections for ITF validation scripts.

Author: Malik Hamdane
Date: January 2026
"""

import os

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Sequence


class DatabaseConnection:
    """PostgreSQL database connection manager."""

    def __init__(self):
        """Initialise connection parameters from environment variables."""
        self.config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', '5432')),
            'database': os.environ.get('DB_NAME', 'itf_tournament'),
            'user': os.environ.get('DB_USER', 'itfuser'),
            'password': os.environ.get('DB_PASSWORD', 'itfpwd'),
        }
        self.connection = None

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(**self.config)
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as a list of dictionaries.

        Args:
            sql: SQL SELECT statement (no parameters)

        Returns:
            List of dictionaries (one per row)
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            print(f"Query error: {e}")
            return []

    def query_params(self, sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
        """
        Execute a parameterised SELECT query and return results as a list of dictionaries.

        This is required for queries using placeholders (e.g. WHERE draw_id = %s).

        Args:
            sql: SQL SELECT statement with placeholders
            params: Parameter sequence matching the placeholders

        Returns:
            List of dictionaries (one per row)
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            print(f"Query error: {e}")
            return []


def get_all_data() -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    Fetch all data needed for validation.

    Returns:
        Dictionary containing all table data, or None on failure
    """
    db = DatabaseConnection()

    if not db.connect():
        print("Failed to connect to database")
        return None

    print("Loading data from database...")

    data = {
        'tournaments': db.query("SELECT * FROM Tournaments ORDER BY tournament_id"),
        'draws': db.query("SELECT * FROM Draws ORDER BY draw_id"),
        'players': db.query("SELECT * FROM Players ORDER BY player_id"),
        'age_categories': db.query("SELECT * FROM AgeCategory ORDER BY age_category_id"),
        'entries': db.query("SELECT * FROM Entries ORDER BY entry_id"),
        'draw_players': db.query("SELECT * FROM DrawPlayers ORDER BY draw_id, player_id"),
        'matches': db.query("SELECT * FROM Matches ORDER BY match_id"),
        'points_history': db.query("SELECT * FROM PointsHistory ORDER BY id"),
        'seeding_rules': db.query("SELECT * FROM SeedingRules ORDER BY id"),
        'weekly_ranking': db.query("SELECT * FROM WeeklyRanking ORDER BY ranking_year, ranking_week, player_id")
    }

    db.disconnect()

    # Print summary
    print(f"\nData loaded:")
    for table, records in data.items():
        print(f"  {table}: {len(records)} records")

    return data


if __name__ == '__main__':
    # Test connection
    print("Testing database connection...")
    data = get_all_data()

    if data:
        print("\n✓ Connection successful!")
        print("\nSample tournament:")
        if data['tournaments']:
            print(f"  {data['tournaments'][0]}")
    else:
        print("\n✗ Connection failed")
