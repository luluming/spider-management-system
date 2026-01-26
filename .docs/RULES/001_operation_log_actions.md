## 操作日志动作维护规范

1. `accounts/models.py::OperationLog.ACTION_CHOICES` 定义了系统允许的操作类型。
2. 任意代码新增或修改操作日志时，若使用新的 `action` 值，必须同步更新该枚举并运行 `python manage.py makemigrations accounts`。
3. 更新后需补充对应的中文描述，确保后台展示友好。
4. 若发现未来动作值持续增长，可评估改为集中常量或配置化管理，并在文档中另行说明。


