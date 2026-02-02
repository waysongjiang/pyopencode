"""
Todo与TodoList模块
支持添加、删除、完成标记与查询
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class Priority(Enum):
    """任务优先级"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"


class TodoStatus(Enum):
    """任务状态"""
    PENDING = "待办"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"
    CANCELLED = "已取消"


@dataclass
class Todo:
    """Todo任务类"""
    
    id: str
    title: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    status: TodoStatus = TodoStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.id:
            raise ValueError("Todo ID不能为空")
        if not self.title:
            raise ValueError("Todo标题不能为空")
    
    def mark_completed(self) -> None:
        """标记为已完成"""
        self.status = TodoStatus.COMPLETED
        self.updated_at = datetime.now()
    
    def mark_in_progress(self) -> None:
        """标记为进行中"""
        self.status = TodoStatus.IN_PROGRESS
        self.updated_at = datetime.now()
    
    def mark_cancelled(self) -> None:
        """标记为已取消"""
        self.status = TodoStatus.CANCELLED
        self.updated_at = datetime.now()
    
    def update_title(self, title: str) -> None:
        """更新标题"""
        if not title:
            raise ValueError("标题不能为空")
        self.title = title
        self.updated_at = datetime.now()
    
    def update_description(self, description: str) -> None:
        """更新描述"""
        self.description = description
        self.updated_at = datetime.now()
    
    def update_priority(self, priority: Priority) -> None:
        """更新优先级"""
        self.priority = priority
        self.updated_at = datetime.now()
    
    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()
    
    def remove_tag(self, tag: str) -> None:
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()
    
    def set_due_date(self, due_date: Optional[datetime]) -> None:
        """设置截止日期"""
        self.due_date = due_date
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Todo':
        """从字典创建Todo"""
        # 处理datetime字段
        created_at = datetime.fromisoformat(data["created_at"]) if data["created_at"] else datetime.now()
        updated_at = datetime.fromisoformat(data["updated_at"]) if data["updated_at"] else datetime.now()
        due_date = datetime.fromisoformat(data["due_date"]) if data["due_date"] else None
        
        # 处理枚举字段
        priority_map = {p.value: p for p in Priority}
        status_map = {s.value: s for s in TodoStatus}
        
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            priority=priority_map.get(data["priority"], Priority.MEDIUM),
            status=status_map.get(data["status"], TodoStatus.PENDING),
            created_at=created_at,
            updated_at=updated_at,
            due_date=due_date,
            tags=data.get("tags", [])
        )


class TodoList:
    """Todo列表管理类"""
    
    def __init__(self, name: str = "默认列表"):
        """
        初始化Todo列表
        
        Args:
            name: 列表名称
        """
        self.name = name
        self.todos: Dict[str, Todo] = {}
    
    def add_todo(self, todo: Todo) -> None:
        """
        添加Todo
        
        Args:
            todo: Todo对象
            
        Raises:
            ValueError: 如果Todo ID已存在
        """
        if todo.id in self.todos:
            raise ValueError(f"Todo ID '{todo.id}' 已存在")
        self.todos[todo.id] = todo
    
    def create_todo(self, title: str, description: str = "", **kwargs) -> Todo:
        """
        创建并添加Todo
        
        Args:
            title: 标题
            description: 描述
            **kwargs: 其他Todo参数
            
        Returns:
            创建的Todo对象
        """
        import uuid
        
        todo_id = str(uuid.uuid4())
        todo = Todo(
            id=todo_id,
            title=title,
            description=description,
            **kwargs
        )
        self.add_todo(todo)
        return todo
    
    def remove_todo(self, todo_id: str) -> bool:
        """
        移除Todo
        
        Args:
            todo_id: Todo ID
            
        Returns:
            是否成功移除
        """
        if todo_id in self.todos:
            del self.todos[todo_id]
            return True
        return False
    
    def get_todo(self, todo_id: str) -> Optional[Todo]:
        """
        获取Todo
        
        Args:
            todo_id: Todo ID
            
        Returns:
            Todo对象或None
        """
        return self.todos.get(todo_id)
    
    def get_all_todos(self) -> List[Todo]:
        """
        获取所有Todo
        
        Returns:
            Todo列表
        """
        return list(self.todos.values())
    
    def get_todos_by_status(self, status: TodoStatus) -> List[Todo]:
        """
        按状态筛选Todo
        
        Args:
            status: 状态
            
        Returns:
            符合条件的Todo列表
        """
        return [todo for todo in self.todos.values() if todo.status == status]
    
    def get_todos_by_priority(self, priority: Priority) -> List[Todo]:
        """
        按优先级筛选Todo
        
        Args:
            priority: 优先级
            
        Returns:
            符合条件的Todo列表
        """
        return [todo for todo in self.todos.values() if todo.priority == priority]
    
    def get_todos_with_tag(self, tag: str) -> List[Todo]:
        """
        按标签筛选Todo
        
        Args:
            tag: 标签
            
        Returns:
            符合条件的Todo列表
        """
        return [todo for todo in self.todos.values() if tag in todo.tags]
    
    def get_overdue_todos(self) -> List[Todo]:
        """
        获取过期的Todo
        
        Returns:
            过期的Todo列表
        """
        now = datetime.now()
        return [
            todo for todo in self.todos.values()
            if todo.due_date and todo.due_date < now and todo.status != TodoStatus.COMPLETED
        ]
    
    def get_todos_due_today(self) -> List[Todo]:
        """
        获取今天到期的Todo
        
        Returns:
            今天到期的Todo列表
        """
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
        
        return [
            todo for todo in self.todos.values()
            if todo.due_date and today_start <= todo.due_date <= today_end
        ]
    
    def mark_todo_completed(self, todo_id: str) -> bool:
        """
        标记Todo为已完成
        
        Args:
            todo_id: Todo ID
            
        Returns:
            是否成功标记
        """
        todo = self.get_todo(todo_id)
        if todo:
            todo.mark_completed()
            return True
        return False
    
    def mark_todo_in_progress(self, todo_id: str) -> bool:
        """
        标记Todo为进行中
        
        Args:
            todo_id: Todo ID
            
        Returns:
            是否成功标记
        """
        todo = self.get_todo(todo_id)
        if todo:
            todo.mark_in_progress()
            return True
        return False
    
    def mark_todo_cancelled(self, todo_id: str) -> bool:
        """
        标记Todo为已取消
        
        Args:
            todo_id: Todo ID
            
        Returns:
            是否成功标记
        """
        todo = self.get_todo(todo_id)
        if todo:
            todo.mark_cancelled()
            return True
        return False
    
    def search_todos(self, keyword: str) -> List[Todo]:
        """
        搜索Todo
        
        Args:
            keyword: 关键词
            
        Returns:
            符合条件的Todo列表
        """
        keyword_lower = keyword.lower()
        return [
            todo for todo in self.todos.values()
            if keyword_lower in todo.title.lower() or keyword_lower in todo.description.lower()
        ]
    
    def clear_completed(self) -> int:
        """
        清除所有已完成的Todo
        
        Returns:
            清除的数量
        """
        completed_ids = [
            todo_id for todo_id, todo in self.todos.items()
            if todo.status == TodoStatus.COMPLETED
        ]
        
        for todo_id in completed_ids:
            del self.todos[todo_id]
        
        return len(completed_ids)
    
    def count_by_status(self) -> Dict[TodoStatus, int]:
        """
        统计各状态的Todo数量
        
        Returns:
            状态到数量的映射
        """
        counts = {status: 0 for status in TodoStatus}
        for todo in self.todos.values():
            counts[todo.status] += 1
        return counts
    
    def count_by_priority(self) -> Dict[Priority, int]:
        """
        统计各优先级的Todo数量
        
        Returns:
            优先级到数量的映射
        """
        counts = {priority: 0 for priority in Priority}
        for todo in self.todos.values():
            counts[todo.priority] += 1
        return counts
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "todos": {todo_id: todo.to_dict() for todo_id, todo in self.todos.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TodoList':
        """从字典创建TodoList"""
        todo_list = cls(name=data["name"])
        for todo_id, todo_data in data["todos"].items():
            todo = Todo.from_dict(todo_data)
            todo_list.todos[todo_id] = todo
        return todo_list
    
    def save_to_file(self, filepath: str) -> None:
        """
        保存到文件
        
        Args:
            filepath: 文件路径
        """
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'TodoList':
        """
        从文件加载
        
        Args:
            filepath: 文件路径
            
        Returns:
            TodoList对象
        """
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


# 示例使用
if __name__ == "__main__":
    # 创建TodoList
    todo_list = TodoList("我的待办事项")
    
    # 创建Todo
    todo1 = todo_list.create_todo(
        title="学习Python",
        description="学习Python高级特性",
        priority=Priority.HIGH,
        tags=["学习", "编程"]
    )
    
    todo2 = todo_list.create_todo(
        title="购物",
        description="购买日常用品",
        priority=Priority.MEDIUM,
        tags=["生活"]
    )
    
    # 标记完成
    todo_list.mark_todo_completed(todo1.id)
    
    # 查询
    print(f"所有待办事项: {len(todo_list.get_all_todos())}")
    print(f"已完成: {len(todo_list.get_todos_by_status(TodoStatus.COMPLETED))}")
    print(f"高优先级: {len(todo_list.get_todos_by_priority(Priority.HIGH))}")
    
    # 统计
    print(f"状态统计: {todo_list.count_by_status()}")
    print(f"优先级统计: {todo_list.count_by_priority()}")