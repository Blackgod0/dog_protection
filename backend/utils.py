import os
import json
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import bcrypt

load_dotenv()
FERNET_KEY = os.getenv('FERNET_KEY')
USERS_FILE = 'users.json'
PROFILES_FILE = 'encrypted_profiles.json'

def ensure_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, 'wb') as f:
            f.write(b'')

def hash_password(password: str) -> bytes:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def check_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def load_users(encrypted=False):
    ensure_files()
    with open(USERS_FILE, 'r') as f:
        data = json.load(f)
    return data

def save_user(username: str, password: str):
    users = load_users()
    hashed = hash_password(password).decode('utf-8')
    users[username] = {'password': hashed}
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def encrypt_profiles(plaintext_bytes: bytes) -> bytes:
    if not FERNET_KEY:
        raise RuntimeError('FERNET_KEY not set')
    f = Fernet(FERNET_KEY.encode())
    return f.encrypt(plaintext_bytes)

def decrypt_profiles(ciphertext: bytes) -> bytes:
    if not FERNET_KEY:
        raise RuntimeError('FERNET_KEY not set')
    f = Fernet(FERNET_KEY.encode())
    if not ciphertext:
        return b''
    return f.decrypt(ciphertext)

def save_encrypted_profiles(json_obj):
    ciphertext = encrypt_profiles(json.dumps(json_obj).encode('utf-8'))
    with open(PROFILES_FILE, 'wb') as f:
        f.write(ciphertext)

def load_encrypted_profiles():
    ensure_files()
    with open(PROFILES_FILE, 'rb') as f:
        data = f.read()
    if not data:
        return {}
    plaintext = decrypt_profiles(data)
    return json.loads(plaintext.decode('utf-8'))
