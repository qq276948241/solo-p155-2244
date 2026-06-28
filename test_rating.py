import requests
import json
from datetime import date, timedelta

BASE = "http://localhost:8000"
tomorrow = (date.today() + timedelta(days=1)).isoformat()
H = {"Content-Type": "application/json"}

r = requests.post(f"{BASE}/auth/login", json={"phone": "13800000001", "password": "123456"}, headers=H)
token = r.json()["access_token"]
rH = {**H, "Authorization": f"Bearer {token}"}

r = requests.post(
    f"{BASE}/users/addresses",
    json={
        "province": "广东省", "city": "深圳市", "district": "南山区",
        "detail": "科技园路1号", "contact_name": "张居民",
        "contact_phone": "13800000001", "is_default": True
    },
    headers=rH
)
addr_id = r.json()["id"]

r = requests.post(
    f"{BASE}/orders",
    json={
        "scheduled_date": tomorrow, "scheduled_time_slot": "morning",
        "address_id": addr_id,
        "items": [{"category_id": 1, "estimated_weight": 5}]
    },
    headers=rH
)
order_id = r.json()["id"]
print(f"[1] 创建订单 id={order_id}")

r = requests.post(f"{BASE}/auth/login", json={"phone": "13900000001", "password": "123456"}, headers=H)
ct = r.json()["access_token"]
cH = {**H, "Authorization": f"Bearer {ct}"}

r = requests.put(f"{BASE}/collector/orders/{order_id}/accept", headers=cH)
print(f"[2] 接单: {r.status_code}")
r = requests.put(f"{BASE}/collector/orders/{order_id}/start", headers=cH)
print(f"[3] 开始: {r.status_code}")
r = requests.put(f"{BASE}/collector/orders/{order_id}/complete", json={"actual_weight": 5, "total_amount": 6}, headers=cH)
print(f"[4] 完成: {r.status_code}")

r = requests.post(f"{BASE}/orders/{order_id}/rate", json={"score": 5, "comment": "回收员非常准时，态度很好！"}, headers=rH)
print(f"[5] 提交评价: {r.status_code}")
print(f"    响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

r = requests.post(f"{BASE}/orders/{order_id}/rate", json={"score": 3, "comment": "想改差评"}, headers=rH)
print(f"[6] 重复评价: {r.status_code} -> {r.json()['detail']}")

r = requests.get(f"{BASE}/orders/{order_id}/rate", headers=rH)
print(f"[7] 查看评价: {r.status_code}")
print(f"    响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

r = requests.get(f"{BASE}/orders/collector/3/ratings", headers=rH)
print(f"[8] 回收员评价汇总: {r.status_code}")
data = r.json()
print(f"    回收员: {data['collector_name']}, 平均分: {data['average_score']}, 评价数: {data['total_count']}")

r2 = requests.post(
    f"{BASE}/orders",
    json={
        "scheduled_date": tomorrow, "scheduled_time_slot": "afternoon",
        "address_id": addr_id,
        "items": [{"category_id": 2, "estimated_weight": 3}]
    },
    headers=rH
)
pending_id = r2.json()["id"]
r = requests.post(f"{BASE}/orders/{pending_id}/rate", json={"score": 4, "comment": "试试未完成评价"}, headers=rH)
print(f"[9] 评价未完成订单: {r.status_code} -> {r.json()['detail']}")

r = requests.post(f"{BASE}/orders/{order_id}/rate", json={"score": 6, "comment": "超范围"}, headers=rH)
print(f"[10] 评分越界(6星): {r.status_code}")

r = requests.post(f"{BASE}/orders/{order_id}/rate", json={"score": 0, "comment": "超范围"}, headers=rH)
print(f"[11] 评分越界(0星): {r.status_code}")

r = requests.post(f"{BASE}/orders/{order_id}/rate", json={"score": 4, "comment": "a" * 201}, headers=rH)
print(f"[12] 评语超200字: {r.status_code}")

print("\n评价功能测试完成！")
