from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import Category, User
from app.utils.security import hash_password

Base.metadata.create_all(bind=engine)

categories = [
    {"name": "纸板", "code": "paper", "unit_price": 1.2, "description": "纸箱、报纸、书本等纸类废品"},
    {"name": "塑料", "code": "plastic", "unit_price": 0.8, "description": "饮料瓶、塑料袋等塑料废品"},
    {"name": "金属", "code": "metal", "unit_price": 3.0, "description": "易拉罐、铁丝等金属废品"},
    {"name": "织物", "code": "textile", "unit_price": 0.5, "description": "旧衣物、床单等织物废品"},
]

users = [
    {"phone": "13800000001", "name": "张居民", "password": "123456", "role": "resident"},
    {"phone": "13800000002", "name": "李居民", "password": "123456", "role": "resident"},
    {"phone": "13900000001", "name": "王回收", "password": "123456", "role": "collector"},
    {"phone": "13900000002", "name": "赵回收", "password": "123456", "role": "collector"},
    {"phone": "13700000001", "name": "管理员", "password": "123456", "role": "admin"},
]


def init_data():
    db = SessionLocal()
    try:
        for cat_data in categories:
            existing = db.query(Category).filter(Category.code == cat_data["code"]).first()
            if not existing:
                cat = Category(**cat_data)
                db.add(cat)
                print(f"创建品类: {cat_data['name']}")
            else:
                print(f"品类已存在: {cat_data['name']}")

        for user_data in users:
            existing = db.query(User).filter(User.phone == user_data["phone"]).first()
            if not existing:
                user = User(
                    phone=user_data["phone"],
                    name=user_data["name"],
                    password_hash=hash_password(user_data["password"]),
                    role=user_data["role"]
                )
                db.add(user)
                print(f"创建用户: {user_data['name']} ({user_data['role']})")
            else:
                print(f"用户已存在: {user_data['name']}")

        db.commit()
        print("\n数据初始化完成！")
        print("\n测试账号:")
        print("  居民: 13800000001 / 123456")
        print("  回收员: 13900000001 / 123456")
        print("  管理员: 13700000001 / 123456")
    except Exception as e:
        print(f"初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_data()
