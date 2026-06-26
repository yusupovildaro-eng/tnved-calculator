import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, Response
import tariff as t

app = Flask(__name__)

@app.route('/')
@app.route('/tariff')
def index():
    html = t.PAGE.replace('COUNTRIES_JSON_PLACEHOLDER', t.country_items_json())
    return Response(html, mimetype='text/html; charset=utf-8')

@app.route('/api/lookup')
def api_lookup():
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
    q = request.args.get('q', '').strip()
    return jsonify(t.smart_search(q, limit=18))

@app.route('/api/docs')
def api_docs():
    code  = request.args.get('code', '').strip()
    rejim = request.args.get('rejim', 'import').strip()
    return jsonify(t.get_docs(code, rejim))

@app.route('/api/rates')
def api_rates():
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
    code     = request.args.get('code', '').strip()
    sending  = request.args.get('sending', '000')
    origin   = request.args.get('origin', '000')
    trade    = request.args.get('trade', '000')
    return jsonify(t.customs_uz_lookup(code, origin, sending, trade))
