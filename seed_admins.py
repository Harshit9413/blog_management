# from database import sessionlocal
# from models import User
# import auth  # your existing auth module

# db = sessionlocal()

# admins = [
#     {"email": "superadmin@yourapp.com",  "password": "SuperPass123", "role": "superadmin"},
#     {"email": "clientadmin@yourapp.com", "password": "ClientPass123", "role": "clientadmin"},
# ]

# for a in admins:
#     existing = db.query(User).filter(User.email == a["email"]).first()
#     if not existing:
#         user = User(
#             email=a["email"],
#             password=auth.hash_password(a["password"]),
#             role=a["role"]
#         )
#         db.add(user)
#         print(f"Created: {a['email']}")
#     else:
#         print(f"Already exists: {a['email']}")

# db.commit()
# db.close()