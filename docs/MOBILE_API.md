# App 采集员 Mobile API 接口文档

版本：**v1**  
Base URL：`http(s)://{host}/api/v1/mobile/`  
数据格式：**JSON**  
字符编码：**UTF-8**  
时区：**Asia/Shanghai**

---

## 1. 通用约定

### 1.1 响应结构

```json
{
  "success": true,
  "message": "说明文字",
  "data": {}
}
```

| HTTP 状态码 | 含义 |
|------------|------|
| 200 | 成功（业务失败时 `success=false` 也可能返回 200，以 `success` 为准） |
| 400 | 参数错误 |
| 401 | Token 无效 / 账号密码错误 |
| 403 | 无权限 / 设备未授权 / 账号禁用 |
| 404 | 资源不存在 |
| 423 | 账号锁定 |

### 1.2 鉴权 Header（除登录、验证码、换绑发起/验证外）

```
Authorization: Bearer {token}
X-Device-Id: {device_id}    // 建议始终携带
Content-Type: application/json
```

### 1.3 comment_id 生成规则

```
comment_id = MD5( user_name + comment_grade + comment_content )
```

- 编码：UTF-8  
- 输出：32 位小写 hex  
- 相同三要素视为同一条评论（upsert）

---

## 2. 验证码

### GET `/captcha/`

获取图形验证码（无需登录）。

**响应示例：**

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "captcha_id": "a1b2c3d4e5f6....",
    "captcha_image": "iVBORw0KGgo...",
    "expires_in": 300
  }
}
```

| 字段 | 说明 |
|------|------|
| captcha_id | 验证码 ID，登录时回传 |
| captcha_image | PNG 图片 Base64（不含 `data:image/png;base64,` 前缀） |
| expires_in | 有效秒数（300 秒） |

---

## 3. 登录 / 登出

### POST `/login/`

**请求体：**

```json
{
  "username": "collector01",
  "password": "your_password",
  "device_id": "uuid-device-id",
  "device_info": "Android 14 / 小米14",
  "captcha_id": "验证码ID",
  "captcha_code": "AB12"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| username | 是 | App 采集员账号 |
| password | 是 | 密码 |
| device_id | 是 | 设备唯一 ID |
| device_info | 否 | 设备描述 |
| captcha_id | 是 | 图形验证码 ID |
| captcha_code | 是 | 用户输入的验证码 |

**成功响应：**

```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "token": "xxx",
    "expires_at": "2026-07-03 12:00:00",
    "collector": {
      "id": 1,
      "username": "collector01",
      "display_name": "张三"
    }
  }
}
```

**设备不匹配（403）：**

```json
{
  "success": false,
  "message": "设备未授权，请发起设备换绑申请",
  "data": { "error_code": "DEVICE_MISMATCH" }
}
```

**安全策略：**

- 连续 5 次密码错误 → 锁定 30 分钟（HTTP 423）
- 首次登录自动绑定 `device_id`
- Token 有效期 30 天

---

### POST `/logout/`

需 Bearer Token。使当前 Token 失效。

**响应：**

```json
{ "success": true, "message": "已退出登录" }
```

---

## 4. 授权项目

### GET `/projects/`

返回当前采集员被授权的项目，按平台分组。

**响应：**

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "platforms": [
      {
        "platform": "抖音",
        "items": [
          { "poiId": "1234567890", "itemName": "深圳世界之窗" }
        ]
      }
    ],
    "total_count": 1
  }
}
```

---

## 5. 评论数据

### POST `/comments/`

上报评论，写入 `quset_answer` 表。仅可向**已授权 poiId** 写入。

**请求体：**

```json
{
  "poiId": "1234567890",
  "user_name": "游客张三",
  "comment_content": "景色不错，值得推荐",
  "comment_grade": "5",
  "release_time": "2026-06-03 14:30:00",
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

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| poiId | 是 | string | 项目 ID，须在授权列表 |
| user_name | 是 | string | 评论者昵称 |
| comment_content | 是 | string | 评论正文 |
| comment_grade | 是 | string | 评分（生产库为 varchar，如 `"5"`、`"4.5"`、`"好评"`） |
| release_time | 是 | string | 发布时间 `YYYY-MM-DD HH:MM:SS` |
| user_id | 否 | string | 默认 `"0"` |
| comment_num | 否 | number | 默认 0 |
| like_num | 否 | int | 默认 0 |
| reply_num | 否 | int | 默认 0 |
| c_num | 否 | int | 默认 0 |
| reply_content | 否 | string | 回复内容 |
| reply_video | 否 | int | 默认 0 |
| reply_img | 否 | int | 默认 0 |

**说明：**

- `comment_id` 服务端按 MD5 规则生成，无需上传  
- `create_time` 服务端自动写入  
- 若 `comment_id` 已存在且属于其他采集员 → 403  
- 未授权 poiId → 403  

**成功响应：**

```json
{
  "success": true,
  "message": "保存成功",
  "data": {
    "comment": {
      "comment_id": "a1b2c3d4e5f6789012345678901234ab",
      "poiId": "1234567890",
      "user_name": "游客张三",
      "comment_content": "景色不错，值得推荐",
      "comment_grade": "5",
      "release_time": "2026-06-03 14:30:00",
      "create_time": "2026-06-03 14:35:00"
    }
  }
}
```

**专用插入路径（与 POST `/comments/` 相同）：** `POST /quset-answer/`  
详见：`docs/QusetAnswer_INSERT_API.md`

---

### GET `/comments/`

查询**当天**评论（按 `release_time` 日期，服务器时区 Asia/Shanghai）。

**Query 参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| poiId | 是 | 项目 ID |
| mine | 否 | `1` 时仅返回**自己上报**的评论 |
| page | 否 | 页码，默认 1 |
| page_size | 否 | 每页条数，默认 20，最大 100 |

**示例：** `GET /comments/?poiId=1234567890&mine=1&page=1`

**响应：**

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "items": [
      {
        "comment_id": "abc123...",
        "poiId": "1234567890",
        "user_name": "游客张三",
        "comment_content": "...",
        "comment_grade": "5",
        "comment_num": 0,
        "like_num": 0,
        "reply_num": 0,
        "c_num": 0,
        "user_id": "0",
        "reply_content": "",
        "reply_video": 0,
        "reply_img": 0,
        "release_time": "2026-06-03 14:30:00",
        "create_time": "2026-06-03 14:35:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

### PUT `/comments/{comment_id}/`

修改评论。**仅可修改自己上报的、且 release_time 为当天的评论。**

**不可修改：** `user_name`（会导致 comment_id 变化）

**可修改字段：** `comment_content`、`comment_grade`、`comment_num`、`like_num`、`reply_num`、`c_num`、`user_id`、`reply_content`、`reply_video`、`reply_img`、`release_time`

**请求示例：**

```json
{
  "comment_content": "更新后的评论内容",
  "comment_grade": "4",
  "like_num": 10
}
```

---

## 6. 设备换绑

流程：**新设备发起 → 旧设备查看验证码 → 新设备输入验证码 → 管理员审批 → 新设备完成绑定**

### POST `/device/rebind/request/`

新设备发起换绑（无需 Token，需图形验证码 + 账号密码）。

```json
{
  "username": "collector01",
  "password": "your_password",
  "device_id": "new-device-uuid",
  "device_info": "Android 14",
  "captcha_id": "...",
  "captcha_code": "AB12"
}
```

**响应：**

```json
{
  "success": true,
  "message": "换绑申请已创建，请在旧设备查看验证码",
  "data": {
    "request_id": 1,
    "request_no": "RB20260603143022001",
    "status": "pending_old_verify",
    "verify_expires_at": "2026-06-03 14:45:00"
  }
}
```

---

### GET `/device/rebind/pending/`

**旧设备**调用（需 Token）。获取待验证的换绑申请及 6 位验证码。

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "pending": true,
    "request_id": 1,
    "request_no": "RB20260603143022001",
    "new_device_info": "Android 14",
    "verify_code": "583921",
    "verify_expires_at": "2026-06-03 14:45:00",
    "status": "pending_old_verify"
  }
}
```

---

### POST `/device/rebind/verify/`

**新设备**提交旧设备上看到的验证码（无需 Token）。

```json
{
  "request_id": 1,
  "verify_code": "583921"
}
```

成功后状态变为 `pending_admin`（待管理员审批）。

---

### GET `/device/rebind/status/`

轮询换绑进度（无需 Token）。

**Query：** `request_id=1` 或 `request_no=RB20260603143022001`

**响应 status 枚举：**

| status | 说明 |
|--------|------|
| pending_old_verify | 待旧设备验证 |
| pending_admin | 待管理员审批 |
| approved | 已批准，请完成绑定 |
| completed | 已完成 |
| rejected | 已拒绝 |
| expired | 已过期 |
| cancelled | 已取消 |

---

### POST `/device/rebind/complete/`

管理员批准后，**新设备**完成换绑并获取 Token。

```json
{
  "request_id": 1,
  "username": "collector01",
  "password": "your_password",
  "device_id": "new-device-uuid",
  "device_info": "Android 14",
  "captcha_id": "...",
  "captcha_code": "AB12"
}
```

**也可：** 审批通过后直接调用 `/login/`（device_id 与申请一致），系统自动完成换绑。

---

### POST `/device/rebind/cancel/`

取消换绑（仅 `pending_old_verify` 状态）。

```json
{ "request_id": 1 }
```

---

## 7. 典型调用顺序

### 7.1 首次使用

1. `GET /captcha/`  
2. `POST /login/`（首次绑定 device_id）  
3. `GET /projects/`  
4. `POST /comments/` 上报数据  

### 7.2 换机

1. 新设备 `POST /device/rebind/request/`  
2. 旧设备 `GET /device/rebind/pending/` 查看验证码  
3. 新设备 `POST /device/rebind/verify/`  
4. 管理员 Web 后台审批（`/app-device-rebind/`）  
5. 新设备 `GET /device/rebind/status/` 轮询至 `approved`  
6. 新设备 `POST /device/rebind/complete/` 或 `POST /login/`  

---

## 8. Web 管理入口（管理员）

| 页面 | URL |
|------|-----|
| App 采集员管理 | `/app-collector-management/` |
| 采集员项目权限 | `/app-collector-permissions/{id}/` |
| 设备换绑审批 | `/app-device-rebind/` |

---

## 9. curl 示例

```bash
# 1. 获取验证码
curl -s http://127.0.0.1:8000/api/v1/mobile/captcha/

# 2. 登录
curl -s -X POST http://127.0.0.1:8000/api/v1/mobile/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"collector01","password":"pass123","device_id":"dev-001","device_info":"Test","captcha_id":"...","captcha_code":"AB12"}'

# 3. 获取项目
curl -s http://127.0.0.1:8000/api/v1/mobile/projects/ \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Device-Id: dev-001'

# 4. 上报评论
curl -s -X POST http://127.0.0.1:8000/api/v1/mobile/comments/ \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"poiId":"123","user_name":"张三","comment_content":"很好","comment_grade":"5","release_time":"2026-06-03 10:00:00"}'
```

---

## 10. 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-03 | 初版：采集员独立账号、项目权限、评论上报、设备换绑 |
