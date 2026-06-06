# quset_answer 评论数据插入接口文档

向数据库表 **`quset_answer`** 写入采集评论。适用于 App 采集员上报、脚本批量导入等场景。

---

## 1. 接口概览

| 项目 | 说明 |
|------|------|
| **推荐地址** | `POST /api/v1/mobile/quset-answer/` |
| **兼容地址** | `POST /api/v1/mobile/comments/`（逻辑完全相同） |
| **完整 URL 示例** | `http://{host}:8000/api/v1/mobile/quset-answer/` |
| **Content-Type** | `application/json`（也支持 `application/x-www-form-urlencoded`） |
| **鉴权** | 必须，见下文 |
| **写入表** | `quset_answer` |

---

## 2. 鉴权 Header

```
Authorization: Bearer {登录返回的 token}
X-Device-Id: {device_id}    // 建议携带，与登录时一致
Content-Type: application/json
```

Token 通过 `POST /api/v1/mobile/login/` 获取，有效期默认 30 天。

---

## 3. 请求体字段

对应 `quset_answer` 表字段（`comment_id`、`create_time` 由服务端生成）：

```json
{
  "poiId": "988444",
  "user_name": "游客张三",
  "comment_content": "景色不错，值得推荐",
  "comment_grade": "5",
  "release_time": "2026-06-06 14:30:00",
  "user_id": "0",
  "comment_num": 0,
  "like_num": 0,
  "reply_num": 0,
  "c_num": 0,
  "reply_content": "",
  "reply_video": 0,
  "reply_img": 0
}
```

| 字段 | 必填 | 类型 | 数据库列 | 说明 |
|------|------|------|----------|------|
| poiId | 是 | string | poiId | 项目 ID，须在采集员授权列表中 |
| user_name | 是 | string | user_name | 评论者昵称 |
| comment_content | 是 | string | comment_content | 评论正文 |
| comment_grade | 是 | string | comment_grade | 评分，如 `"5"`、`"4.5"`、`"好评"` |
| release_time | 是 | string | release_time | 发布时间，格式 `YYYY-MM-DD HH:MM:SS` |
| user_id | 否 | string | user_id | 默认 `"0"` |
| comment_num | 否 | number | comment_num | 默认 `0` |
| like_num | 否 | int | like_num | 默认 `0` |
| reply_num | 否 | int | reply_num | 默认 `0` |
| c_num | 否 | int | c_num | 默认 `0` |
| reply_content | 否 | string | reply_content | 回复内容，默认空 |
| reply_video | 否 | int | reply_video | 默认 `0` |
| reply_img | 否 | int | reply_img | 默认 `0` |

**别名：** `poi_id` 可代替 `poiId`。

---

## 4. comment_id 生成规则

服务端自动生成主键，**无需上传**：

```
comment_id = MD5( user_name + comment_grade + comment_content )
```

- 编码：UTF-8  
- 输出：32 位小写 hex  

相同 `user_name + comment_grade + comment_content` 视为同一条评论，再次提交会 **更新（upsert）** 已有记录。

---

## 5. 成功响应

**HTTP 200**

```json
{
  "success": true,
  "message": "保存成功",
  "data": {
    "comment": {
      "comment_id": "a1b2c3d4e5f6789012345678901234ab",
      "poiId": "988444",
      "user_name": "游客张三",
      "comment_content": "景色不错，值得推荐",
      "comment_grade": "5",
      "comment_num": 0,
      "like_num": 0,
      "reply_num": 0,
      "c_num": 0,
      "user_id": "0",
      "reply_content": "",
      "reply_video": 0,
      "reply_img": 0,
      "release_time": "2026-06-06 14:30:00",
      "create_time": "2026-06-06 14:35:12"
    }
  }
}
```

---

## 6. 失败响应

| HTTP | message | 常见原因 |
|------|---------|----------|
| 401 | 无效或已过期的 Token | 未登录或 Token 失效 |
| 403 | 无权向该项目写入数据 | poiId 未在采集员授权列表 |
| 403 | 该评论已由其他采集员上报，无法覆盖 | comment_id 冲突 |
| 400 | poiId 不能为空 | 缺少 poiId |
| 400 | user_name / comment_content / comment_grade 不能为空 | 必填字段缺失 |
| 400 | release_time 格式无效 | 时间格式错误 |

示例：

```json
{
  "success": false,
  "message": "无权向该项目写入数据"
}
```

---

## 7. 调用流程

```
1. POST /api/v1/mobile/login/          → 获取 token
2. GET  /api/v1/mobile/projects/       → 确认 poiId 在授权列表
3. POST /api/v1/mobile/quset-answer/   → 插入评论到 quset_answer
```

---

## 8. curl 示例

### 8.1 登录

```bash
curl -s -X POST 'http://127.0.0.1:8000/api/v1/mobile/login/' \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "api_test_user",
    "password": "your_password",
    "device_id": "903d3643-b734-414d-918d-cefa467a234a",
    "device_info": "Xiaomi M2007J22C (Android 10)"
  }'
```

从响应中取出 `data.token`。

### 8.2 插入评论

```bash
TOKEN="替换为登录返回的 token"

curl -s -X POST 'http://127.0.0.1:8000/api/v1/mobile/quset-answer/' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'X-Device-Id: 903d3643-b734-414d-918d-cefa467a234a' \
  -d '{
    "poiId": "988444",
    "user_name": "测试用户",
    "comment_content": "接口写入测试评论",
    "comment_grade": "5",
    "release_time": "2026-06-06 15:00:00",
    "like_num": 3
  }'
```

### 8.3 查询当天已写入数据（可选）

```bash
curl -s "http://127.0.0.1:8000/api/v1/mobile/comments/?poiId=988444&mine=1" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'X-Device-Id: 903d3643-b734-414d-918d-cefa467a234a'
```

---

## 9. 业务规则摘要

1. 仅可向 **后台「采集用户管理」已授权** 的 `poiId` 写入。  
2. `create_time` 首次插入时由服务端写入当前时间；更新时不强制修改。  
3. 同一 `comment_id` 重复提交：更新字段，归属原采集员；其他采集员无法覆盖。  
4. 修改已存在评论请使用 `PUT /api/v1/mobile/comments/{comment_id}/`（仅限当天、本人上报）。

---

## 10. 相关文档

- 完整 Mobile API：`docs/MOBILE_API.md`  
- 采集员登录、项目权限、设备换绑等同文档第 3～6 节
