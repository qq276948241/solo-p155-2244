import requests
import json
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"

tomorrow = (date.today() + timedelta(days=1)).isoformat()


def print_response(label, response):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"状态码: {response.status_code}")
    if response.status_code != 204:
        try:
            data = response.json()
            print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return data
        except:
            print(f"响应文本: {response.text}")
    return None


def test_full_flow():
    headers = {"Content-Type": "application/json"}

    print("\n" + "="*60)
    print("社区废品回收预约系统 - API 完整流程测试")
    print("="*60)

    print("\n[1] 测试健康检查")
    r = requests.get(f"{BASE_URL}/health")
    print_response("健康检查", r)

    print("\n[2] 测试获取品类列表（无需登录）")
    r = requests.get(f"{BASE_URL}/categories")
    categories = print_response("获取品类列表", r)
    if categories:
        cat_map = {c["code"]: c["id"] for c in categories}
        print(f"\n品类映射: {cat_map}")

    print("\n[3] 测试居民登录")
    resident_login = {
        "phone": "13800000001",
        "password": "123456"
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=resident_login, headers=headers)
    resident_data = print_response("居民登录", r)
    resident_token = resident_data["access_token"] if resident_data else None
    resident_headers = {**headers, "Authorization": f"Bearer {resident_token}"} if resident_token else headers

    print("\n[4] 测试获取当前用户信息")
    r = requests.get(f"{BASE_URL}/users/me", headers=resident_headers)
    print_response("获取用户信息", r)

    print("\n[5] 测试添加收货地址")
    address_data = {
        "province": "广东省",
        "city": "深圳市",
        "district": "南山区",
        "detail": "科技园路1号 1栋101室",
        "contact_name": "张居民",
        "contact_phone": "13800000001",
        "is_default": True
    }
    r = requests.post(f"{BASE_URL}/users/addresses", json=address_data, headers=resident_headers)
    address = print_response("添加地址", r)
    address_id = address["id"] if address else None

    print("\n[6] 测试获取地址列表")
    r = requests.get(f"{BASE_URL}/users/addresses", headers=resident_headers)
    print_response("获取地址列表", r)

    print("\n[7] 测试定价计算接口")
    pricing_data = {
        "items": [
            {"category_code": "paper", "estimated_weight": 5.5},
            {"category_code": "plastic", "estimated_weight": 2.0},
            {"category_code": "metal", "estimated_weight": 1.5}
        ]
    }
    r = requests.post(f"{BASE_URL}/pricing/calculate", json=pricing_data, headers=resident_headers)
    pricing_result = print_response("定价计算", r)

    print("\n[8] 测试创建预约订单")
    order_data = {
        "scheduled_date": tomorrow,
        "scheduled_time_slot": "morning",
        "address_id": address_id,
        "remark": "请早上9点后上门",
        "items": [
            {"category_id": cat_map["paper"], "estimated_weight": 5.5},
            {"category_id": cat_map["plastic"], "estimated_weight": 2.0},
            {"category_id": cat_map["metal"], "estimated_weight": 1.5}
        ]
    }
    r = requests.post(f"{BASE_URL}/orders", json=order_data, headers=resident_headers)
    order = print_response("创建订单", r)
    order_id = order["id"] if order else None

    print("\n[9] 测试获取我的订单列表")
    r = requests.get(f"{BASE_URL}/orders", headers=resident_headers)
    print_response("获取订单列表", r)

    print("\n[10] 测试获取订单详情")
    if order_id:
        r = requests.get(f"{BASE_URL}/orders/{order_id}", headers=resident_headers)
        print_response("获取订单详情", r)

    print("\n[11] 测试修改预约时间")
    if order_id:
        reschedule_data = {
            "scheduled_date": tomorrow,
            "scheduled_time_slot": "afternoon"
        }
        r = requests.put(f"{BASE_URL}/orders/{order_id}/reschedule", json=reschedule_data, headers=resident_headers)
        print_response("修改预约时间", r)

    print("\n[12] 测试回收员登录")
    collector_login = {
        "phone": "13900000001",
        "password": "123456"
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=collector_login, headers=headers)
    collector_data = print_response("回收员登录", r)
    collector_token = collector_data["access_token"] if collector_data else None
    collector_headers = {**headers, "Authorization": f"Bearer {collector_token}"} if collector_token else headers

    print("\n[13] 测试回收员查看今日订单")
    r = requests.get(f"{BASE_URL}/collector/orders/today", headers=collector_headers)
    print_response("查看今日订单", r)

    print("\n[14] 测试回收员接单")
    if order_id:
        r = requests.put(f"{BASE_URL}/collector/orders/{order_id}/accept", headers=collector_headers)
        print_response("回收员接单", r)

    print("\n[15] 测试回收员开始上门")
    if order_id:
        r = requests.put(f"{BASE_URL}/collector/orders/{order_id}/start", headers=collector_headers)
        print_response("开始上门", r)

    print("\n[16] 测试回收员查看今日路线")
    r = requests.get(f"{BASE_URL}/collector/route/today", headers=collector_headers)
    print_response("查看今日路线", r)

    print("\n[17] 测试回收员完成订单")
    if order_id:
        complete_data = {
            "actual_weight": 9.2,
            "total_amount": 12.7
        }
        r = requests.put(f"{BASE_URL}/collector/orders/{order_id}/complete", json=complete_data, headers=collector_headers)
        print_response("完成订单", r)

    print("\n[18] 测试居民取消订单（已完成的订单不能取消，创建新订单测试）")
    order_data2 = {
        "scheduled_date": tomorrow,
        "scheduled_time_slot": "all_day",
        "address_id": address_id,
        "remark": "测试取消订单",
        "items": [
            {"category_id": cat_map["textile"], "estimated_weight": 3.0}
        ]
    }
    r = requests.post(f"{BASE_URL}/orders", json=order_data2, headers=resident_headers)
    order2 = print_response("创建订单2", r)
    order_id2 = order2["id"] if order2 else None

    if order_id2:
        r = requests.put(f"{BASE_URL}/orders/{order_id2}/cancel", headers=resident_headers)
        print_response("取消订单", r)

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)


if __name__ == "__main__":
    test_full_flow()
