import bcrypt, getpass
pw = getpass.getpass("Password: ").encode("utf-8")
h = bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")
print("BCRYPT_HASH=", h)
