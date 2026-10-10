import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "quiz_history.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                quiz TEXT,
                results TEXT,
                score INTEGER
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                quiz TEXT NOT NULL,
                submitted INTEGER NOT NULL DEFAULT 0
            )
        """)


def save_quiz(date, quiz, results, score):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO quiz_history(date, quiz, results, score)
            VALUES (?, ?, ?, ?)
        """, (
            date,
            json.dumps(quiz, ensure_ascii=False),
            json.dumps(results, ensure_ascii=False),
            score,
        ))
        return cursor.lastrowid


def create_quiz_session(session_id, date, quiz):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO quiz_sessions(session_id, date, quiz, submitted)
            VALUES (?, ?, ?, 0)
        """, (session_id, date, json.dumps(quiz, ensure_ascii=False)))


def get_quiz_session(session_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT session_id, date, quiz, submitted FROM quiz_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


def mark_quiz_session_submitted(session_id):
    with get_connection() as connection:
        connection.execute(
            "UPDATE quiz_sessions SET submitted = 1 WHERE session_id = ?",
            (session_id,),
        )


def get_all_history():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, date, quiz, results, score FROM quiz_history ORDER BY id DESC"
        ).fetchall()

    items = []
    for row in rows:
        quiz = json.loads(row["quiz"])
        results = json.loads(row["results"])
        items.append({
            "id": row["id"],
            "date": row["date"],
            "topic": quiz.get("topic", "Quiz"),
            "score": row["score"] or 0,
            "total": len(results),
            "question_count": len(quiz.get("questions", [])),
        })
    return items


def get_history_by_id(quiz_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, date, quiz, results, score FROM quiz_history WHERE id = ?",
            (quiz_id,),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "date": row["date"],
        "quiz": json.loads(row["quiz"]),
        "results": json.loads(row["results"]),
        "score": row["score"] or 0,
    }


init_db()
