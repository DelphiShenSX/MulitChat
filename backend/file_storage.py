"""文件存储管理"""
import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class FileStorage:
    def __init__(self, topics_dir: str = None):
        self.topics_dir = Path(topics_dir) if topics_dir else (BASE_DIR / "data" / "topics")
        self.topics_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """将文本转换为安全的文件名"""
        sanitized = re.sub(r'[^\w\s-]', '', text)
        sanitized = re.sub(r'[\s]+', '_', sanitized)
        return sanitized[:max_length]

    def _generate_topic_summary(self, topic: str) -> str:
        """生成主题摘要作为目录名"""
        import hashlib
        hash_obj = hashlib.md5(topic.encode())
        short_topic = self._sanitize_filename(topic)[:40]
        return f"{short_topic}_{hash_obj.hexdigest()[:8]}"

    def get_topic_dir(self, topic_summary: str) -> Path:
        topic_dir = self.topics_dir / topic_summary
        topic_dir.mkdir(parents=True, exist_ok=True)
        return topic_dir

    def get_markdown_path(self, topic_summary: str) -> Path:
        return self.get_topic_dir(topic_summary) / "topic.md"

    def get_db_path(self, topic_summary: str) -> Path:
        return self.get_topic_dir(topic_summary) / "messages.db"

    def initialize_topic_file(self, topic_summary: str, topic: str):
        """初始化话题Markdown文件（只保存牵引主题）"""
        md_path = self.get_markdown_path(topic_summary)

        # 始终写入，确保牵引主题正确保存
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"【牵引主题】：{topic}\n")
            f.flush()
            os.fsync(f.fileno())

        return md_path

    def append_to_markdown(
        self,
        topic_summary: str,
        role: str,
        model_alias: Optional[str] = None,
        model_name: Optional[str] = None,
        content: str = "",
        is_system: bool = False
    ):
        """追加内容到Markdown文件"""
        md_path = self.get_markdown_path(topic_summary)

        if not md_path.exists():
            return False

        with open(md_path, "a", encoding="utf-8") as f:
            if model_alias:
                f.write(f"\n{model_alias}认为：\n")
            elif is_system:
                f.write(f"\n系统：\n")
            else:
                f.write("\n用户：\n")

            if content:
                # 统一换行符，去掉每行开头的 > 符号
                normalized = content.replace('\r\n', '\n').replace('\r', '\n')
                cleaned_lines = []
                for line in normalized.split('\n'):
                    stripped = line.lstrip()
                    if stripped.startswith('> '):
                        indent = line[:len(line) - len(stripped)]
                        cleaned_lines.append(indent + stripped[2:])
                    elif stripped.startswith('>'):
                        indent = line[:len(line) - len(stripped)]
                        cleaned_lines.append(indent + stripped[1:])
                    else:
                        cleaned_lines.append(line)
                cleaned_content = '\n'.join(cleaned_lines)
                f.write(f"{cleaned_content}\n")

            # 强制刷新缓冲区
            f.flush()
            os.fsync(f.fileno())

        return True

    def append_user_message(self, topic_summary: str, content: str):
        """追加用户消息"""
        return self.append_to_markdown(
            topic_summary,
            role="user",
            content=content
        )

    def append_ai_message(self, topic_summary: str, model_alias: str, model_name: str, content: str):
        """追加AI消息"""
        return self.append_to_markdown(
            topic_summary,
            role="assistant",
            model_alias=model_alias,
            model_name=model_name,
            content=content
        )

    def append_system_message(self, topic_summary: str, content: str):
        """追加系统消息"""
        return self.append_to_markdown(
            topic_summary,
            role="system",
            is_system=True,
            content=content
        )

    def terminate_discussion(self, topic_summary: str):
        """终止讨论并添加总结提示"""
        self.append_system_message(
            topic_summary,
            "本次讨论已终止。请基于以上全部内容，做出结构化总结。"
        )

    def read_full_content(self, topic_summary: str) -> str:
        """读取完整的Markdown内容"""
        md_path = self.get_markdown_path(topic_summary)
        if not md_path.exists():
            return ""
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()

    def list_topics(self) -> List[dict]:
        """列出所有话题"""
        topics = []
        if not self.topics_dir.exists():
            return topics

        for topic_dir in self.topics_dir.iterdir():
            if topic_dir.is_dir():
                md_path = topic_dir / "topic.md"
                db_path = topic_dir / "messages.db"
                if md_path.exists():
                    with open(md_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line.startswith("【牵引主题】："):
                            topic_name = first_line[7:].strip()
                        else:
                            topic_name = first_line

                    stat = topic_dir.stat()

                    # 获取最新的 session_id
                    session_id = None
                    if db_path.exists():
                        try:
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT id FROM sessions
                                ORDER BY updated_at DESC LIMIT 1
                            """)
                            row = cursor.fetchone()
                            conn.close()
                            if row:
                                session_id = row[0]
                        except sqlite3.Error:
                            pass

                    topics.append({
                        "summary": topic_dir.name,
                        "topic": topic_name,
                        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "id": session_id
                    })

        return sorted(topics, key=lambda x: x["updated_at"], reverse=True)

    def get_or_create_topic_summary(self, topic: str) -> str:
        """获取或创建主题摘要"""
        topic_hash = self._generate_topic_summary(topic)
        self.initialize_topic_file(topic_hash, topic)
        return topic_hash


file_storage = FileStorage()
