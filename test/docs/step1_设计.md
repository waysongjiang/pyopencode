# Todo与TodoList模块设计文档

## 概述

本文档描述了Todo与TodoList模块的数据结构与接口设计。该模块用于管理个人或团队的待办事项，支持添加、删除、完成标记与查询等功能。

## 设计目标

1. **功能完整性**：支持完整的待办事项管理功能
2. **易用性**：提供简洁直观的API接口
3. **可扩展性**：支持未来功能扩展
4. **数据持久化**：支持保存和加载数据
5. **类型安全**：使用Python类型注解提高代码质量

## 数据结构设计

### 1. 枚举类型

#### Priority（优先级）
```python
class Priority(Enum):
    LOW = "低"      # 低优先级
    MEDIUM = "中"   # 中优先级（默认）
    HIGH = "高"     # 高优先级
```

#### TodoStatus（任务状态）
```python
class TodoStatus(Enum):
    PENDING = "待办"        # 待办状态（默认）
    IN_PROGRESS = "进行中"  # 进行中
    COMPLETED = "已完成"    # 已完成
    CANCELLED = "已取消"    # 已取消
```

### 2. Todo类（单个待办事项）

#### 属性
| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| id | str | 唯一标识符 | 必填 |
| title | str | 任务标题 | 必填 |
| description | str | 任务描述 | 空字符串 |
| priority | Priority | 优先级 | Priority.MEDIUM |
| status | TodoStatus | 任务状态 | TodoStatus.PENDING |
| created_at | datetime | 创建时间 | 当前时间 |
| updated_at | datetime | 更新时间 | 当前时间 |
| due_date | Optional[datetime] | 截止日期 | None |
| tags | List[str] | 标签列表 | 空列表 |

#### 核心方法
1. **状态管理**
   - `mark_completed()`: 标记为已完成
   - `mark_in_progress()`: 标记为进行中
   - `mark_cancelled()`: 标记为已取消

2. **内容更新**
   - `update_title(title: str)`: 更新标题
   - `update_description(description: str)`: 更新描述
   - `update_priority(priority: Priority)`: 更新优先级

3. **标签管理**
   - `add_tag(tag: str)`: 添加标签
   - `remove_tag(tag: str)`: 移除标签

4. **数据转换**
   - `to_dict() -> Dict[str, Any]`: 转换为字典
   - `from_dict(data: Dict[str, Any]) -> Todo`: 从字典创建

### 3. TodoList类（待办事项列表）

#### 属性
| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| name | str | 列表名称 | "默认列表" |
| todos | Dict[str, Todo] | Todo字典（ID到Todo的映射） | 空字典 |

#### 核心方法

##### 1. 增删改查
- `add_todo(todo: Todo)`: 添加Todo
- `create_todo(title: str, ...) -> Todo`: 创建并添加Todo
- `remove_todo(todo_id: str) -> bool`: 移除Todo
- `get_todo(todo_id: str) -> Optional[Todo]`: 获取单个Todo
- `get_all_todos() -> List[Todo]`: 获取所有Todo

##### 2. 状态管理
- `mark_todo_completed(todo_id: str) -> bool`: 标记为已完成
- `mark_todo_in_progress(todo_id: str) -> bool`: 标记为进行中
- `mark_todo_cancelled(todo_id: str) -> bool`: 标记为已取消

##### 3. 查询筛选
- `get_todos_by_status(status: TodoStatus) -> List[Todo]`: 按状态筛选
- `get_todos_by_priority(priority: Priority) -> List[Todo]`: 按优先级筛选
- `get_todos_with_tag(tag: str) -> List[Todo]`: 按标签筛选
- `get_overdue_todos() -> List[Todo]`: 获取过期Todo
- `get_todos_due_today() -> List[Todo]`: 获取今天到期Todo
- `search_todos(keyword: str) -> List[Todo]`: 关键词搜索

##### 4. 统计功能
- `count_by_status() -> Dict[TodoStatus, int]`: 按状态统计
- `count_by_priority() -> Dict[Priority, int]`: 按优先级统计
- `clear_completed() -> int`: 清除已完成Todo

##### 5. 数据持久化
- `to_dict() -> Dict[str, Any]`: 转换为字典
- `from_dict(data: Dict[str, Any]) -> TodoList`: 从字典创建
- `save_to_file(filepath: str)`: 保存到文件
- `load_from_file(filepath: str) -> TodoList`: 从文件加载

## 接口设计

### 1. 创建与初始化

```python
# 创建TodoList
todo_list = TodoList(name="工作待办")

# 创建Todo
todo = Todo(
    id="task_001",
    title="完成项目报告",
    description="编写项目总结报告",
    priority=Priority.HIGH,
    tags=["工作", "报告"]
)

# 或使用便捷方法
todo = todo_list.create_todo(
    title="学习Python",
    description="学习装饰器",
    priority=Priority.MEDIUM
)
```

### 2. 基本操作

```python
# 添加
todo_list.add_todo(todo)

# 查询
todo = todo_list.get_todo("task_001")
all_todos = todo_list.get_all_todos()

# 更新状态
todo.mark_completed()
todo_list.mark_todo_completed("task_001")

# 删除
todo_list.remove_todo("task_001")
```

### 3. 高级查询

```python
# 按状态筛选
pending_todos = todo_list.get_todos_by_status(TodoStatus.PENDING)

# 按优先级筛选
high_priority = todo_list.get_todos_by_priority(Priority.HIGH)

# 按标签筛选
work_todos = todo_list.get_todos_with_tag("工作")

# 搜索
results = todo_list.search_todos("报告")

# 获取过期任务
overdue = todo_list.get_overdue_todos()
```

### 4. 统计与分析

```python
# 统计数量
status_counts = todo_list.count_by_status()
priority_counts = todo_list.count_by_priority()

# 清理已完成
cleared_count = todo_list.clear_completed()
```

### 5. 数据持久化

```python
# 保存数据
todo_list.save_to_file("todos.json")

# 加载数据
loaded_list = TodoList.load_from_file("todos.json")
```

## 使用示例

### 基本工作流

```python
# 1. 初始化
todo_list = TodoList("个人待办")

# 2. 添加任务
todo_list.create_todo("买菜", "去超市买菜", priority=Priority.MEDIUM)
todo_list.create_todo("写代码", "完成Python项目", priority=Priority.HIGH)

# 3. 标记完成
todo_list.mark_todo_completed(todo_id)

# 4. 查询统计
print(f"总任务数: {len(todo_list.get_all_todos())}")
print(f"待办任务: {len(todo_list.get_todos_by_status(TodoStatus.PENDING))}")

# 5. 保存数据
todo_list.save_to_file("my_todos.json")
```

### 高级功能示例

```python
# 设置截止日期
from datetime import datetime, timedelta
due_date = datetime.now() + timedelta(days=7)
todo.set_due_date(due_date)

# 标签管理
todo.add_tag("紧急")
todo.add_tag("个人")
todo.remove_tag("个人")

# 批量操作
# 获取所有高优先级任务
high_priority = todo_list.get_todos_by_priority(Priority.HIGH)

# 搜索包含特定关键词的任务
search_results = todo_list.search_todos("项目")
```

## 设计考虑

### 1. ID生成策略
- 使用UUID确保全局唯一性
- 在`create_todo`方法中自动生成

### 2. 时间管理
- `created_at`: 创建时间，不可修改
- `updated_at`: 更新时间，每次修改自动更新
- `due_date`: 截止日期，可选

### 3. 错误处理
- 验证输入参数（如空标题）
- 处理重复ID
- 处理不存在的Todo操作

### 4. 扩展性考虑
- 使用枚举类型便于扩展新状态或优先级
- 标签系统支持灵活分类
- 可序列化设计支持多种存储后端

## 未来扩展方向

1. **用户系统**：支持多用户
2. **协作功能**：共享待办列表
3. **提醒功能**：定时提醒
4. **分类系统**：更复杂的分类体系
5. **数据分析**：生成统计报告
6. **API接口**：提供RESTful API
7. **UI界面**：图形用户界面

## 总结

本设计提供了一个完整、可扩展的Todo管理系统，涵盖了从基础CRUD操作到高级查询统计的全套功能。通过清晰的接口设计和类型安全保证，使得模块易于使用和维护，同时为未来的功能扩展预留了空间。