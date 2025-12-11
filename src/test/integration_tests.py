import hashlib

# Mật khẩu cần mã hóa
password = "12345"

# Mã hóa mật khẩu với SHA-256
hashed_password = hashlib.sha256(password.encode()).hexdigest()

print("Mã hash của mật khẩu:", hashed_password)
