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

@app.route('/api/tree')
def api_tree():
    prefix = request.args.get('prefix', '').strip()
    return jsonify(t.get_tree(prefix))

@app.route('/api/identify', methods=['POST'])
def api_identify():
    import json, re, os, urllib.request, urllib.error
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'GEMINI_API_KEY не настроен. Добавьте ключ из aistudio.google.com в переменные среды Vercel.'}), 503
    body = request.get_json(silent=True) or {}
    img_b64 = body.get('image')
    media_type = body.get('media_type', 'image/jpeg')
    if not img_b64:
        return jsonify({'error': 'Изображение не передано'}), 400
    if media_type not in ('image/jpeg', 'image/png', 'image/gif', 'image/webp'):
        media_type = 'image/jpeg'
    prompt = (
        'Вы — эксперт по ТН ВЭД (Товарная номенклатура внешнеэкономической деятельности) Узбекистана. '
        'Определите 3-5 наиболее подходящих 10-значных кодов ТН ВЭД для товара на изображении. '
        'Ответьте ТОЛЬКО JSON массивом, без лишнего текста:\n'
        '[{"code":"ХХХХХХХХХХ","name":"краткое название","reason":"почему подходит этот код"}]\n'
        'Коды должны быть ровно 10 цифр. Если последние цифры неизвестны, используйте 00.'
    )
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
    payload = json.dumps({
        'contents': [{'parts': [
            {'inline_data': {'mime_type': media_type, 'data': img_b64}},
            {'text': prompt}
        ]}]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'x-goog-api-key': api_key
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data['candidates'][0]['content']['parts'][0]['text'].strip()
        m = re.search(r'\[.*?\]', text, re.DOTALL)
        if not m:
            return jsonify({'error': 'Не удалось распознать ответ ИИ', 'raw': text[:400]}), 500
        codes_raw = json.loads(m.group())
        conn = t.get_db()
        result = []
        for item in codes_raw[:5]:
            code = re.sub(r'\D', '', str(item.get('code', ''))).ljust(10, '0')[:10]
            row = conn.execute(
                'SELECT code, name_ru, poshlina_pct, nds_pct FROM tnved WHERE code=?', (code,)
            ).fetchone()
            if not row and len(code) >= 4:
                row = conn.execute(
                    'SELECT code, name_ru, poshlina_pct, nds_pct FROM tnved WHERE code LIKE ? ORDER BY code LIMIT 1',
                    (code[:4] + '%',)
                ).fetchone()
            result.append({
                'code': row[0] if row else code,
                'name': row[1] if row else item.get('name', ''),
                'poshlina_pct': row[2] if row else None,
                'nds_pct': row[3] if row else None,
                'reason': item.get('reason', ''),
                'found_in_db': bool(row)
            })
        conn.close()
        return jsonify({'codes': result})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')[:400]
        return jsonify({'error': f'Gemini API {e.code}: {err_body}'}), 502
    except json.JSONDecodeError:
        return jsonify({'error': 'Ошибка парсинга ответа ИИ'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
