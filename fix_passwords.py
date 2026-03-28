# from database import sessionlocal
# from models import User
# import auth

# db = sessionlocal()

# users = db.query(User).all()

# for u in users:
#     if not u.password.startswith("$argon2"):
#         print(f"Fixing password for {u.email}")
#         u.password = auth.hash_password(u.password)

# db.commit()
# db.close()

# # print("✅ All passwords fixed")