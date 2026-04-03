"""SQLite 기반 회의 히스토리 저장소."""

import re
import sqlite3
from collections import Counter
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "meetings.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '회의',
            date TEXT NOT NULL,
            attendees TEXT DEFAULT '',
            meeting_type TEXT DEFAULT '일반 회의',
            location TEXT DEFAULT '',
            full_text TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_meeting(title, date, attendees, meeting_type, location, full_text, summary):
    """회의 데이터를 DB에 저장. 저장된 ID 반환."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO meetings
               (title, date, attendees, meeting_type, location, full_text, summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, date, attendees, meeting_type, location, full_text, summary,
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_meetings(limit=50):
    """최근 회의 목록 반환 (id, title, date, meeting_type, created_at)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, date, meeting_type, created_at FROM meetings ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_meeting(meeting_id):
    """ID로 회의 전체 데이터 조회."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_meetings(query, limit=20):
    """전체 텍스트 또는 요약에서 키워드 검색."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, title, date, meeting_type, created_at FROM meetings
               WHERE full_text LIKE ? OR summary LIKE ? OR title LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_meeting(meeting_id):
    """회의 삭제."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        conn.commit()
    finally:
        conn.close()


def update_meeting(meeting_id, full_text=None, summary=None):
    """회의 기록/요약 업데이트."""
    conn = _get_conn()
    try:
        if full_text is not None and summary is not None:
            conn.execute(
                "UPDATE meetings SET full_text = ?, summary = ? WHERE id = ?",
                (full_text, summary, meeting_id),
            )
        elif full_text is not None:
            conn.execute(
                "UPDATE meetings SET full_text = ? WHERE id = ?",
                (full_text, meeting_id),
            )
        elif summary is not None:
            conn.execute(
                "UPDATE meetings SET summary = ? WHERE id = ?",
                (summary, meeting_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_meeting_stats():
    """월별 회의 횟수, 빈출 키워드 등 통계 반환."""
    conn = _get_conn()

    # 월별 회의 횟수
    monthly = conn.execute(
        """SELECT strftime('%Y-%m', date) as month, COUNT(*) as count
           FROM meetings GROUP BY month ORDER BY month DESC LIMIT 12"""
    ).fetchall()
    monthly_stats = [(r["month"], r["count"]) for r in monthly]

    # 총 회의 수
    total = conn.execute("SELECT COUNT(*) as cnt FROM meetings").fetchone()["cnt"]

    # 빈출 키워드 (요약에서 2글자 이상 한글 단어 추출)
    summaries = conn.execute("SELECT summary FROM meetings").fetchall()
    conn.close()

    word_counter = Counter()
    stop_words = {"없음", "있습니다", "합니다", "입니다", "했습니다", "됩니다",
                  "대한", "통해", "위해", "에서", "으로", "에게", "것으로",
                  "아이템", "회의", "요약", "사항", "내용", "담당자", "화자"}
    for row in summaries:
        words = re.findall(r"[가-힣]{2,}", row["summary"])
        for w in words:
            if w not in stop_words:
                word_counter[w] += 1

    top_keywords = word_counter.most_common(20)

    return {
        "monthly": monthly_stats,
        "total": total,
        "top_keywords": top_keywords,
    }
