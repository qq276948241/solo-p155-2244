import requests
import json
from datetime import date, timedelta

BASE = "http://localhost:8000"
tomorrow = (date.today() + timedelta(days=1)).isoformat()
H = {"Content-Type": "application/json"}

def login(phone, password):
    r = requests.post(f"{BASE}/auth/login", json={"phone": phone, "password": password}, headers=H)
    return r.json()["access_token"]

def auth_headers(token):
    return {**H, "Authorization": f"Bearer {token}"}

print("=" * 60)
print("评价权限校验测试")
print("=" * 60)

# 1. 准备测试数据
r1_token = login("13800000001", "123456")  # 居民1 - 张居民
r2_token = login("13800000002", "123456")  # 居民2 - 李居民
c_token = login("13900000001", "123456")   # 回收员 - 王回收
a_token = login("13700000001", "123456")   # 管理员

r1H = auth_headers(r1_token)
r2H = auth_headers(r2_token)
cH = auth_headers(c_token)
aH = auth_headers(a_token)

# 居民1添加地址
r = requests.post(f"{BASE}/users/addresses", json={
    "province": "广东省", "city": "深圳市", "district": "南山区",
    "detail": "测试地址", "contact_name": "张居民",
    "contact_phone": "13800000001", "is_default": True
}, headers=r1H)
addr_id = r.json()["id"]

# 居民1创建订单
r = requests.post(f"{BASE}/orders", json={
    "scheduled_date": tomorrow,
    "scheduled_time_slot": "morning",
    "address_id": addr_id,
    "items": [{"category_id": 1, "estimated_weight": 5}]
}, headers=r1H)
order_id = r.json()["id"]
print(f"[1] 居民1创建订单 id={order_id}")

# 回收员接单、开始、完成
r = requests.put(f"{BASE}/collector/orders/{order_id}/accept", headers=cH)
print(f"[2] 回收员接单: {r.status_code}")
r = requests.put(f"{BASE}/collector/orders/{order_id}/start", headers=cH)
print(f"[3] 回收员开始: {r.status_code}")
r = requests.put(f"{BASE}/collector/orders/{order_id}/complete", json={
    "actual_weight": 5, "total_amount": 6
}, headers=cH)
print(f"[4] 回收员完成: {r.status_code}")

print("\n" + "=" * 60)
print("权限拦截测试")
print("=" * 60)

# 测试1: 回收员给自己打分 - 应被拦截 403
r = requests.post(f"{BASE}/orders/{order_id}/rate", json={
    "score": 5, "comment": "回收员给自己打满分嘿嘿"
}, headers=cH)
print(f"[5] 回收员评价自己的订单: {r.status_code} -> {r.json()['detail']}")
assert r.status_code == 403, "回收员应该被拦截"

# 测试2: 管理员评价 - 应被拦截 403
r = requests.post(f"{BASE}/orders/{order_id}/rate", json={
    "score": 5, "comment": "管理员也来评价"
}, headers=aH)
print(f"[6] 管理员评价订单: {r.status_code} -> {r.json()['detail']}")
assert r.status_code == 403, "管理员应该被拦截"

# 测试3: 其他居民评价 - 应被拦截 403（不是下单人）
r = requests.post(f"{BASE}/orders/{order_id}/rate", json={
    "score": 1, "comment": "我是李居民，我来评价别人的订单"
}, headers=r2H)
print(f"[7] 其他居民评价: {r.status_code} -> {r.json()['detail']}")
assert r.status_code == 403, "其他居民应该被拦截"

# 测试4: 居民1本人评价 - 应该成功 201
r = requests.post(f"{BASE}/orders/{order_id}/rate", json={
    "score": 5, "comment": "回收员服务很好，准时上门！"
}, headers=r1H)
print(f"[8] 下单人本人评价: {r.status_code}")
assert r.status_code == 201, "下单人应该能评价"

# 测试5: 再次评价 - 应被拦截 409 幂等
r = requests.post(f"{BASE}/orders/{order_id}/rate", json={
    "score": 1, "comment": "再评一次"
}, headers=r1H)
print(f"[9] 重复评价: {r.status_code} -> {r.json()['detail']}")
assert r.status_code == 409, "重复评价应该被拦截"

# 测试6: 未登录评价 - 应被拦截 401
r = requests.post(f"{BASE}/orders/{order_id}/rate", json={
    "score": 5, "comment": "未登录评价"
}, headers=H)
print(f"[10] 未登录评价: {r.status_code}")
assert r.status_code == 401, "未登录应该被拦截"

print("\n" + "=" * 60)
print("其他接口权限验证（GET 接口）")
print("=" * 60)

# 测试7: 回收员查看订单评价 - 应该能看到 200
r = requests.get(f"{BASE}/orders/{order_id}/rate", headers=cH)
print(f"[11] 回收员查看评价: {r.status_code}")
assert r.status_code == 200, "查看评价应该对所有登录用户开放"

# 测试8: 回收员查看自己的评价汇总 - 应该能看到 200
r = requests.get(f"{BASE}/orders/collector/3/ratings", headers=cH)
print(f"[12] 回收员查看自己评分: {r.status_code} -> 平均分 {r.json()['average_score']}")
assert r.status_code == 200, "查看评分汇总应该对所有登录用户开放"

# 测试9: 居民查看回收员评分 - 应该能看到 200
r = requests.get(f"{BASE}/orders/collector/3/ratings", headers=r1H)
print(f"[13] 居民查看回收员评分: {r.status_code} -> 平均分 {r.json()['average_score']}")
assert r.status_code == 200

print("\n" + "=" * 60)
print("✅ 所有 13 项测试全部通过！")
print("=" * 60)
