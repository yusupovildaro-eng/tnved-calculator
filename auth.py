import json, hmac, hashlib, time, base64, os

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
SECRET     = os.environ.get('AUTH_SECRET', 'tnved-dev-secret-change-me')
COOKIE     = 'tnved_sess'
SESSION_SECS = 7 * 24 * 3600  # 7 дней

def load_users():
    try:
        with open(USERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def check_password(stored_hash, password):
    try:
        _, salt_hex, key_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        key  = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def make_session(username):
    ts      = str(int(time.time()))
    payload = username + ':' + ts
    sig     = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token   = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
    return token + '.' + sig

def verify_session(cookie_val):
    if not cookie_val:
        return None
    try:
        token, sig = cookie_val.rsplit('.', 1)
        padding    = '=' * (-len(token) % 4)
        payload    = base64.urlsafe_b64decode(token + padding).decode()
        expected   = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        username, ts = payload.rsplit(':', 1)
        if time.time() - int(ts) > SESSION_SECS:
            return None
        return username
    except Exception:
        return None

def parse_cookie(cookie_header):
    for part in (cookie_header or '').split(';'):
        part = part.strip()
        if part.startswith(COOKIE + '='):
            return part[len(COOKIE) + 1:]
    return None

def cookie_header(token, clear=False):
    if clear:
        return f'{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
    return f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_SECS}'
