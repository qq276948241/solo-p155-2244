# 社区废品回收预约系统 - 架构速览

给新来的同学快速建立整体认知用的。不用太纠结细节，知道东西在哪里就行。

---

## 一、整体分层结构

项目用 FastAPI，分层是经典的 MVC 变体，东西不多，文件夹一眼能看完：

```
project155/
├── app/
│   ├── main.py              ← 入口，注册路由、建表、加 CORS
│   ├── config.py            ← 读 .env，所有配置都在这里
│   ├── database.py          ← SQLAlchemy engine + SessionLocal + Base
│   ├── models.py            ← 数据库表（SQLAlchemy ORM 模型）
│   ├── schemas.py           ← 请求/响应体（Pydantic 模型）
│   ├── dependencies.py      ← 依赖注入：拿 DB 会话、拿当前用户、鉴权
│   ├── utils/
│   │   ├── security.py      ← JWT 签发/解析 + 密码哈希
│   │   └── pricing.py       ← 定价计算逻辑
│   └── routers/             ← 路由层（按业务模块拆分）
│       ├── auth.py          ← 注册/登录
│       ├── users.py         ← 用户信息 + 地址 CRUD
│       ├── pricing.py       ← 品类 + 价格计算
│       ├── orders.py        ← 订单 CRUD + 改期 + 取消
│       ├── reviews.py       ← 评价（居民打分、回收员看平均分）
│       └── collector.py     ← 回收员：接单/开始/完成、今日路线
├── init_data.py             ← 初始化品类和测试账号
├── start_server.py          ← 启动 uvicorn
├── requirements.txt
├── .env
└── recycle.db               ← SQLite 数据库文件（运行后自动生成）
```

**每层的职责：**

| 层 | 放在哪里 | 做什么 | 不该做什么 |
|---|---|---|---|
| 配置 | `config.py` | 读环境变量，提供 `settings` 对象 | 别写死密码 |
| 数据模型 | `models.py` | 定义表结构和关系 | 别放业务逻辑 |
| 请求/响应 | `schemas.py` | 定义接口入参出参，做参数校验 | 别查数据库 |
| 路由 | `routers/*.py` | 处理 HTTP 请求，组装响应 | 复杂逻辑抽到 utils |
| 工具逻辑 | `utils/*.py` | 纯函数/业务逻辑（JWT、定价） | 别依赖 Request |
| 依赖 | `dependencies.py` | DB 会话、当前用户、角色权限 | 别写业务 |

---

## 二、数据库表关系

一共 6 张表，核心关系是「用户下单 → 订单挂明细 → 完成后评价」：

```
┌─────────┐     ┌───────────┐     ┌──────────┐
│ users   │1───N│ addresses │     │categories│
│ (用户)  │     │ (收货地址)│     │ (废品品类)│
└────┬────┘     └─────┬─────┘     └────┬─────┘
     │1              1│                │1
     │                │                │
     │N               │                │N
┌────┴────────────────┴────────┐  ┌────┴──────┐
│         orders               │  │order_items │
│         (订单)                │N-1│ (订单明细) │
└────┬──────────────┬───────────┘  └───────────┘
     │1             │1
     │              │
     │N             │1
┌────┴───┐     ┌────┴────┐
│ratings │     │  users  │
│(评价表)│     │(回收员)  │
└────────┘     └─────────┘
```

逐张说：

### 1. `users` — 用户
- 三种角色：`resident`（居民）、`collector`（回收员）、`admin`（管理员）
- 密码存的是 bcrypt hash，见 [security.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo155/project155/app/utils/security.py)

```python
# models.py 关键定义
class User(Base):
    id            = Column(Integer, primary_key=True)
    phone         = Column(String(20), unique=True)   # 用手机号登录
    password_hash = Column(String(255))
    name          = Column(String(50))
    role          = Column(String(20))                # resident / collector / admin
```

### 2. `addresses` — 收货地址
- 一个用户可以有多个地址，`is_default` 标记默认地址
- 订单创建时会记录 `address_id`，地址即使后来删了，订单详情也保留历史快照（但这里实际用了外键关系，删地址会触发 order → address，所以这里用了 lazy load，没做快照，注意下）

### 3. `categories` — 废品品类
- 存每个品类的单价 `unit_price`
- 目前内置 4 种：纸板(paper 1.2/kg)、塑料(plastic 0.8/kg)、金属(metal 3.0/kg)、织物(textile 0.5/kg)
- `is_active` 软停用，下架时不用真删

### 4. `orders` — 订单主表
- `status` 流转：`pending` → `assigned` → `in_progress` → `completed`
- 或者：`pending` → `cancelled`
- 时间用 `scheduled_date`（日期）+ `scheduled_time_slot`（morning/afternoon/all_day），不是精确到分钟的时间段

```python
# orders.py 里订单状态变更的位置
order.status = "pending"       # 创建时
order.status = "assigned"      # 回收员接单 /collector/orders/{id}/accept
order.status = "in_progress"   # 回收员出发 /collector/orders/{id}/start
order.status = "completed"     # 回收完成 /collector/orders/{id}/complete
order.status = "cancelled"     # 居民取消 /orders/{id}/cancel
```

### 5. `order_items` — 订单明细
- 每个品类一行，记录 `estimated_weight`（预约时预估）和 `actual_weight`（上门后实际称重）
- 下单时就把 `unit_price` 和 `subtotal` 快照存下来，避免后面品类调价导致历史订单价格变了

### 6. `ratings` — 评价表
- `order_id` 设了 `unique=True`，一个订单只能评一次（数据库级保障）
- 只有 `role == resident` 且是下单人本人才能提交，见 [reviews.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo155/project155/app/routers/reviews.py#L15-L80)

---

## 三、JWT 认证流程

链路不复杂，从请求头一路走到路由函数里的 `current_user`：

```
客户端请求
  │
  ▼ Header: Authorization: Bearer <token>
  │
dependencies.py: get_current_user()
  │ 1. HTTPBearer 从 Header 里抠出 token
  │ 2. decode_token() 解析 JWT → 拿到 {user_id, role, exp}
  │ 3. 查 users 表拿到 User 对象
  │ 4. 过期/解析失败/用户不存在 → 直接抛 401
  ▼
（可选）角色鉴权依赖：
  ├─ get_current_resident  → role == resident 或 admin？不！居民评价接口现在要求必须严格 == resident
  ├─ get_current_collector → role in [collector, admin]
  └─ get_current_admin     → role == admin
  ▼
路由函数参数：current_user: User = Depends(get_current_user)
```

### 签发 Token（登录时）

```python
# auth.py /login 接口
access_token = create_access_token(user_id=user.id, role=user.role)

# security.py
def create_access_token(user_id: int, role: str, expires_delta=None):
    to_encode = {"user_id": user_id, "role": role}
    # 默认过期时间 24 小时（ACCESS_TOKEN_EXPIRE_MINUTES=1440）
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
```

Token 里存了 3 个字段：
- `user_id`：查库用的主键
- `role`：权限判断，避免每次查库
- `exp`：过期时间，JWT 自动校验

### 实际用例：居民评价接口的鉴权

[reviews.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo155/project155/app/routers/reviews.py#L15-L80) 里的 `rate_order` 没走 `get_current_resident`（因为那个依赖允许 admin 通行），而是自己写了两道校验：

```python
def rate_order(current_user: User = Depends(get_current_user), ...):
    # 关卡1: 角色必须严格是 resident（admin/collector 都不行）
    if current_user.role != "resident":
        raise HTTPException(403, "只有居民用户才能评价订单")

    order = db.query(Order).filter(Order.id == order_id).first()

    # 关卡2: token 里的 user_id 必须等于订单的下单人
    if order.user_id != current_user.id:
        raise HTTPException(403, "只能评价自己的订单")
```

---

## 四、定价计算逻辑

定价是个独立模块，**单独抽了接口**，创建订单时内部也会复用同一段逻辑。

### 放在哪里

核心纯函数在 [utils/pricing.py](file:///d:/code/ai-prompt/solo-chrome-dev-F12/repos/repo155/project155/app/utils/pricing.py) 的 `calculate_pricing()`。

### 计算逻辑

```python
# utils/pricing.py
def calculate_pricing(db: Session, items: List[PricingItem]):
    """
    入参: [
      {"category_code": "paper",   "estimated_weight": 5.5},
      {"category_code": "plastic", "estimated_weight": 2.0},
    ]
    """
    # 1. 查出所有启用的品类，按 code 建索引
    category_map = {cat.code: cat for cat in db.query(Category).filter(is_active=True).all()}

    total_amount = 0.0
    total_weight = 0.0
    details = []

    for item in items:
        category = category_map[item.category_code]
        # 2. 每行：小计 = 单价 × 预估重量
        subtotal = round(category.unit_price * item.estimated_weight, 2)
        total_amount += subtotal
        total_weight += item.estimated_weight
        details.append({
            "category_code": category.code,
            "category_name": category.name,
            "unit_price": category.unit_price,   # 单价
            "estimated_weight": ...,             # 重量
            "subtotal": subtotal                 # 这行多少钱
        })

    # 3. 返回：每行明细 + 总计 + 总重量
    return PricingResponse(
        details=details,              # 前端展示用，每行的钱一目了然
        total_amount=round(total_amount, 2),
        total_weight=round(total_weight, 2)
    ), order_items_data               # 第二个返回值给创建订单时入库用
```

### 被谁调用

1. **定价接口 `POST /pricing/calculate`**
   - 前端让居民选品类+填重量后，实时算钱展示
   - 直接调用 `calculate_pricing()`，把结果返回给前端

2. **创建订单 `POST /orders`**
   - 前端传的是 `category_id`，不是 code，所以要先把 id 转成 code 组装成 `PricingItem`
   - 调用同一个 `calculate_pricing()`，拿到的结果里每行的 `unit_price` 和 `subtotal` 直接存进 `order_items` 表
   - 好处：两个入口用完全相同的计算逻辑，不会出现「前端显示 6 块，下单后变成 5 块」的尴尬

---

## 五、核心链路示例：从预约到完成到评价

帮你把几个模块串起来，跑一次脑子里就有图了：

```
1. 居民登录 /auth/login
   ↓ 拿到 JWT

2. 居民选品类填重量 → 调用 /pricing/calculate
   ↓ 返回明细和总价（让居民看一眼多少钱）

3. 居民确认 → 调用 POST /orders
   ├─ orders.py: create_order()
   ├─ 内部复用 calculate_pricing() 算钱，快照存 order_items
   └─ 订单状态：pending

4. 回收员登录 → GET /collector/orders/today 看今天有哪些单

5. 回收员点击「接单」→ PUT /collector/orders/{id}/accept
   ↓ 订单状态：pending → assigned

6. 回收员出发 → PUT /collector/orders/{id}/start
   ↓ 订单状态：assigned → in_progress

7. 回收员上门称重 → PUT /collector/orders/{id}/complete
   ├─ 填实际重量 actual_weight 和总钱数 total_amount
   └─ 订单状态：in_progress → completed

8. 居民满意 → POST /orders/{id}/rate
   ├─ reviews.py: rate_order()
   ├─ 校验：role==resident + 是下单人本人 + 订单==completed + 未评过
   └─ 写 ratings 表，score 1-5 星

9. 其他居民点回收员头像 → GET /orders/collector/{id}/ratings
   ← 看到：平均分、总评价数、每条评价的打分+评语
```

---

## 六、去哪里改什么

| 想做的事 | 改哪里 |
|---|---|
| 加新接口 | 对应模块的 `routers/*.py` |
| 加新表 | `models.py`，然后在 `main.py` 的 `Base.metadata.create_all()` 会自动建 |
| 改参数校验 | `schemas.py` |
| 改品类单价 | 管理后台接口目前在 `pricing.py` 的 `POST /categories`（需 admin） |
| 改价格算法 | `utils/pricing.py` 的 `calculate_pricing()` |
| 加新权限角色 | `dependencies.py` 加新的 `get_current_xxx` 函数 |
| 改 Token 过期时间 | `.env` 里的 `ACCESS_TOKEN_EXPIRE_MINUTES` |

---

好了，差不多就这些。跑完 `test_api.py` 和 `test_rating_permission.py` 这两个脚本，上面的流程基本都过一遍了，剩下的就是自己动手改几个接口找找感觉。
