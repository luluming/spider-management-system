- **背景**  
  配置管理模块的新增配置弹窗在提交后返回失败，导致无法保存新配置。需要明确根因并制定修复方案。

- **现状与证据**  
  - 前端 `/add-spider/` Ajax 请求返回 `success: false`。  
  - `spiders/views.py::add_spider` 在成功写入 `SpiderBase` 后调用 `OperationLog.objects.create(... action='create')`。  
  - `accounts/models.py::OperationLog.ACTION_CHOICES` 未包含 `'create'`/`'update'`/`'delete'`/`'add_data'`/`'edit_data'`。
  - 运行时会触发 `ValueError: '"create" is not a valid choice'`，导致保存流程回滚。

- **根因分析**  
  操作日志模型的 `action` 字段使用受限枚举，但视图层新增了额外的操作类型，未同步更新枚举，造成新增/编辑/删除配置及其他功能的日志写入失败。

- **目标**  
  允许配置新增等操作成功写入日志并完成保存；保证其他使用新动作值的接口同样可正常运行。

- **方案选项**  
  1. **扩展枚举列表（推荐）**：在 `OperationLog.ACTION_CHOICES` 中补充所有实际使用的动作值。维护量低，无需数据库迁移。  
  2. 移除枚举限制：将 `choices` 去除或改为自由文本，牺牲结构化约束。  
  3. 新增动作映射层：在记录日志前统一将动作值映射到枚举范围，增加维护复杂度。

- **推荐方案**  
  采用选项 1：在模型中补充 `'create'`、`'update'`、`'delete'`、`'add_data'`、`'edit_data'` 等当前代码引用的动作；若后续扩展需更新文档与模型保持同步。

- **实施步骤**  
  1. 更新 `accounts/models.py::OperationLog.ACTION_CHOICES`，新增缺失的动作值。  
  2. （可选）在文档中记录日志动作管理规范，提醒新增动作需同步更新。  
  3. 执行 `python manage.py makemigrations` 验证无需迁移；运行关键单元测试或最小化集成测试。  
  4. 手动或通过测试脚本调用 `/add-spider/` 接口验证返回成功，并检查日志写入。

- **测试计划**  
  - 运行现有 `test_fix.py`（涉及 OperationLog 创建）验证不受影响。  
  - 若时间允许，编写新增单元测试覆盖 `OperationLog` 的新增动作值。  
  - 手动通过 `manage.py shell` 或 API 调用模拟新增配置，确认响应成功且日志记录包含新动作。

- **风险与缓解**  
  - **遗漏其他动作值**：需要代码搜索确认（已通过 `rg "action='"` 覆盖）。  
  - **后续新增动作未同步**：在 `.docs/RULES` 中补充约束或在代码中集中定义动作常量。

- **交付物**  
  - 更新后的 `accounts/models.py`。  
  - （可选）文档更新：在 `.docs/RULES` 或 `.docs/STATE` 记录动作维护规范。  
  - 测试结果记录。


