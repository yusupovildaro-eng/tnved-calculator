import json, hmac, hashlib, time, base64, os, datetime
import kv as _kv

USERS_FILE   = os.path.join(os.path.dirname(__file__), 'users.json')
SECRET       = os.environ.get('AUTH_SECRET', 'tnved-dev-secret-change-me')
COOKIE       = 'tnved_sess'
SESSION_SECS = 7 * 24 * 3600
_KV_KEY      = 'tnved:users'

# ── Хранилище ───────────────────────────────────────────────────────────────

def load_users():
    """Возвращает {username: {password, tokens, created_at, paid_at}}"""
    raw = None
    if _kv.AVAILABLE:
        try:
            raw = _kv.get(_KV_KEY)
            if raw:
                data = json.loads(raw)
            else:
                data = {}
        except Exception:
            data = {}
    else:
        try:
            with open(USERS_FILE, encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

    # Миграция старого формата (строка → словарь)
    migrated = False
    today = datetime.date.today().isoformat()
    for username, value in list(data.items()):
        if isinstance(value, str):
            data[username] = {
                'password': value,
                'tokens': None,
                'created_at': today,
                'paid_at': None,
            }
            migrated = True

    if migrated:
        save_users(data)

    return data

def save_users(users):
    if _kv.AVAILABLE:
        _kv.set(_KV_KEY, json.dumps(users, ensure_ascii=False))
    else:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

# ── Пароли ───────────────────────────────────────────────────────────────────

def hash_password(password):
    salt = os.urandom(16)
    key  = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"pbkdf2:{salt.hex()}:{key.hex()}"

def check_password(user_data, password):
    stored = user_data['password'] if isinstance(user_data, dict) else user_data
    try:
        _, salt_hex, key_hex = stored.split(':')
        salt = bytes.fromhex(salt_hex)
        key  = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

# ── Доступ и токены ──────────────────────────────────────────────────────────

def can_access(username):
    """Возвращает (разрешено: bool, причина: str)"""
    users = load_users()
    if username not in users:
        return False, 'not_found'
    data  = users[username]

    # Проверка срока подписки
    paid_at = data.get('paid_at')
    if paid_at:
        expires = datetime.date.fromisoformat(paid_at) + datetime.timedelta(days=30)
        if datetime.date.today() > expires:
            return False, 'expired'

    # Проверка токенов
    tokens = data.get('tokens')
    if tokens is not None and tokens <= 0:
        return False, 'no_tokens'

    return True, 'ok'

def use_token(username):
    """Уменьшает счётчик токенов на 1. Возвращает True если разрешено."""
    users = load_users()
    if username not in users:
        return False
    tokens = users[username].get('tokens')
    if tokens is None:
        return True   # Безлимит
    if tokens <= 0:
        return False
    users[username]['tokens'] = tokens - 1
    save_users(users)
    return True

def check_and_clear_new(username):
    """Возвращает True если пользователь новый (первый вход), сбрасывает флаг."""
    users = load_users()
    if username not in users:
        return False
    if users[username].get('is_new'):
        users[username]['is_new'] = False
        save_users(users)
        return True
    return False

def tokens_badge_html(username):
    """Возвращает HTML-бейдж с остатком токенов для хедера."""
    users = load_users()
    if username not in users:
        return ''
    tokens = users[username].get('tokens')
    if tokens is None:
        return '<span class="tok-badge">∞ запросов</span>'
    cls = 'tok-badge tok-low' if tokens <= 5 else 'tok-badge'
    if tokens % 10 == 1 and tokens % 100 != 11:
        word = 'запрос'
    elif tokens % 10 in (2, 3, 4) and tokens % 100 not in (12, 13, 14):
        word = 'запроса'
    else:
        word = 'запросов'
    return f'<span class="{cls}">🔢 {tokens} {word}</span>'

# ── Метаданные для админки ───────────────────────────────────────────────────

def get_users_with_meta():
    users = load_users()
    today = datetime.date.today()
    result = []
    for username, data in users.items():
        paid_at    = data.get('paid_at')
        expires_at = None
        days_left  = None
        if paid_at:
            expires    = datetime.date.fromisoformat(paid_at) + datetime.timedelta(days=30)
            expires_at = expires.isoformat()
            days_left  = (expires - today).days
        result.append({
            'username':   username,
            'tokens':     data.get('tokens'),
            'created_at': data.get('created_at'),
            'paid_at':    paid_at,
            'expires_at': expires_at,
            'days_left':  days_left,
            'first_name': data.get('first_name', ''),
            'last_name':  data.get('last_name', ''),
            'inn':        data.get('inn', ''),
            'phone':      data.get('phone', ''),
            'org':        data.get('org', ''),
        })
    result.sort(key=lambda x: x['username'])
    return result

# ── Сессии ───────────────────────────────────────────────────────────────────

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
