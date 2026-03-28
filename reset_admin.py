# # reset_admin.py
# from database import sessionlocal, engine
# from models import Base, User
# import auth

# # ─── CREATE TABLES IF NOT EXIST ─────────────────────
# Base.metadata.create_all(bind=engine)
# db = sessionlocal()

# # ─── SUPERADMIN ─────────────────────────────────────
# sa_email = "superadmin@gmail.com"
# sa_password = "Admin@12345"

# user = db.query(User).filter(User.email == sa_email).first()
# if not user:
#     user = User(
#         email=sa_email.strip().lower(),
#         password=auth.hash_password(sa_password),
#         role="superadmin"
#     )
#     db.add(user)
#     print(f"✅ Superadmin CREATED: {sa_email}")
# else:
#     user.password = auth.hash_password(sa_password)
#     user.role = "superadmin"
#     print(f"✅ Superadmin UPDATED: {sa_email}")

# # ─── CLIENTADMIN ────────────────────────────────────
# ca_email = "clientadmin@gmail.com"
# ca_password = "Client@123"

# user2 = db.query(User).filter(User.email == ca_email).first()
# if not user2:
#     user2 = User(
#         email=ca_email.strip().lower(),
#         password=auth.hash_password(ca_password),
#         role="clientadmin"
#     )
#     db.add(user2)
#     print(f"✅ Client Admin CREATED: {ca_email}")
# else:
#     user2.password = auth.hash_password(ca_password)
#     user2.role = "clientadmin"
#     print(f"✅ Client Admin UPDATED: {ca_email}")

# # ─── COMMIT CHANGES ────────────────────────────────
# db.commit()

# # ─── VERIFY HASHES ─────────────────────────────────
# ok1 = auth.verify_password(sa_password, user.password)
# ok2 = auth.verify_password(ca_password, user2.password)
# print(f"\nSuperadmin verify:    {'✅ PASS' if ok1 else '❌ FAIL'}")
# print(f"Client Admin verify:  {'✅ PASS' if ok2 else '❌ FAIL'}")

# db.close()