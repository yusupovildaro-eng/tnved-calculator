import os, json, urllib.request, urllib.error

_URL   = os.environ.get('KV_REST_API_URL', '').rstrip('/')
_TOKEN = os.environ.get('KV_REST_API_TOKEN', '')
AVAILABLE = bool(_URL and _TOKEN)

def _cmd(*args):
    req = urllib.request.Request(
        _URL,
        data=json.dumps(list(args)).encode(),
        headers={
            'Authorization': f'Bearer {_TOKEN}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read()).get('result')

def get(key):
    return _cmd('GET', key)

def set(key, value):
    _cmd('SET', key, value)
