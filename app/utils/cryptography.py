from pwdlib import PasswordHash

def hash_password(password: str) -> str:
    return PasswordHash.recommended().hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return PasswordHash.recommended().verify(password, hashed_password)
