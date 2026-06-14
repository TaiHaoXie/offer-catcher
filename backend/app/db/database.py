"""
Offer 捕手 - 数据库模块（TinyDB）
"""
import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage


class Database:
    """数据库管理类"""

    def __init__(self, data_dir: str = "./data"):
        """初始化数据库"""
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # 初始化各个数据表
        self.resumes_db = TinyDB(f"{data_dir}/resumes.json")
        self.jobs_db = TinyDB(f"{data_dir}/jobs.json")
        self.matches_db = TinyDB(f"{data_dir}/matches.json")
        self.atoms_db = TinyDB(f"{data_dir}/atoms.json")
        self.applications_db = TinyDB(f"{data_dir}/applications.json")

    def generate_id(self, prefix: str = "") -> str:
        """生成唯一ID"""
        import uuid
        return f"{prefix}{uuid.uuid4().hex[:12]}"

    # ========== 简历操作 ==========

    def save_resume(self, resume_data: Dict) -> str:
        """保存简历数据"""
        resume_id = self.generate_id("resume_")
        resume_data["id"] = resume_id
        resume_data["created_at"] = datetime.now().isoformat()
        self.resumes_db.insert(resume_data)
        return resume_id

    def get_resume(self, resume_id: str) -> Optional[Dict]:
        """获取简历数据"""
        query = Query()
        result = self.resumes_db.get(query.id == resume_id)
        return result

    def list_resumes(self, limit: int = 10) -> List[Dict]:
        """列出最近的简历"""
        return self.resumes_db.all()[-limit:]

    def delete_resume(self, resume_id: str) -> bool:
        """删除简历"""
        query = Query()
        return self.resumes_db.remove(query.id == resume_id)

    # ========== 岗位操作 ==========

    def save_job(self, job_data: Dict) -> str:
        """保存岗位数据"""
        job_id = self.generate_id("job_")
        job_data["id"] = job_id
        job_data["created_at"] = datetime.now().isoformat()
        self.jobs_db.insert(job_data)
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取岗位数据"""
        query = Query()
        result = self.jobs_db.get(query.id == job_id)
        return result

    def list_jobs(self, limit: int = 10) -> List[Dict]:
        """列出最近的岗位"""
        return self.jobs_db.all()[-limit:]

    def delete_job(self, job_id: str) -> bool:
        """删除岗位"""
        query = Query()
        return self.jobs_db.remove(query.id == job_id)

    # ========== 匹配记录操作 ==========

    def save_match(self, match_data: Dict) -> str:
        """保存匹配记录"""
        match_id = self.generate_id("match_")
        match_data["id"] = match_id
        match_data["created_at"] = datetime.now().isoformat()
        self.matches_db.insert(match_data)
        return match_id

    def get_match(self, match_id: str) -> Optional[Dict]:
        """获取匹配记录"""
        query = Query()
        result = self.matches_db.get(query.id == match_id)
        return result

    def list_matches(self, limit: int = 20) -> List[Dict]:
        """列出匹配记录（按时间倒序）"""
        matches = self.matches_db.all()
        matches.reverse()  # 最新的在前
        return matches[:limit]

    def get_matches_by_resume(self, resume_id: str) -> List[Dict]:
        """获取某简历的所有匹配记录"""
        query = Query()
        results = self.matches_db.search(query.resume_id == resume_id)
        results.reverse()
        return results

    def delete_match(self, match_id: str) -> bool:
        """删除匹配记录"""
        query = Query()
        return self.matches_db.remove(query.id == match_id)

    # ========== 数据清理 ==========

    def clear_all(self):
        """清空所有数据（慎用）"""
        self.resumes_db.truncate()
        self.jobs_db.truncate()
        self.matches_db.truncate()
        self.atoms_db.truncate()
        self.applications_db.truncate()

    # ========== 经历原子库操作 ==========

    def save_atom(self, atom_data: Dict) -> str:
        """保存经历原子"""
        atom_id = self.generate_id("atom_")
        atom_data["id"] = atom_id
        atom_data["created_at"] = datetime.now().isoformat()
        if "weight" not in atom_data:
            atom_data["weight"] = 1.0
        self.atoms_db.insert(atom_data)
        return atom_id

    def get_atom(self, atom_id: str) -> Optional[Dict]:
        """获取单个原子"""
        query = Query()
        return self.atoms_db.get(query.id == atom_id)

    def list_atoms(self, atom_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """列出经历原子"""
        if atom_type:
            query = Query()
            atoms = self.atoms_db.search(query.type == atom_type)
        else:
            atoms = self.atoms_db.all()
        atoms.reverse()
        return atoms[:limit]

    def update_atom(self, atom_id: str, update_data: Dict) -> bool:
        """更新经历原子"""
        query = Query()
        return self.atoms_db.update(update_data, query.id == atom_id)

    def update_atom_weight(self, atom_id: str, weight: float) -> bool:
        """更新原子权重（基于反馈）"""
        query = Query()
        return self.atoms_db.update({"weight": weight}, query.id == atom_id)

    def delete_atom(self, atom_id: str) -> bool:
        """删除经历原子"""
        query = Query()
        return self.atoms_db.remove(query.id == atom_id)

    # ========== 投递追踪操作 ==========

    def save_application(self, application_data: Dict) -> str:
        """保存投递记录"""
        app_id = self.generate_id("app_")
        application_data["id"] = app_id
        application_data["applied_date"] = datetime.now().isoformat()
        if "status" not in application_data:
            application_data["status"] = "pending"
        self.applications_db.insert(application_data)
        return app_id

    def get_application(self, app_id: str) -> Optional[Dict]:
        """获取投递记录"""
        query = Query()
        return self.applications_db.get(query.id == app_id)

    def list_applications(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """列出投递记录"""
        if status:
            query = Query()
            apps = self.applications_db.search(query.status == status)
        else:
            apps = self.applications_db.all()
        apps.reverse()
        return apps[:limit]

    def update_application(self, app_id: str, update_data: Dict) -> bool:
        """更新投递记录"""
        query = Query()
        return self.applications_db.update(update_data, query.id == app_id)

    def delete_application(self, app_id: str) -> bool:
        """删除投递记录"""
        query = Query()
        return self.applications_db.remove(query.id == app_id)

    def get_stats(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        return {
            "resumes_count": len(self.resumes_db),
            "jobs_count": len(self.jobs_db),
            "matches_count": len(self.matches_db),
            "atoms_count": len(self.atoms_db) if hasattr(self, 'atoms_db') else 0,
            "applications_count": len(self.applications_db) if hasattr(self, 'applications_db') else 0
        }


# 全局数据库实例
_db_instance: Optional[Database] = None


def get_db(data_dir: str = "./data") -> Database:
    """获取数据库实例（单例模式）"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(data_dir)
    return _db_instance
