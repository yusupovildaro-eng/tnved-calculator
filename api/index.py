import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, Response, redirect, make_response
import tariff as t
import auth as _auth

app = Flask(__name__)

def _current_user():
    return _auth.verify_session(request.cookies.get(_auth.COOKIE))

@app.route('/login')
def login_page():
    return Response(t.LOGIN_PAGE, mimetype='text/html; charset=utf-8')

@app.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    users    = _auth.load_users()
    if username in users and _auth.check_password(users[username], password):
        token = _auth.make_session(username)
        resp  = make_response(jsonify({'ok': True}))
        resp.set_cookie(_auth.COOKIE, token, max_age=_auth.SESSION_SECS,
                        httponly=True, samesite='Lax')
        return resp
    return jsonify({'ok': False, 'error': 'Неверный логин или пароль'}), 401

@app.route('/logout')
def logout():
    resp = make_response(redirect('/login'))
    resp.set_cookie(_auth.COOKIE, '', max_age=0, httponly=True, samesite='Lax')
    return resp

@app.route('/')
@app.route('/tariff')
def index():
    user = _current_user()
    if not user:
        return redirect('/login')
    html = t.PAGE.replace('COUNTRIES_JSON_PLACEHOLDER', t.country_items_json())
    html = html.replace('CURRENT_USER_PLACEHOLDER', user)
    return Response(html, mimetype='text/html; charset=utf-8')

def _require_auth():
    if not _current_user():
        return jsonify({'error': 'unauthorized'}), 401

@app.route('/api/lookup')
def api_lookup():
    if err := _require_auth(): return err
    code = request.args.get('code', '').strip()
    conn = t.get_db()
    row = conn.execute('SELECT * FROM tnved WHERE code=?', (code,)).fetchone()
    if not row:
        row = conn.execute(
            'SELECT * FROM tnved WHERE code LIKE ? ORDER BY code LIMIT 1',
            (code + '%',)
        ).fetchone()
    conn.close()
    return jsonify(dict(row) if row else {'error': 'not found'})

@app.route('/api/search')
def api_search():
    if err := _require_auth(): return err
    q = request.args.get('q', '').strip()
    return jsonify(t.smart_search(q, limit=18))

@app.route('/api/docs')
def api_docs():
    if err := _require_auth(): return err
    code  = request.args.get('code', '').strip()
    rejim = request.args.get('rejim', 'import').strip()
    return jsonify(t.get_docs(code, rejim))

@app.route('/api/rates')
def api_rates():
    if err := _require_auth(): return err
    import ssl, json, urllib.request
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            'https://cbu.uz/ru/arkhiv-kursov-valyut/json/',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        data = json.loads(urllib.request.urlopen(req, context=ctx, timeout=8).read())
        rates = {}
        date_str = ''
        for item in data:
            ccy = item.get('Ccy', '')
            if ccy in ('USD', 'EUR', 'RUB', 'CNY', 'GBP', 'KZT'):
                rates[ccy] = {'rate': float(item['Rate']), 'diff': item.get('Diff', '0')}
                date_str = item.get('Date', '')
        return jsonify({'ok': True, 'rates': rates, 'date': date_str})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/customs_check')
def api_customs_check():
    if err := _require_auth(): return err
    code     = request.args.get('code', '').strip()
    sending  = request.args.get('sending', '000')
    origin   = request.args.get('origin', '000')
    trade    = request.args.get('trade', '000')
    return jsonify(t.customs_uz_lookup(code, origin, sending, trade))

@app.route('/api/tree')
def api_tree():
    if err := _require_auth(): return err
    prefix = request.args.get('prefix', '').strip()
    return jsonify(t.get_tree(prefix))

