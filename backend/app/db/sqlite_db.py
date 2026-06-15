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

        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                remaining_quota INTEGER NOT NULL DEFAULT 0,
                seen_onboarding INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 邀请码表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invite_codes (
                code TEXT PRIMARY KEY,
                max_uses INTEGER NOT NULL DEFAULT 1,
                used_count INTEGER NOT NULL DEFAULT 0,
                grant_count INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 邀请码兑换记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invite_redemptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                code TEXT NOT NULL,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, code)
            )
        """)

        # 创建索引提升查询性能
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_resume ON matches(resume_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_job ON matches(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_created ON matches(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_atoms_type ON atoms(atom_type)")

        # 迁移：为 atoms 增加 meta 列，承载事实层/表达层与 JD 改写版本
        atom_cols = [row[1] for row in cursor.execute("PRAGMA table_info(atoms)").fetchall()]
        if "meta" not in atom_cols:
            cursor.execute("ALTER TABLE atoms ADD COLUMN meta TEXT")
        # 迁移：为 atoms 增加 user_id 列，实现原子库按登录用户隔离（每人只看自己的）
        if "user_id" not in atom_cols:
            cursor.execute("ALTER TABLE atoms ADD COLUMN user_id TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_atoms_user ON atoms(user_id)")

        # 迁移：手机号登录改造。
        # - email 列复用为登录身份（存手机号），password_hash 不再使用（手机号+验证码登录）。
        # - 新增 is_unlimited：站长本人手机号设为无限次。
        user_cols = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
        if "is_unlimited" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_unlimited INTEGER NOT NULL DEFAULT 0")

        # seed 演示邀请码（重复启动不会报错）
        cursor.execute(
            """INSERT OR IGNORE INTO invite_codes (code, max_uses, used_count, grant_count, active)
               VALUES (?, ?, ?, ?, ?)""",
            ("OFFER2026", 100, 0, 1, 1)
        )
        # seed 通用验证码 WASD：任何人凭它登录可使用一次完整流程（max_uses 给足，按人次发放）
        cursor.execute(
            """INSERT OR IGNORE INTO invite_codes (code, max_uses, used_count, grant_count, active)
               VALUES (?, ?, ?, ?, ?)""",
            ("WASD", 1000000, 0, 1, 1)
        )

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

    def save_atom(self, atom: Dict[str, Any], user_id: Optional[str] = None) -> str:
        """保存经历原子（按登录用户隔离）"""
        atom_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO atoms (id, title, atom_type, description, company, skills, meta, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    atom_id,
                    atom.get("title", ""),
                    atom.get("type", "work"),
                    atom.get("description", ""),
                    atom.get("company", ""),
                    json.dumps(atom.get("skills", []), ensure_ascii=False),
                    json.dumps(atom.get("meta", {}), ensure_ascii=False),
                    user_id,
                )
            )
            conn.commit()
            return atom_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def list_atoms(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取经历原子（传 user_id 则只返回该用户的）"""
        conn = self._get_conn()
        try:
            if user_id is not None:
                cursor = conn.execute(
                    """SELECT id, title, atom_type, description, company, skills, meta, created_at
                       FROM atoms WHERE user_id = ?
                       ORDER BY created_at DESC""",
                    (user_id,)
                )
            else:
                cursor = conn.execute(
                    """SELECT id, title, atom_type, description, company, skills, meta, created_at
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
                    "meta": json.loads(row["meta"]) if ("meta" in row.keys() and row["meta"]) else {},
                    "created_at": row["created_at"]
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_atom(self, atom_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取单个经历原子（传 user_id 则限定只能取该用户自己的）"""
        conn = self._get_conn()
        try:
            if user_id is not None:
                row = conn.execute(
                    """SELECT id, title, atom_type, description, company, skills, meta, created_at
                       FROM atoms WHERE id = ? AND user_id = ?""",
                    (atom_id, user_id)
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT id, title, atom_type, description, company, skills, meta, created_at
                       FROM atoms WHERE id = ?""",
                    (atom_id,)
                ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "title": row["title"],
                "type": row["atom_type"],
                "description": row["description"],
                "company": row["company"],
                "skills": json.loads(row["skills"]) if row["skills"] else [],
                "meta": json.loads(row["meta"]) if ("meta" in row.keys() and row["meta"]) else {},
                "created_at": row["created_at"]
            }
        finally:
            conn.close()

    def update_atom_meta(self, atom_id: str, meta: Dict[str, Any]) -> bool:
        """更新经历原子的 meta（表达层版本等）"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE atoms SET meta = ? WHERE id = ?",
                (json.dumps(meta, ensure_ascii=False), atom_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_atom(self, atom_id: str, user_id: Optional[str] = None) -> bool:
        """删除经历原子（传 user_id 则限定只能删该用户自己的）"""
        conn = self._get_conn()
        try:
            if user_id is not None:
                cursor = conn.execute(
                    "DELETE FROM atoms WHERE id = ? AND user_id = ?",
                    (atom_id, user_id)
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM atoms WHERE id = ?",
                    (atom_id,)
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ========== 账号体系 ==========

    def get_or_create_user_by_phone(self, phone: str, signup_quota: int, is_unlimited: bool = False) -> Dict[str, Any]:
        """按手机号获取用户，不存在则创建（手机号+验证码登录）。

        - 已存在：直接返回；若 is_unlimited 需要提升则同步更新。
        - 不存在：创建并赠送 signup_quota 次（无限用户额度记 0，由 is_unlimited 控制）。
        手机号复用 email 列作为唯一登录身份；password_hash 写占位值（不再用于校验）。
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id, email, remaining_quota, seen_onboarding, is_unlimited, created_at FROM users WHERE email = ?",
                (phone,)
            ).fetchone()
            if row:
                # 已存在：必要时把站长本人提升为无限
                if is_unlimited and not row["is_unlimited"]:
                    conn.execute("UPDATE users SET is_unlimited = 1 WHERE id = ?", (row["id"],))
                    conn.commit()
                return {
                    "id": row["id"],
                    "phone": row["email"],
                    "remaining_quota": row["remaining_quota"],
                    "seen_onboarding": bool(row["seen_onboarding"]),
                    "is_unlimited": bool(is_unlimited or row["is_unlimited"]),
                    "created_at": row["created_at"],
                    "is_new": False,
                }
            user_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO users (id, email, password_hash, remaining_quota, seen_onboarding, is_unlimited)
                   VALUES (?, ?, ?, ?, 0, ?)""",
                (user_id, phone, "phone-login", 0 if is_unlimited else signup_quota, 1 if is_unlimited else 0)
            )
            conn.commit()
            return {
                "id": user_id,
                "phone": phone,
                "remaining_quota": 0 if is_unlimited else signup_quota,
                "seen_onboarding": False,
                "is_unlimited": is_unlimited,
                "created_at": None,
                "is_new": True,
            }
        finally:
            conn.close()

    def create_user(self, email: str, password_hash: str, quota: int) -> Dict[str, Any]:
        """创建用户，email 冲突抛 ValueError"""
        user_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, remaining_quota, seen_onboarding)
                   VALUES (?, ?, ?, ?, 0)""",
                (user_id, email, password_hash, quota)
            )
            conn.commit()
            return {
                "id": user_id,
                "email": email,
                "remaining_quota": quota,
                "seen_onboarding": False
            }
        except sqlite3.IntegrityError:
            raise ValueError("该邮箱已注册")
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """按 email 查询用户（含 password_hash，用于登录校验）"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT id, email, password_hash, remaining_quota, seen_onboarding, created_at
                   FROM users WHERE email = ?""",
                (email,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "email": row["email"],
                "password_hash": row["password_hash"],
                "remaining_quota": row["remaining_quota"],
                "seen_onboarding": bool(row["seen_onboarding"]),
                "created_at": row["created_at"]
            }
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """按 id 查询用户（不含 password_hash，用于对外）"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT id, email, remaining_quota, seen_onboarding, is_unlimited, created_at
                   FROM users WHERE id = ?""",
                (user_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "email": row["email"],
                "phone": row["email"],
                "remaining_quota": row["remaining_quota"],
                "seen_onboarding": bool(row["seen_onboarding"]),
                "is_unlimited": bool(row["is_unlimited"]),
                "created_at": row["created_at"]
            }
        finally:
            conn.close()

    def update_quota(self, user_id: str, delta: int) -> int:
        """原子更新额度，返回更新后的 remaining_quota"""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE users SET remaining_quota = remaining_quota + ? WHERE id = ?",
                (delta, user_id)
            )
            conn.commit()
            row = conn.execute(
                "SELECT remaining_quota FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            return row["remaining_quota"] if row else 0
        finally:
            conn.close()

    def consume_quota(self, user_id: str) -> bool:
        """原子安全扣减 1，成功返回 True（并发下不会扣成负数）"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE users SET remaining_quota = remaining_quota - 1 WHERE id = ? AND remaining_quota > 0",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_onboarding_done(self, user_id: str) -> bool:
        """标记已看过引导"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE users SET seen_onboarding = 1 WHERE id = ?",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_invite_code(self, code: str) -> Optional[Dict[str, Any]]:
        """查询邀请码"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT code, max_uses, used_count, grant_count, active
                   FROM invite_codes WHERE code = ?""",
                (code,)
            ).fetchone()
            if not row:
                return None
            return {
                "code": row["code"],
                "max_uses": row["max_uses"],
                "used_count": row["used_count"],
                "grant_count": row["grant_count"],
                "active": bool(row["active"])
            }
        finally:
            conn.close()

    def has_redeemed(self, user_id: str, code: str) -> bool:
        """判断用户是否已兑换过该邀请码"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM invite_redemptions WHERE user_id = ? AND code = ?",
                (user_id, code)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def record_redemption(self, user_id: str, code: str) -> None:
        """记录一次兑换"""
        redemption_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO invite_redemptions (id, user_id, code) VALUES (?, ?, ?)",
                (redemption_id, user_id, code)
            )
            conn.commit()
        finally:
            conn.close()

    def increment_invite_used(self, code: str) -> None:
        """邀请码已用次数 +1"""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE invite_codes SET used_count = used_count + 1 WHERE code = ?",
                (code,)
            )
            conn.commit()
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
