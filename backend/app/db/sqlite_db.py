"""
SQLite 数据库层 - 替代 TinyDB

优势：
- 支持并发访问（SQLite默认支持）
- ACID 事务支持
- 更可靠的文件存储
- 原生 SQL 支持

作者：Claude
创建日期：2026-06-01
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class SQLiteDatabase:
    """SQLite 数据库操作类"""

    def __init__(self, db_path: str = "data/offer_catcher.db"):
        """初始化数据库连接"""
        self.db_path = db_path
        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（线程安全）"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None  # 自动提交模式
        )
        conn.row_factory = sqlite3.Row
        # 启用 WAL 模式，提升并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        return conn

    def _init_tables(self):
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 简历表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 岗位表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 匹配记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                resume_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                result TEXT NOT NULL,
                position_name TEXT,
                company TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resume_id) REFERENCES resumes(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)

        # 经历原子表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS atoms (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                atom_type TEXT NOT NULL,
                description TEXT,
                company TEXT,
                skills TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 投递记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                keywords_used TEXT,
                notes TEXT,
                applied_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引提升查询性能
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_resume ON matches(resume_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_job ON matches(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_created ON matches(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_atoms_type ON atoms(atom_type)")

        conn.commit()
        conn.close()

    def save_resume(self, resume_data: Dict[str, Any]) -> str:
        """保存简历"""
        resume_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO resumes (id, data) VALUES (?, ?)",
                (resume_id, json.dumps(resume_data, ensure_ascii=False))
            )
            conn.commit()
            return resume_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_resume(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """获取简历"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT data FROM resumes WHERE id = ?",
                (resume_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["data"])
            return None
        finally:
            conn.close()

    def save_job(self, job_data: Dict[str, Any]) -> str:
        """保存岗位"""
        job_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO jobs (id, data) VALUES (?, ?)",
                (job_id, json.dumps(job_data, ensure_ascii=False))
            )
            conn.commit()
            return job_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取岗位"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT data FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["data"])
            return None
        finally:
            conn.close()

    def save_match(self, match_record: Dict[str, Any]) -> str:
        """保存匹配记录"""
        match_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO matches (id, resume_id, job_id, result, position_name, company)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    match_id,
                    match_record.get("resume_id", ""),
                    match_record.get("job_id", ""),
                    json.dumps(match_record.get("match_result", {}), ensure_ascii=False),
                    match_record.get("position_name", ""),
                    match_record.get("company", "")
                )
            )
            conn.commit()
            return match_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def list_matches(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取匹配历史"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """SELECT id, result, position_name, company, created_at
                   FROM matches
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,)
            )
            return [
                {
                    "id": row["id"],
                    "match_result": json.loads(row["result"]),
                    "position_name": row["position_name"],
                    "company": row["company"],
                    "created_at": row["created_at"]
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def list_resumes(self) -> List[str]:
        """获取所有简历ID"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT id FROM resumes ORDER BY created_at DESC")
            return [row["id"] for row in cursor.fetchall()]
        finally:
            conn.close()

    def list_jobs(self) -> List[str]:
        """获取所有岗位ID"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT id FROM jobs ORDER BY created_at DESC")
            return [row["id"] for row in cursor.fetchall()]
        finally:
            conn.close()

    # ========== 经历原子库 ==========

    def save_atom(self, atom: Dict[str, Any]) -> str:
        """保存经历原子"""
        atom_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO atoms (id, title, atom_type, description, company, skills)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    atom_id,
                    atom.get("title", ""),
                    atom.get("type", "work"),
                    atom.get("description", ""),
                    atom.get("company", ""),
                    json.dumps(atom.get("skills", []), ensure_ascii=False)
                )
            )
            conn.commit()
            return atom_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def list_atoms(self) -> List[Dict[str, Any]]:
        """获取所有经历原子"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """SELECT id, title, atom_type, description, company, skills, created_at
                   FROM atoms
                   ORDER BY created_at DESC"""
            )
            return [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "type": row["atom_type"],
                    "description": row["description"],
                    "company": row["company"],
                    "skills": json.loads(row["skills"]) if row["skills"] else [],
                    "created_at": row["created_at"]
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def delete_atom(self, atom_id: str) -> bool:
        """删除经历原子"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM atoms WHERE id = ?",
                (atom_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ========== 投递追踪 ==========

    def save_application(self, app: Dict[str, Any]) -> str:
        """保存投递记录"""
        app_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO applications (id, company, position, status, keywords_used, notes, applied_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    app_id,
                    app.get("company", ""),
                    app.get("position", ""),
                    app.get("status", "pending"),
                    app.get("keywords_used", ""),
                    app.get("notes", ""),
                    app.get("applied_date", datetime.now().strftime("%Y-%m-%d"))
                )
            )
            conn.commit()
            return app_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def list_applications(self) -> List[Dict[str, Any]]:
        """获取所有投递记录"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """SELECT id, company, position, status, keywords_used, notes, applied_date, created_at
                   FROM applications
                   ORDER BY created_at DESC"""
            )
            return [
                {
                    "id": row["id"],
                    "company": row["company"],
                    "position": row["position"],
                    "status": row["status"],
                    "keywords_used": row["keywords_used"],
                    "notes": row["notes"],
                    "applied_date": row["applied_date"],
                    "created_at": row["created_at"]
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def update_application(self, app_id: str, updates: Dict[str, Any]) -> bool:
        """更新投递记录"""
        if not updates:
            return False
        conn = self._get_conn()
        try:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [app_id]
            cursor = conn.execute(
                f"UPDATE applications SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        conn = self._get_conn()
        try:
            stats = {}
            stats["resumes_count"] = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
            stats["jobs_count"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            stats["matches_count"] = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            stats["atoms_count"] = conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
            stats["applications_count"] = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
            return stats
        finally:
            conn.close()


# 全局数据库实例
_db_instance: Optional[SQLiteDatabase] = None


def get_db() -> SQLiteDatabase:
    """获取数据库实例（单例模式）"""
    global _db_instance
    if _db_instance is None:
        _db_instance = SQLiteDatabase()
    return _db_instance
