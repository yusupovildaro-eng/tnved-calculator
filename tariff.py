#!/usr/bin/env python3
"""
Тарифный калькулятор — расширенная форма с выбором страны и сравнением с customs.uz
python3 tariff.py        → http://localhost:5002
python3 tariff.py 5003   → другой порт
"""
import sys, json, sqlite3, os, re, ssl, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, urlencode
import urllib.request
import auth as _auth

DB_PATH = os.path.join(os.path.dirname(__file__), "tnved.db")

# ── Словарь синонимов: разговорное слово → технические термины в БД ───────────
# Используется для расширения поискового запроса
SYNONYMS = {
    # Связь / электроника
    'рация':         ['радиовещани', 'включающ', 'приемную'],
    'радиостанция':  ['радиовещани', 'радиостанц'],
    'walkie':        ['радиовещани', 'включающ'],
    'телефон':       ['телефон', 'смартфон', 'аппарат'],
    'смартфон':      ['смартфон', 'телефон'],
    'ноутбук':       ['вычислительн', 'портатив', 'ноутбук'],
    'компьютер':     ['вычислительн', 'процессор', 'компьютер'],
    'планшет':       ['планшет', 'вычислительн', 'портатив'],
    'телевизор':     ['телевизор', 'монитор', 'видеомонитор'],
    'монитор':       ['монитор', 'видеомонитор', 'дисплей'],
    'принтер':       ['принтер', 'печатающ'],
    'камера':        ['камера', 'фотоаппарат', 'видеокамер'],
    'фотоаппарат':   ['фотоаппарат', 'камера', 'фотографич'],
    'наушники':      ['наушник', 'головных телефон'],
    'колонки':       ['акустическ', 'громкоговорит', 'звуковоспроизвод'],
    'микрофон':      ['микрофон'],
    'роутер':        ['маршрутизатор', 'роутер'],
    'аккумулятор':   ['аккумулятор', 'батарей', 'аккумуляторн'],
    'батарейка':     ['батарея', 'элемент', 'первичн'],
    'трансформатор': ['трансформатор'],
    'генератор':     ['генератор', 'электрогенератор'],
    'панель солнечная': ['солнечн', 'фотоэлектр'],
    'солнечная панель': ['солнечн', 'фотоэлектр'],
    'лампа':         ['лампа', 'осветительн', 'лампочка'],
    'светодиод':     ['светодиодн', 'led'],
    'дрон':          ['беспилотн', 'дрон', 'бпла'],
    'квадрокоптер':  ['беспилотн', 'дрон'],
    # Бытовая техника
    'холодильник':   ['холодильник', 'морозильник', 'холодильного'],
    'морозильник':   ['морозильник', 'морозильного'],
    'кондиционер':   ['кондиционер', 'кондиционирован', 'охлаждени'],
    'стиральная машина': ['стиральн', 'машин'],
    'стиралка':      ['стиральн'],
    'пылесос':       ['пылесос'],
    'микроволновка': ['микроволновая', 'свч'],
    'плита':         ['плита', 'кухонная', 'варочная', 'плит'],
    'духовка':       ['духовка', 'печь', 'духовой'],
    'посудомойка':   ['посудомоечн'],
    'утюг':          ['утюг'],
    'фен':           ['фен', 'сушилка для волос'],
    'кофеварка':     ['кофеварк', 'кофемашин'],
    'чайник':        ['чайник', 'кипятильник'],
    'вентилятор':    ['вентилятор'],
    # Автомобили / транспорт
    'автомобиль':    ['автомобил', 'легковой', 'транспортн'],
    'машина':        ['автомобил', 'легковой'],
    'легковой автомобиль': ['легковой', 'автомобил', 'пассажирск'],
    'грузовик':      ['грузов', 'грузовой автомобил'],
    'автобус':       ['автобус'],
    'мотоцикл':      ['мотоцикл'],
    'велосипед':     ['велосипед'],
    'самокат':       ['самокат', 'электросамокат'],
    'скутер':        ['скутер', 'мопед'],
    'трактор':       ['трактор'],
    'экскаватор':    ['экскаватор', 'землеройн'],
    'грузоподъемник':['погрузчик', 'вилочный', 'подъемн'],
    'шины':          ['шина', 'покрышк', 'пневматическ'],
    'запчасти':      ['части', 'запасн', 'детали'],
    # Продукты питания
    'мясо':          ['мясо', 'мясной', 'туши'],
    'говядина':      ['говядин', 'крупного рогатого'],
    'свинина':       ['свинин', 'свиная'],
    'курица':        ['домашней птиц', 'курица', 'птиц'],
    'рыба':          ['рыба', 'рыбн', 'рыбного'],
    'молоко':        ['молоко', 'молочн'],
    'масло':         ['масло', 'растительн', 'сливочн'],
    'сыр':           ['сыр', 'творог'],
    'сахар':         ['сахар'],
    'мука':          ['мука', 'муки'],
    'рис':           ['рис'],
    'пшеница':       ['пшениц', 'зерно'],
    'фрукты':        ['фрукт', 'плод', 'цитрусовых'],
    'яблоки':        ['яблок', 'яблони'],
    'бананы':        ['банан'],
    'виноград':      ['виноград'],
    'овощи':         ['овощ', 'огурц', 'помидор', 'морковь'],
    'чай':           ['чай'],
    'кофе':          ['кофе'],
    'шоколад':       ['шоколад', 'какао'],
    'вода':          ['воды', 'водой', 'минеральн'],
    'сок':           ['сок', 'соки'],
    # Алкоголь и табак
    'вино':          ['вин', 'виноградн'],
    'пиво':          ['пиво', 'пивной'],
    'водка':         ['водка', 'водки', 'этиловый'],
    'коньяк':        ['коньяк', 'бренди'],
    'виски':         ['виски'],
    'сигареты':      ['сигарет', 'табак'],
    'табак':         ['табак'],
    # Стройматериалы
    'цемент':        ['цемент'],
    'кирпич':        ['кирпич'],
    'плитка':        ['плитк', 'керамическ', 'кафель'],
    'стекло':        ['стекло', 'стекольн'],
    'арматура':      ['арматур', 'стальн', 'прутк'],
    'труба':         ['труб', 'трубопровод'],
    'профиль':       ['профиль', 'профил'],
    'сэндвич панель':['сэндвич', 'сэндвичн'],
    'гипсокартон':   ['гипсокартон', 'гипс'],
    'утеплитель':    ['утеплит', 'теплоизол', 'минеральная вата'],
    # Одежда
    'одежда':        ['одежд', 'одеяни'],
    'куртка':        ['куртк', 'пальто', 'ветровк'],
    'брюки':         ['брюки', 'штаны', 'слаксы'],
    'рубашка':       ['рубашк'],
    'платье':        ['платье'],
    'футболка':      ['фуфайк', 'футболк'],
    'носки':         ['носок', 'носки', 'чулочн'],
    'нижнее белье':  ['бельё', 'белье', 'нижн'],
    'пальто':        ['пальто'],
    'костюм':        ['костюм'],
    # Обувь
    'обувь':         ['обувь', 'обувного', 'ботинк'],
    'кроссовки':     ['кроссовк', 'спортивн обувь', 'кеды'],
    'сапоги':        ['сапог', 'ботинок'],
    'туфли':         ['туфли', 'туфель'],
    # Мебель
    'мебель':        ['мебель', 'мебельн'],
    'стул':          ['стул', 'кресло', 'сиден'],
    'диван':         ['диван', 'кушетк', 'сиден'],
    'кресло':        ['кресло', 'сиден'],
    'стол':          ['стол', 'столешниц'],
    'шкаф':          ['шкаф', 'гардероб', 'шкафчик'],
    'кровать':       ['кровать', 'постельн', 'матрас'],
    'матрас':        ['матрас', 'матрац'],
    # Промышленность
    'насос':         ['насос'],
    'компрессор':    ['компрессор'],
    'кабель':        ['кабель', 'провод', 'кабельн'],
    'провод':        ['провод', 'кабель', 'проводник'],
    'подшипник':     ['подшипник'],
    'клапан':        ['клапан', 'вентиль'],
    'кран':          ['кран', 'краны', 'запорн'],
    'двигатель':     ['двигател', 'мотор'],
    'станок':        ['станок'],
    'краска':        ['краска', 'лак', 'эмаль', 'покрыти'],
    'удобрение':     ['удобрен', 'нитрат', 'фосфат'],
    'пластик':       ['пластмасс', 'полимер', 'пластик'],
    'резина':        ['резина', 'каучук', 'резиновый'],
    'алюминий':      ['алюминий', 'алюминиев'],
    'медь':          ['медь', 'медн'],
    'нержавейка':    ['нержавеющ', 'коррозионн'],
    'нефть':         ['нефть', 'нефтяных'],
    'бензин':        ['бензин', 'автомобильного топлив'],
    'дизель':        ['дизельн', 'газойль'],
    'газ':           ['газ', 'сжиженн', 'природный'],
    # Медицина
    'лекарство':     ['лекарств', 'фармацевт', 'медицинск'],
    'таблетки':      ['таблетк', 'лекарств', 'фармацевт'],
    'маска':         ['маска', 'защитн маска', 'респиратор'],
    'перчатки':      ['перчатк', 'хирургическ'],
    # Прочее
    'часы':          ['часы', 'часовой'],
    'очки':          ['очки', 'линзы', 'оптическ'],
    'игрушки':       ['игрушк', 'игровой'],
    'книги':         ['книг', 'печатн', 'издани'],
    'косметика':     ['косметик', 'парфюм', 'туалетн'],
    'духи':          ['парфюм', 'духи', 'туалетная вода'],
    'шампунь':       ['шампунь', 'средств для волос'],
    'инструмент':    ['инструмент'],
    'дрель':         ['дрель', 'перфоратор'],
    'болт':          ['болт', 'гайка', 'крепёж', 'резьбовой'],
    'гвоздь':        ['гвоздь', 'гвоздей'],
    'замок':         ['замок', 'запор'],
    'цепь':          ['цепь', 'цепочка'],
    # Строительство / сантехника
    'ламинат':           ['паркетн', 'плиты древесн'],
    'паркет':            ['паркетн', 'паркет'],
    'обои':              ['обои', 'настенн'],
    'мрамор':            ['мрамор', 'травертин'],
    'гранит':            ['гранит', 'базальт'],
    'унитаз':            ['унитаз', 'биде', 'раковин'],
    'раковина':          ['раковин', 'умывальник'],
    'смеситель':         ['смеситель'],
    'посуда':            ['посуда', 'кухонная'],
    'керамика':          ['керамическ', 'фарфор'],
    'зеркало':           ['зеркало', 'зеркальн'],
    'окно':              ['оконн', 'стеклопакет'],
    'дверь':             ['дверн'],
    # Электроника (дополнения)
    'powerbank':         ['портатив', 'литиев'],
    'пауэрбанк':         ['портатив', 'литиев'],
    'power bank':        ['портатив', 'литиев'],
    'умные часы':        ['часы наручн'],
    'смарт часы':        ['часы наручн'],
    'навигатор':         ['навигац', 'радионавигац'],
    'gps':               ['навигац', 'спутников'],
    'швейная машина':    ['швейн', 'футляр'],
    'игровая приставка': ['видеоигр', 'игровой'],
    'игровая консоль':   ['видеоигр', 'игровой'],
    'playstation':       ['видеоигр', 'игровой'],
    'xbox':              ['видеоигр', 'игровой'],
    # Топливо и ресурсы
    'уголь':             ['каменн', 'антрацит'],
    'металлолом':        ['лом черных', 'отходы'],
    'лом металла':       ['лом черных', 'отходы'],
    # Драгоценные металлы и украшения
    'золото':            ['золото', 'гальванич'],
    'серебро':           ['серебр'],
    'платина':           ['платин'],
    'ювелирные изделия': ['ювелирн', 'драгоценн'],
    'украшения':         ['ювелирн', 'бижутер', 'драгоценн'],
    'монета':            ['монет'],
    'сталь':             ['стальн', 'прокат'],
    'цинк':              ['цинк'],
    # Овощи и фрукты (дополнения)
    'картофель':         ['картофель', 'свежий'],
    'картошка':          ['картофель', 'свежий'],
    'помидоры':          ['томат'],
    'томаты':            ['томат'],
    'перец':             ['перец', 'паприк'],
    'лук':               ['лук репчат'],
    'морковь':           ['морков'],
    'чеснок':            ['чеснок'],
    'арбуз':             ['арбуз'],
    'дыня':              ['дыня', 'бахчев'],
    # Животноводство и пчеловодство
    'яйца':              ['яйцо', 'яйца'],
    'яйцо':              ['яйцо', 'яйца'],
    'мёд':               ['натуральный', 'пчел'],
    'шерсть':            ['шерсть', 'шерстян'],
    # Сухофрукты и орехи
    'курага':            ['абрикос', 'сушен'],
    'чернослив':         ['слив', 'сушен'],
    'финики':            ['финик'],
    'изюм':              ['виноград', 'сушен'],
    'сухофрукты':        ['абрикос', 'виноград', 'чернослив', 'фрукты сушен'],
    'орехи':             ['орех', 'грецкий'],
    'грецкий орех':      ['грецкий', 'орех'],
    'фундук':            ['фундук', 'орех'],
    'миндаль':           ['миндаль'],
    'фисташки':          ['фисташк'],
    # Хлопок и текстиль
    'хлопок':            ['гребнечесани', 'хлопков'],
    'хлопковая ткань':   ['хлопчатобумажн'],
    'шелк':              ['шелк', 'шелков'],
    'лён':               ['льнян'],
    'лен':               ['льнян'],
    # Масла и химия
    'подсолнечное масло':['подсолнечн'],
    'кукурузное масло':  ['кукурузн'],
    'моторное масло':    ['моторн', 'смазочн'],
    'мыло':              ['мыло', 'моющ'],
    'стиральный порошок':['стиральн', 'моющ'],
    'моющее средство':   ['моющ'],
    'порошок':           ['порошок', 'стиральн', 'моющ'],
    'дезодорант':        ['дезодорант', 'антиперспирант'],
    # Медицина (расширение)
    'шприц':             ['шприц'],
    'медоборудование':   ['медицинск', 'хирургическ'],
    'медицинское оборудование': ['медицинск', 'хирургическ'],
    # Спорт и активный отдых
    'коньки':            ['коньк'],
    'тренажёр':          ['физкультур', 'гимнастич'],
    'тренажер':          ['физкультур', 'гимнастич'],
    'беговая дорожка':   ['физкультур', 'бегов'],
    'теннис':            ['теннис', 'ракетк'],
    'газонокосилка':     ['газонокос'],
    'оружие':            ['огнестрельн'],
    'охота':             ['охотнич', 'огнестрельн'],
    'рыбалка':           ['рыболовн', 'удочк'],
    'спортинвентарь':    ['спортивн', 'инвентарь'],
    # Сумки и аксессуары
    'сумка':             ['сумк', 'портфель'],
    'рюкзак':            ['рюкзак'],
    'чемодан':           ['чемодан'],
    'ковёр':             ['ковер', 'ковровый'],
    'ковер':             ['ковер', 'ковровый'],
    'подушка':           ['подушк'],
    'одеяло':            ['одеяло'],
    # Сельское хозяйство
    'семена':            ['семена', 'посевн'],
    'саженцы':           ['саженц', 'черенки'],
    'цветы':             ['срезанн', 'цветы', 'цветок'],
    'пестициды':         ['пестицид', 'гербицид', 'фунгицид'],
}

def expand_query(q: str):
    """Расширяет запрос синонимами. Возвращает список терминов для поиска."""
    q_low = q.lower().strip()
    # Берём только самый длинный совпавший ключ (приоритет многословных фраз)
    matched_key = None
    matched_len = 0
    for key in SYNONYMS:
        if key in q_low and len(key) > matched_len:
            matched_key = key
            matched_len = len(key)
    if matched_key:
        expanded = list(SYNONYMS[matched_key])
        for word in q_low.split():
            if len(word) > 2:
                expanded.append(word)
        return list(dict.fromkeys(expanded))  # убираем дубликаты
    # Иначе — используем слова из запроса (фильтруем короткие)
    words = [w for w in q_low.split() if len(w) > 2]
    return words if words else [q_low]

def smart_search(q: str, limit: int = 18):
    """Умный поиск по ТН ВЭД с расширением синонимов и скорингом."""
    conn = get_db()
    q = q.strip()

    # Если это код — ищем по коду
    if re.match(r'^\d+$', q):
        rows = conn.execute(
            '''SELECT code, name_ru, poshlina_pct, poshlina_usd_per_unit, poshlina_unit,
                      nds_pct, unit1, aksiz_uzs_per_unit, aksiz_unit
               FROM tnved WHERE code LIKE ? ORDER BY code LIMIT ?''',
            (q + '%', limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    terms = expand_query(q)

    # Строим запрос с OR по всем термам и скорингом
    # LOWER() на name_ru делает поиск нечувствительным к регистру кириллицы
    # Скор: code match = 200, каждый термин в name_ru = 10
    score_cases = '\n'.join(
        [f"+ CASE WHEN lower_ru(name_ru) LIKE ? THEN 10 ELSE 0 END" for _ in terms]
    )
    where_clauses = ' OR '.join(['lower_ru(name_ru) LIKE ?' for _ in terms])

    sql = f'''
        SELECT code, name_ru, poshlina_pct, poshlina_usd_per_unit, poshlina_unit,
               nds_pct, unit1, aksiz_uzs_per_unit, aksiz_unit,
               (CASE WHEN code LIKE ? THEN 200 ELSE 0 END
                {score_cases}) AS _score
        FROM tnved
        WHERE code LIKE ? OR ({where_clauses})
        ORDER BY _score DESC, LENGTH(name_ru) ASC, code
        LIMIT ?
    '''
    like_terms = ['%' + t.lower() + '%' for t in terms]
    params = [q + '%'] + like_terms + [q + '%'] + like_terms + [limit]
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── СНГ ЗСТ (Зона свободной торговли) — 0% пошлина ──────────────────────────
CIS_CODES = {'643','112','398','417','762','031','051','498','804','795'}
# 643=Россия 112=Беларусь 398=Казахстан 417=Кыргызстан 762=Таджикистан
# 031=Азербайджан 051=Армения 498=Молдова 804=Украина 795=Туркмения

# ── Шкала таможенного сбора (ПКМ №700) ───────────────────────────────────────
SBOR = [(200,.5),(1000,1),(5000,2),(20000,5),(75000,10),(200000,20),(600000,40),(None,75)]

def calc_sbor(usd):
    for mx, brv in SBOR:
        if mx is None or usd <= mx: return brv
    return 75

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function('lower_ru', 1, lambda s: s.lower() if s else '')
    return conn

# ── Прокси к customs.uz ───────────────────────────────────────────────────────
def customs_uz_lookup(code, origin='', sending='', trade=''):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    params = (f'tnved={code}&rejim=import&sending_country={sending}'
              f'&receiving_country=UZ&lang=ru_RU&orign_country={origin}&trade_country={trade}')
    req = urllib.request.Request(
        'https://tarif.customs.uz/calc/view_calc.jsp',
        data=params.encode(),
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible)',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://tarif.customs.uz/ru'
        }
    )
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=12)
        html = resp.read().decode('utf-8', errors='ignore')
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()

        m_duty   = re.search(r'20:\s*Bojxona\s*boji\s*([\d\.,]+)\s*(%)', text)
        m_no_duty= re.search(r'20:\s*Bojxona\s*boji[^2]*?(?:нет|0\.0\s*%)', text, re.I)
        m_aksiz  = re.search(r'27:\s*Aksiz\s*solig.i\s*([\d\.,]+)', text)
        m_nds    = re.search(r'29:\s*QQS\s*([\d\.,]+)', text)
        m_law    = re.search(r'(ПП-\d+[^\s]*\s*от\s*[\d\.]+\.[\d]+)', text)
        m_law2   = re.search(r'(ЗРУ-\d+[^\s]*\s*от\s*[\d\.]+\.[\d]+)', text)

        if m_duty:
            duty_pct = float(m_duty.group(1).replace(',','.'))
        elif m_no_duty:
            duty_pct = 0.0
        else:
            duty_pct = None

        return {
            'ok': True,
            'duty_pct': duty_pct,
            'aksiz_pct': float(m_aksiz.group(1).replace(',','.')) if m_aksiz else None,
            'nds_pct':   float(m_nds.group(1).replace(',','.'))   if m_nds   else 12.0,
            'law_duty':  m_law.group(1)  if m_law  else None,
            'law_nds':   m_law2.group(1) if m_law2 else None,
            'raw': text[max(0,text.find('20:')):text.find('20:')+400] if '20:' in text else text[:400]
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# ── Список стран (codes from customs.uz) ──────────────────────────────────────
# Полный список 246 стран из tarif.customs.uz
COUNTRIES = {"036":"АВСТРАЛИЯ","040":"АВСТРИЯ","031":"АЗЕРБАЙДЖАН","008":"АЛБАНИЯ","012":"АЛЖИР","660":"АНГИЛЬЯ","024":"АНГОЛА","020":"АНДОРРА","010":"АНТАРКТИДА","028":"АНТИГУА И БАРБУДА","032":"АРГЕНТИНА","051":"АРМЕНИЯ","533":"АРУБА","004":"АФГАНИСТАН","044":"БАГАМЫ","050":"БАНГЛАДЕШ","052":"БАРБАДОС","048":"БАХРЕЙН","112":"БЕЛАРУСЬ","084":"БЕЛИЗ","056":"БЕЛЬГИЯ","204":"БЕНИН","060":"БЕРМУДЫ","100":"БОЛГАРИЯ","068":"БОЛИВИЯ","070":"БОСНИЯ И ГЕРЦЕГОВИНА","072":"БОТСВАНА","076":"БРАЗИЛИЯ","086":"БРИТАН. ТЕРРИТОРИИ","096":"БРУНЕЙ","074":"БУВЕ","854":"БУРКИНА-ФАСО","108":"БУРУНДИ","064":"БУТАН","548":"ВАНУАТУ","336":"ВАТИКАН","348":"ВЕНГРИЯ","862":"ВЕНЕСУЭЛА","850":"ВИРГИНСКИЕ О-ВА (США)","092":"ВИРГИНСКИЕ О-ВА (БРИТ)","016":"ВОСТОЧНОЕ САМОА","704":"ВЬЕТНАМ","266":"ГАБОН","332":"ГАИТИ","328":"ГАЙАНА","270":"ГАМБИЯ","288":"ГАНА","312":"ГВАДЕЛУПА","320":"ГВАТЕМАЛА","254":"ГВИАНА","324":"ГВИНЕЯ","624":"ГВИНЕЯ-БИСАУ","276":"ГЕРМАНИЯ","831":"ГЕРНСИ","292":"ГИБРАЛТАР","340":"ГОНДУРАС","344":"ГОНКОНГ","308":"ГРЕНАДА","304":"ГРЕНЛАНДИЯ","300":"ГРЕЦИЯ","268":"ГРУЗИЯ","316":"ГУАМ","208":"ДАНИЯ","832":"ДЖЕРСИ","262":"ДЖИБУТИ","212":"ДОМИНИКА","214":"ДОМИНИКАНСКАЯ РЕСПУБЛИКА","818":"ЕГИПЕТ","894":"ЗАМБИЯ","732":"ЗАПАДНАЯ САХАРА","716":"ЗИМБАБВЕ","376":"ИЗРАИЛЬ","356":"ИНДИЯ","360":"ИНДОНЕЗИЯ","400":"ИОРДАНИЯ","368":"ИРАК","364":"ИРАН","372":"ИРЛАНДИЯ","352":"ИСЛАНДИЯ","724":"ИСПАНИЯ","380":"ИТАЛИЯ","887":"ЙЕМЕН","132":"КАБО-ВЕРДЕ","398":"КАЗАХСТАН","136":"КАЙМАН","116":"КАМБОДЖА","120":"КАМЕРУН","124":"КАНАДА","634":"КАТАР","404":"КЕНИЯ","196":"КИПР","296":"КИРИБАТИ","156":"КИТАЙ","166":"КОКОСОВЫЕ О-ВА","170":"КОЛУМБИЯ","174":"КОМОРЫ","178":"КОНГО","180":"КОНГО (ДРК)","410":"КОРЕЯ (ЮЖН)","408":"КОРЕЯ (КНДР)","188":"КОСТА-РИКА","384":"КОТ Д'ИВУАР","192":"КУБА","414":"КУВЕЙТ","417":"КЫРГЫЗСТАН","418":"ЛАОС","428":"ЛАТВИЯ","426":"ЛЕСОТО","430":"ЛИБЕРИЯ","422":"ЛИВАН","434":"ЛИВИЯ","440":"ЛИТВА","438":"ЛИХТЕНШТЕЙН","442":"ЛЮКСЕМБУРГ","480":"МАВРИКИЙ","478":"МАВРИТАНИЯ","450":"МАДАГАСКАР","175":"МАЙОТТА","446":"МАКАО","807":"МАКЕДОНИЯ (С.М.)","454":"МАЛАВИ","458":"МАЛАЙЗИЯ","466":"МАЛИ","581":"МАЛЫЕ ТИХООК. ОСТРОВА (США)","462":"МАЛЬДИВЫ","470":"МАЛЬТА","580":"МАРИАНСКИЕ ОСТРОВА","504":"МАРОККО","474":"МАРТИНИКА","584":"МАРШАЛЛОВЫ О-ВА","484":"МЕКСИКА","583":"МИКРОНЕЗИЯ","508":"МОЗАМБИК","498":"МОЛДОВА","492":"МОНАКО","496":"МОНГОЛИЯ","500":"МОНТСЕРРАТ","104":"МЬЯНМА","516":"НАМИБИЯ","520":"НАУРУ","000":"НЕ УКАЗАНА","524":"НЕПАЛ","562":"НИГЕР","566":"НИГЕРИЯ","530":"НИДЕРЛАНДСКИЕ АНТИЛЫ","528":"НИДЕРЛАНДЫ","558":"НИКАРАГУА","570":"НИУЭ","554":"НОВАЯ ЗЕЛАНДИЯ","540":"НОВАЯ КАЛЕДОНИЯ","578":"НОРВЕГИЯ","574":"НОРФОЛК","833":"О-В МЭН","162":"О-В РОЖДЕСТВА","184":"О-ВА КУКА","784":"ОАЭ","512":"ОМАН","586":"ПАКИСТАН","585":"ПАЛАУ","275":"ПАЛЕСТИНА","591":"ПАНАМА","598":"ПАПУА-НОВАЯ ГВИНЕЯ","600":"ПАРАГВАЙ","604":"ПЕРУ","612":"ПИТКЭРН","616":"ПОЛЬША","620":"ПОРТУГАЛИЯ","630":"ПУЭРТО-РИКО","999":"РАЗНЫЕ","638":"РЕЮНЬОН","643":"РОССИЯ","646":"РУАНДА","642":"РУМЫНИЯ","882":"САМОА","678":"САН-ТОМЕ И ПРИНСИПИ","674":"САН-МАРИНО","682":"САУДОВСКАЯ АРАВИЯ","748":"СВАЗИЛЕНД","654":"СВЯТАЯ ЕЛЕНА","690":"СЕЙШЕЛЫ","666":"СЕН-ПЬЕР И МИКЕЛОН","686":"СЕНЕГАЛ","670":"СЕНТ-ВИНСЕНТ И ГРЕНАДИНЫ","659":"СЕНТ-КИТС И НЕВИС","662":"СЕНТ-ЛЮСИЯ","688":"СЕРБИЯ","702":"СИНГАПУР","760":"СИРИЯ","703":"СЛОВАКИЯ","705":"СЛОВЕНИЯ","826":"ВЕЛИКОБРИТАНИЯ","090":"СОЛОМОНОВЫ О-ВА","706":"СОМАЛИ","736":"СУДАН","740":"СУРИНАМ","840":"США","694":"СЬЕРРА-ЛЕОНЕ","762":"ТАДЖИКИСТАН","764":"ТАИЛАНД","158":"ТАЙВАНЬ","834":"ТАНЗАНИЯ","796":"ТЕРКС И КАЙКОС","626":"ТИМОР-ЛЕСТЕ","768":"ТОГО","772":"ТОКЕЛАУ","776":"ТОНГА","780":"ТРИНИДАД И ТОБАГО","798":"ТУВАЛУ","788":"ТУНИС","795":"ТУРКМЕНИЯ","792":"ТУРЦИЯ","800":"УГАНДА","860":"УЗБЕКИСТАН","804":"УКРАИНА","876":"УОЛЛИС И ФУТУНА","858":"УРУГВАЙ","234":"ФАРЕРСКИЕ О-ВА","242":"ФИДЖИ","608":"ФИЛИППИНЫ","246":"ФИНЛЯНДИЯ","238":"ФОЛКЛЕНДСКИЕ О-ВА","260":"ФР. ЮЖНЫЕ ТЕРРИТОРИИ","250":"ФРАНЦИЯ","258":"ФРАНЦУЗСКАЯ ПОЛИНЕЗИЯ","334":"ХЕРД И МАКДОНАЛЬД","191":"ХОРВАТИЯ","140":"ЦАР","148":"ЧАД","499":"ЧЕРНОГОРИЯ","203":"ЧЕХИЯ","152":"ЧИЛИ","756":"ШВЕЙЦАРИЯ","752":"ШВЕЦИЯ","744":"ШПИЦБЕРГЕН","144":"ШРИ-ЛАНКА","218":"ЭКВАДОР","226":"ЭКВАТОР. ГВИНЕЯ","248":"ЭЛАНДСКИЕ ОСТРОВА","222":"ЭЛЬ-САЛЬВАДОР","232":"ЭРИТРЕЯ","233":"ЭСТОНИЯ","231":"ЭФИОПИЯ","710":"ЮЖНАЯ АФРИКА","239":"ЮЖНАЯ ДЖОРДЖИЯ","388":"ЯМАЙКА","392":"ЯПОНИЯ"}

COUNTRIES_SORTED = sorted(COUNTRIES.items(), key=lambda x: x[1])

# ── Переводы узбекских названий организаций и документов ──────────────────────
_ORG_RU = {
    'Ўзбекистон техник жиҳатдан тартибга солиш агентлиги':
        'Агентство по техническому регулированию Узбекистана',
    'Ўзбекистон Республикаси Ветеринария ва чорвачиликни ривожлантириш қўмитаси':
        'Комитет по развитию ветеринарии и животноводства РУз',
    'Ўзбекистон Республикаси Давлат Санитария-Эпидемиология Назорат Маркази':
        'Госцентр санитарно-эпидемиологического надзора РУз',
    "O&#39;zbekiston Respublikasi o&#39;simliklar karantini va himoyasi agentligi":
        'Агентство по карантину и защите растений РУз',
    "O'zbekiston Respublikasi o'simliklar karantini va himoyasi agentligi":
        'Агентство по карантину и защите растений РУз',
    "O'zbekiston Respublikasi Investitsiyalar, sanoat va savdo vazirligi":
        'Министерство инвестиций, промышленности и торговли РУз',
    "Oʻzbekiston Respublikasi Investitsiyalar, sanoat va savdo vazirligi":
        'Министерство инвестиций, промышленности и торговли РУз',
    'Ўзбекистон Республикаси Экология ва Атроф Муҳитни Муҳофаза Қилиш Давлат Қўмитаси Ҳузуридаги &quot;Давлат Экологик Сертификатлаштириш ва Стандартлаштириш Маркази&quot; ДУК':
        'ГУП «Госцентр экологической сертификации и стандартизации» при Госкомэкологии РУз',
    "Oʻzbekiston Respublikasi Vazirlar Mahkamasi":
        'Кабинет Министров Республики Узбекистан',
    "O'zbekiston Respublikasi Vazirlar Mahkamasi":
        'Кабинет Министров Республики Узбекистан',
    'Электромагнит Мослашув Маркази ДУК':
        'ГУП «Центр электромагнитной совместимости» (ЦЭМС)',
    'Ўзбекистон Республикаси Ички Ишлар Вазирлиги':
        'Министерство внутренних дел Республики Узбекистан',
}

_DOC_RU = {
    'Мувофиқлик сертификати':
        'Сертификат соответствия',
    'Санитария-эпидемиологик хулоса':
        'Санитарно-эпидемиологическое заключение',
    'Ветеринария гувохномаси форма-2':
        'Ветеринарное свидетельство Форма-2',
    'Ветеринария гувохномаси форма-3':
        'Ветеринарное свидетельство Форма-3',
    'Veterinariya sertifikati 5A':
        'Ветеринарный сертификат 5A',
    'Veterinariya sertifikati 5B':
        'Ветеринарный сертификат 5B',
    'Veterinariya sertifikati 5С':
        'Ветеринарный сертификат 5C',
    'Veterinariya sertifikati 5D':
        'Ветеринарный сертификат 5D',
    'Veterinariya sertifikati 5E':
        'Ветеринарный сертификат 5E',
    'Veterinariya sertifikati 5F':
        'Ветеринарный сертификат 5F',
    'Veterinariya guvohnomasi Forma - 1':
        'Ветеринарное свидетельство Форма-1',
    'Фитосанитария сертификати':
        'Фитосанитарный сертификат',
    'Карантин рухсатномаси':
        'Карантинное разрешение',
    'Экология мувофиклик сертификати':
        'Экологический сертификат соответствия',
    'Ўзбекистон Республикаси Президенти ва Ўзбекистон Республикаси Ҳукуматининг қарорлари асосида экспорт қилинадиган буюмлар ва маҳсулотлар':
        'Товары, экспортируемые на основании решений Президента или Правительства РУз',
    "O'zbekiston Respublikasi Prezidentining hujjatlari yoki O'zbekiston Respublikasi Vazirlar Mahkamasining qarorlari asosida beriladigan litsenziyalar bo'yicha import qilinadigan maxsus tovar":
        'Специальный товар, ввозимый по лицензии на основании решений Президента или Кабмина РУз',
    "O'zbekiston Respublikasi Prezidentining hujjatlari yoki O'zbekiston Respublikasi Vazirlar Mahkamasining qarorlari asosida beriladigan litsenziyalar bo'yicha eksport qilinadigan maxsus tovar":
        'Специальный товар, вывозимый по лицензии на основании решений Президента или Кабмина РУз',
}

_ORG_URL = {
    'Агентство по техническому регулированию Узбекистана':
        'https://standart.uz',
    'Комитет по развитию ветеринарии и животноводства РУз':
        'https://vet.uz',
    'Госцентр санитарно-эпидемиологического надзора РУз':
        'https://ssv.uz',
    'Агентство по карантину и защите растений РУз':
        'https://karantin.uz',
    'Министерство инвестиций, промышленности и торговли РУз':
        'https://invest.gov.uz',
    'ГУП «Госцентр экологической сертификации и стандартизации» при Госкомэкологии РУз':
        'https://eco.gov.uz',
    'ГУП «Центр электромагнитной совместимости» (ЦЭМС)':
        'https://cemc.uz',
    'Кабинет Министров Республики Узбекистан':
        'https://gov.uz',
    'Министерство внутренних дел Республики Узбекистан':
        'https://mia.uz',
}

def _tr_org(s):
    return _ORG_RU.get(s, s)

def _tr_doc(s):
    return _DOC_RU.get(s, s)

def _org_url(translated_org):
    return _ORG_URL.get(translated_org, '')

# ── Страны с ненулевой пошлиной при ввозе из них (запреты/ограничения) ────────
# Коды стран, для которых действует ряд запретов (non_tariff)
NON_TARIFF_BAN_COUNTRIES = {'643', '112', '398', '642', '100', '792'}  # RU, BY, KZ, RO, BG, TR

def get_docs(code, rejim='import'):
    """Возвращает документы для кода ТНВЭД из таблицы gtk_docs."""
    if not code:
        return {'docs': [], 'restrictions': []}
    conn = get_db()
    # Фильтр режима: import → import+both, export → export+both
    if rejim == 'export':
        rejim_filter = ("rejim IN ('export','both')", ())
    else:
        rejim_filter = ("rejim IN ('import','both')", ())

    # Точное совпадение (DISTINCT по org+doc)
    docs = conn.execute(
        f'SELECT DISTINCT org_name, doc_name FROM gtk_docs WHERE code=? AND {rejim_filter[0]}',
        (code,) + rejim_filter[1]
    ).fetchall()
    # Если нет точного — попробовать более короткие коды по убыванию длины
    if not docs:
        for plen in (8, 6, 4):
            prefix = code[:plen]
            docs = conn.execute(
                f'''SELECT DISTINCT org_name, doc_name FROM gtk_docs
                   WHERE code LIKE ? AND {rejim_filter[0]} GROUP BY org_name, doc_name''',
                (prefix + '%',) + rejim_filter[1]
            ).fetchall()
            if docs:
                break
    # non-tariff ограничения: проверяем сначала точный код, потом префиксы
    restrictions = []
    seen_restrict = set()
    for plen in (10, 9, 8, 7, 6, 5, 4, 3, 2):
        prefix = code[:plen]
        rows = conn.execute(
            'SELECT code, descr, condition, legal FROM non_tariff WHERE code=? OR code=?',
            (code, prefix)
        ).fetchall()
        for r in rows:
            key = r[1]
            if key not in seen_restrict:
                seen_restrict.add(key)
                restrictions.append({'code': r[0], 'descr': r[1], 'condition': r[2], 'legal': r[3]})
    conn.close()
    result = []
    for d in docs:
        org_ru = _tr_org(d[0])
        result.append({'org': org_ru, 'doc': _tr_doc(d[1]), 'url': _org_url(org_ru)})
    return {'docs': result, 'restrictions': restrictions}

def country_items_json():
    """Список стран в JSON для JS-поиска."""
    return json.dumps(
        [{'code': k, 'name': v} for k, v in COUNTRIES_SORTED],
        ensure_ascii=False
    )

def get_tree(prefix=''):
    """Иерархическое дерево ТН ВЭД: '' → группы, '85' → позиции, '8525' → коды."""
    conn = get_db()
    prefix = (prefix or '').strip()
    result = []
    if len(prefix) == 0:
        rows = conn.execute(
            'SELECT SUBSTR(code,1,2) grp, COUNT(*) cnt FROM tnved GROUP BY grp ORDER BY grp'
        ).fetchall()
        for row in rows:
            result.append({'prefix': row[0], 'count': row[1]})
    elif len(prefix) == 2:
        rows = conn.execute(
            'SELECT SUBSTR(code,1,4) pos, COUNT(*) cnt, MIN(name_ru) name '
            'FROM tnved WHERE code LIKE ? GROUP BY pos ORDER BY pos',
            (prefix + '%',)
        ).fetchall()
        for row in rows:
            result.append({'prefix': row[0], 'count': row[1], 'name': (row[2] or '')[:80]})
    elif len(prefix) >= 4:
        rows = conn.execute(
            'SELECT code, name_ru, poshlina_pct, nds_pct FROM tnved WHERE code LIKE ? ORDER BY code',
            (prefix + '%',)
        ).fetchall()
        for row in rows:
            result.append({'code': row[0], 'name': row[1] or '', 'poshlina_pct': row[2], 'nds_pct': row[3]})
    conn.close()
    return result

# ─── HTML PAGE ─────────────────────────────────────────────────────────────────
PAGE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Тарифный калькулятор — ТН ВЭД Узбекистан</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{
  --primary:#2563EB;--primary-dark:#1D4ED8;--primary-light:#EFF6FF;--primary-mid:#BFDBFE;
  --success:#059669;--success-bg:#ECFDF5;--success-border:#A7F3D0;
  --warning:#D97706;--warning-bg:#FFFBEB;--warning-border:#FCD34D;
  --danger:#DC2626;--danger-bg:#FEF2F2;--danger-border:#FECACA;
  --orange:#EA580C;--orange-bg:#FFF7ED;--orange-border:#FED7AA;
  --gray-50:#F8FAFC;--gray-100:#F1F5F9;--gray-200:#E2E8F0;--gray-300:#CBD5E1;
  --gray-400:#94A3B8;--gray-500:#64748B;--gray-700:#334155;--gray-900:#0F172A;
  --radius:10px;--radius-sm:6px;--radius-lg:14px;
  --shadow-sm:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
  --shadow:0 4px 6px -1px rgba(0,0,0,.07),0 2px 4px -2px rgba(0,0,0,.05);
  --shadow-md:0 10px 15px -3px rgba(0,0,0,.08),0 4px 6px -4px rgba(0,0,0,.05);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--gray-50);color:var(--gray-900);min-height:100vh;font-size:14px;line-height:1.5}

/* ══ HEADER ══ */
.hdr{background:linear-gradient(135deg,#1D4ED8 0%,#2563EB 60%,#3B82F6 100%);color:#fff;padding:14px 24px;display:flex;align-items:center;justify-content:center;gap:16px;box-shadow:0 2px 12px rgba(37,99,235,.35)}
.hdr-logo{font-size:26px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.2))}
.hdr-title{font-size:16px;font-weight:700;letter-spacing:-.2px}
.hdr-sub{font-size:11px;opacity:.8;margin-top:1px;font-weight:400}
.hdr-nav{margin-left:auto;display:flex;align-items:center;gap:8px}
.hdr-nav a{color:rgba(255,255,255,.9);text-decoration:none;font-size:12px;font-weight:500;padding:6px 14px;border:1px solid rgba(255,255,255,.3);border-radius:var(--radius-sm);transition:all .15s;backdrop-filter:blur(4px)}
.hdr-nav a:hover{background:rgba(255,255,255,.2);border-color:rgba(255,255,255,.6)}
/* ══ FOOTER ══ */
.ftr{background:linear-gradient(135deg,#1D4ED8 0%,#2563EB 60%,#3B82F6 100%);color:#fff;padding:10px 24px;display:flex;align-items:center;justify-content:center;gap:12px;box-shadow:0 -2px 12px rgba(37,99,235,.2);margin-top:24px}
.ftr a{color:rgba(255,255,255,.9);text-decoration:none;font-size:12px;font-weight:500;padding:6px 14px;border:1px solid rgba(255,255,255,.3);border-radius:var(--radius-sm);transition:all .15s;backdrop-filter:blur(4px)}
.ftr a:hover{background:rgba(255,255,255,.2);border-color:rgba(255,255,255,.6)}
.ftr-user{font-size:12px;color:rgba(255,255,255,.85);font-weight:500;white-space:nowrap}
.tok-badge{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:rgba(255,255,255,.18);color:#fff;white-space:nowrap;border:1px solid rgba(255,255,255,.3)}
.tok-badge.tok-low{background:rgba(239,68,68,.35);border-color:rgba(239,68,68,.6)}
.ftr-sep{width:1px;height:16px;background:rgba(255,255,255,.25)}

/* ══ MAIN WRAP ══ */
.main-wrap{max-width:1000px;margin:0 auto;padding:20px 16px}

/* ══ CARDS ══ */
.wcard,.section{background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);margin-bottom:10px;box-shadow:var(--shadow-sm)}

/* ══ SEARCH BAR ══ */
.search-bar{display:flex;align-items:center;gap:10px;padding:16px 18px;flex-wrap:wrap}
.search-wrap{position:relative;flex:1;min-width:200px;max-width:460px}
.search-clear{position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:var(--gray-400);font-size:18px;line-height:1;padding:0;display:none}
.search-clear:hover{color:var(--gray-600)}
.search-inp{width:100%;padding:10px 14px;border:1.5px solid var(--gray-200);border-radius:var(--radius-sm);font-size:14px;font-family:inherit;outline:none;transition:border-color .15s,box-shadow .15s;background:#fff}
.search-inp:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(37,99,235,.12)}
.search-inp::placeholder{color:var(--gray-400)}
#ac-list{position:absolute;top:calc(100% + 4px);left:0;right:0;background:#fff;border:1.5px solid var(--primary);border-radius:var(--radius-sm);max-height:300px;overflow-y:auto;z-index:400;display:none;box-shadow:var(--shadow-md)}
#ac-list div{padding:9px 14px;cursor:pointer;font-size:13px;border-bottom:1px solid var(--gray-100);line-height:1.4;transition:background .1s}
#ac-list div:hover{background:var(--primary-light)}
#ac-list div:last-child{border-bottom:none}
.ac-code{font-family:'Courier New',monospace;font-weight:700;color:var(--primary);margin-right:8px;font-size:12px}
.btn-search{background:var(--primary);color:#fff;border:none;padding:10px 16px;border-radius:var(--radius-sm);cursor:pointer;font-size:17px;line-height:1;transition:background .15s;flex-shrink:0}
.btn-search:hover{background:var(--primary-dark)}
.dir-group{display:flex;align-items:center;gap:14px;margin-left:4px}
.dir-lbl{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;font-weight:500;color:var(--gray-700)}
.dir-lbl input{accent-color:var(--primary);width:15px;height:15px;cursor:pointer}
.cis-badge{background:var(--success-bg);color:var(--success);font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px;border:1px solid var(--success-border);margin-left:6px}
.err-msg{color:var(--danger);font-size:12px;padding:8px 14px;background:var(--danger-bg);border-radius:var(--radius-sm);margin:0 18px 12px;display:none;border:1px solid var(--danger-border)}
#toast{position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:9999;background:#1e293b;color:#fff;padding:28px 48px;border-radius:16px;font-size:22px;box-shadow:0 8px 32px rgba(0,0,0,.25);display:none;max-width:90vw;text-align:center;line-height:1.6}

/* ══ CODE PANEL ══ */
#code-panel{display:none;padding:0 18px 14px}
.cp-code{font-family:'Courier New',monospace;font-size:18px;font-weight:700;color:var(--primary-dark);letter-spacing:.5px}
.cp-name{font-size:13px;color:var(--gray-500);margin:4px 0 10px;line-height:1.5}
.cp-tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.tag{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:.2px}
.tag-red{background:var(--danger-bg);color:var(--danger);border:1px solid var(--danger-border)}
.tag-green{background:var(--success-bg);color:var(--success);border:1px solid var(--success-border)}
.tag-blue{background:var(--primary-light);color:var(--primary-dark);border:1px solid var(--primary-mid)}
.tag-orange{background:var(--orange-bg);color:var(--orange);border:1px solid var(--orange-border)}
.tag-gray{background:var(--gray-100);color:var(--gray-500);border:1px solid var(--gray-200)}
#rate-info{display:none}
.ri-table{width:100%;border-collapse:collapse;font-size:12.5px}
.ri-table td{padding:6px 10px;border-bottom:1px solid var(--gray-100)}
.ri-table .lbl{color:var(--gray-500);width:55%}
.ri-table .val{font-weight:600;text-align:right;color:var(--gray-900)}
.ri-highlight{background:var(--primary-light)}
.ri-formula{font-family:'Courier New',monospace;font-size:11px;color:var(--gray-700);padding:10px 14px;background:var(--gray-50);border-left:3px solid var(--primary);border-radius:0 var(--radius-sm) var(--radius-sm) 0;margin-top:10px;line-height:1.9}

/* ══ COUNTRY ROW ══ */
.country-bar{padding:16px 18px}
.country-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
@media(max-width:580px){.country-row{grid-template-columns:1fr}}
.cs-field>label{display:block;font-size:11px;color:var(--gray-500);margin-bottom:5px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}

/* ══ CUSTOM SELECT ══ */
.cs-wrap{position:relative;user-select:none}
.cs-selected{display:flex;align-items:center;padding:9px 34px 9px 12px;border:1.5px solid var(--gray-200);border-radius:var(--radius-sm);font-size:13px;cursor:pointer;background:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-height:38px;position:relative;transition:border-color .15s;font-family:inherit}
.cs-arr{position:absolute;right:12px;top:50%;transform:translateY(-50%);pointer-events:none;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid var(--gray-400)}
.cs-wrap.open .cs-selected{border-color:var(--primary);border-radius:var(--radius-sm) var(--radius-sm) 0 0;box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.cs-wrap.open .cs-arr{border-top:none;border-bottom:5px solid var(--primary)}
.cs-dropdown{display:none;position:absolute;top:100%;left:0;right:0;background:#fff;border:1.5px solid var(--primary);border-top:none;border-radius:0 0 var(--radius-sm) var(--radius-sm);z-index:300;box-shadow:var(--shadow-md)}
.cs-wrap.open .cs-dropdown{display:block}
.cs-search-inp{width:100%;padding:8px 12px;border:none;border-bottom:1px solid var(--gray-200);font-size:13px;outline:none;font-family:inherit}
.cs-list{max-height:220px;overflow-y:auto}
.cs-item{padding:7px 14px;font-size:12px;cursor:pointer;border-bottom:1px solid var(--gray-100);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:background .1s}
.cs-item:hover,.cs-item.cs-active{background:var(--primary-light);color:var(--primary-dark)}
.cs-item.cs-none{color:var(--gray-400);font-style:italic}
.cs-no-results{padding:12px 14px;font-size:12px;color:var(--gray-400);text-align:center}
#country-note{font-size:12.5px;margin-top:10px;padding:9px 12px;border-radius:var(--radius-sm);background:var(--warning-bg);border:1px solid var(--warning-border);color:#92400E}

/* ══ ACTION BAR ══ */
.action-bar{display:flex;align-items:center;gap:8px;padding:10px 18px;flex-wrap:wrap;border-top:1px solid var(--gray-100);background:var(--gray-50);border-radius:0 0 var(--radius) var(--radius)}
.abtn{padding:7px 14px;border-radius:var(--radius-sm);font-size:12px;font-weight:600;cursor:pointer;border:1.5px solid;font-family:inherit;transition:all .15s}
.abtn-green{background:#fff;color:var(--success);border-color:var(--success-border)}
.abtn-green:hover{background:var(--success-bg)}
.abtn-amber{background:#fff;color:var(--warning);border-color:var(--warning-border)}
.abtn-amber:hover{background:var(--warning-bg)}
.abtn-blue{background:#fff;color:var(--primary);border-color:var(--primary-mid)}
.abtn-blue:hover{background:var(--primary-light)}
#rates-date{font-size:11px;color:var(--gray-400);margin-left:4px}
.loading{display:none;font-size:13px;color:var(--primary);padding:0 8px}

/* ══ SECTIONS ══ */
.section{overflow:visible}
.sec-hdr{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;cursor:pointer;user-select:none;transition:background .15s;border-radius:var(--radius) var(--radius) 0 0}
.sec-hdr:hover{background:var(--gray-50)}
.section.collapsed .sec-hdr{border-radius:var(--radius)}
.sec-title{font-size:15px;font-weight:600;color:var(--primary)}
.sec-arr{color:var(--primary);font-size:12px;transition:transform .2s;opacity:.7}
.section.collapsed .sec-arr{transform:rotate(180deg)}
.sec-body{padding:4px 20px 18px;border-top:1px solid var(--gray-100)}
.section.collapsed .sec-body{display:none}

/* ══ RATES TABLE ══ */
.rates-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:12px}
.rates-tbl th{padding:10px 14px;text-align:left;background:var(--gray-50);border:1px solid var(--gray-200);color:var(--gray-500);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.rates-tbl td{padding:10px 14px;border:1px solid var(--gray-200);vertical-align:middle}
.rates-tbl .col-type{color:var(--gray-700);font-weight:500}
.rates-tbl .col-rate{font-weight:700;color:var(--primary-dark);font-family:'Courier New',monospace;text-align:center;width:130px}
.rates-tbl .col-law{color:var(--gray-500);font-size:12px}
.rates-tbl tr:hover td{background:var(--gray-50)}

/* ══ DOCS TABLE ══ */
.docs-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:12px}
.docs-tbl th{padding:10px 14px;text-align:left;background:var(--gray-50);border:1px solid var(--gray-200);color:var(--gray-500);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.docs-tbl td{padding:11px 14px;border:1px solid var(--gray-200);color:var(--gray-900)}
.docs-tbl td.doc-org{color:var(--primary);font-weight:500}
.docs-tbl td.doc-name{color:var(--gray-700)}
.docs-tbl tr:hover td{background:var(--gray-50)}
.doc-org-link{color:var(--primary);text-decoration:none;font-weight:500}
.doc-org-link:hover{text-decoration:underline;color:var(--primary-dark)}
.doc-restrict-block{background:var(--warning-bg);border:1px solid var(--warning-border);border-radius:var(--radius-sm);padding:12px 16px;font-size:12px}
.doc-restrict-block .restrict-title{font-weight:700;color:var(--orange);margin-bottom:8px;font-size:13px}
.doc-restrict-item{margin-bottom:5px;color:var(--gray-700);line-height:1.5}
.doc-restrict-item b{color:var(--danger)}

/* ══ CALCULATOR ══ */
.calc-row{display:grid;grid-template-columns:1fr 90px 1fr 1fr;gap:10px;align-items:end;margin:12px 0 6px}
@media(max-width:680px){.calc-row{grid-template-columns:1fr 1fr}}
.cf label{display:block;font-size:11px;color:var(--gray-500);margin-bottom:5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.cf input,.cf select{width:100%;padding:9px 12px;border:1.5px solid var(--gray-200);border-radius:var(--radius-sm);font-size:13px;font-family:inherit;outline:none;transition:border-color .15s,box-shadow .15s;background:#fff}
.cf input:focus,.cf select:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.dosmotr-box{background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius-sm);padding:12px 16px;margin:10px 0}
.dosmotr-box .d-title{font-size:13px;font-weight:600;color:var(--gray-700);margin-bottom:10px}
.dosmotr-grid{display:flex;gap:28px}
.di label{display:block;font-size:11px;color:var(--gray-500);margin-bottom:5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.di input{padding:8px 12px;border:1.5px solid var(--gray-200);border-radius:var(--radius-sm);font-size:13px;font-family:inherit;width:100px;outline:none;transition:border-color .15s}
.di input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.price3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:10px 0}
@media(max-width:580px){.price3{grid-template-columns:1fr}}
.price3 .pf label{display:block;font-size:11px;color:var(--gray-500);margin-bottom:5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.price3 .pf input{width:100%;padding:9px 12px;border:1.5px solid var(--gray-200);border-radius:var(--radius-sm);font-size:13px;font-family:inherit;outline:none;transition:border-color .15s}
.price3 .pf input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.calc-footer{display:flex;justify-content:flex-end;gap:10px;margin-top:18px;align-items:center}
.btn-calc{background:var(--primary);color:#fff;border:none;padding:11px 32px;border-radius:var(--radius-sm);font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:all .15s;box-shadow:0 2px 8px rgba(37,99,235,.3)}
.btn-calc:hover{background:var(--primary-dark);box-shadow:0 4px 12px rgba(37,99,235,.4);transform:translateY(-1px)}
.btn-compare{background:#fff;color:var(--primary);border:1.5px solid var(--primary-mid);padding:11px 20px;border-radius:var(--radius-sm);font-size:13px;font-weight:600;font-family:inherit;cursor:pointer;transition:all .15s}
.btn-compare:hover{background:var(--primary-light);border-color:var(--primary)}
#alc-wrap{display:none}

/* ══ RESULTS ══ */
#result-area{display:none;margin-top:16px;padding-top:16px;border-top:1px solid var(--gray-100)}
#placeholder{text-align:center;padding:32px;color:var(--gray-300);font-size:13px}
.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
@media(max-width:580px){.compare-grid{grid-template-columns:1fr}}
.compare-col{border-radius:var(--radius-sm);padding:16px;border:1.5px solid}
.col-ours{border-color:var(--primary-mid);background:var(--primary-light)}
.col-customs{border-color:var(--gray-200);background:var(--gray-50)}
.col-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.col-ours .col-title{color:var(--primary-dark)}
.col-customs .col-title{color:var(--gray-500)}
.res-row{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(0,0,0,.05);font-size:13px}
.res-row:last-child{border-bottom:none}
.res-label{color:var(--gray-500)}
.res-val{font-weight:700;font-family:'Courier New',monospace;font-size:12px;color:var(--gray-900)}
.res-note{font-size:10px;color:var(--gray-400)}
.res-total{background:rgba(37,99,235,.12);border-radius:var(--radius-sm);padding:10px 12px;margin-top:10px;display:flex;justify-content:space-between;align-items:center}
.res-total-lbl{font-weight:700;font-size:13px;color:var(--primary-dark)}
.res-total-val{font-weight:800;font-size:16px;color:var(--primary-dark);font-family:'Courier New',monospace}
.diff-box{background:var(--warning-bg);border:1px solid var(--warning-border);border-radius:var(--radius-sm);padding:12px 16px;font-size:12px;margin-top:12px}
.diff-ok{background:var(--success-bg);border-color:var(--success-border)}
.formula-box{background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius-sm);padding:14px;margin-top:14px;font-size:11px;font-family:'Courier New',monospace;line-height:1.9;color:var(--gray-700);display:none}

/* ══ HISTORY PANEL ══ */
#hist-panel{display:none;background:#fff;border:1px solid var(--gray-200);border-radius:var(--radius);padding:18px;margin-bottom:10px;box-shadow:var(--shadow-sm)}
.hist-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.hist-hdr-title{font-size:14px;font-weight:700;color:var(--primary)}
.hist-close{cursor:pointer;color:var(--gray-300);font-size:20px;line-height:1;transition:color .15s}
.hist-close:hover{color:var(--gray-500)}
.hist-clear{background:none;border:1.5px solid var(--danger-border);color:var(--danger);border-radius:var(--radius-sm);padding:4px 10px;font-size:11px;font-family:inherit;cursor:pointer;transition:all .15s}
.hist-clear:hover{background:var(--danger-bg)}
.hist-tbl{width:100%;border-collapse:collapse;font-size:12px}
.hist-tbl th{background:var(--gray-50);padding:8px 12px;text-align:left;font-weight:600;color:var(--gray-500);border-bottom:2px solid var(--gray-200);font-size:11px;text-transform:uppercase;letter-spacing:.4px}
.hist-tbl td{padding:8px 12px;border-bottom:1px solid var(--gray-100);vertical-align:middle}
.hist-tbl tr:hover td{background:var(--gray-50)}
.hist-tbl .mono{font-family:'Courier New',monospace;font-weight:700;color:var(--primary)}
.hist-del{cursor:pointer;color:var(--danger-border);font-size:14px;padding:0 4px;transition:color .15s}
.hist-del:hover{color:var(--danger)}
.hist-empty{color:var(--gray-300);text-align:center;padding:24px;font-size:13px}

/* ══ SBOR DETAILS ══ */
details summary{cursor:pointer;font-size:12px;color:var(--primary);font-weight:600;margin:10px 0 0;user-select:none}
details table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px;border-radius:var(--radius-sm);overflow:hidden}
details td,details th{padding:6px 10px;border:1px solid var(--gray-200)}
details th{background:var(--gray-50);font-weight:600;color:var(--gray-500);font-size:11px}
details tr:hover td{background:var(--gray-50)}

/* ══ TREE NAV ══ */
.tree-bc{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:4px 0 14px;font-size:12px;min-height:30px}
.tree-bc-item{color:var(--primary);cursor:pointer;font-weight:500}
.tree-bc-item:hover{text-decoration:underline}
.tree-bc-sep{color:var(--gray-300)}
.tree-bc-cur{color:var(--gray-700);font-weight:600}
.tree-sections{display:grid;grid-template-columns:repeat(auto-fill,minmax(195px,1fr));gap:10px}
.tree-sec-card{background:var(--primary-light);border:1.5px solid var(--primary-mid);border-radius:var(--radius-sm);padding:12px 14px;cursor:pointer;transition:all .15s}
.tree-sec-card:hover{background:#DBEAFE;border-color:var(--primary);box-shadow:var(--shadow-sm)}
.tree-sec-num{font-size:11px;font-weight:700;color:var(--primary);margin-bottom:3px;text-transform:uppercase;letter-spacing:.4px}
.tree-sec-name{font-size:12px;color:var(--gray-700);line-height:1.4}
.tree-sec-range{font-size:10px;color:var(--gray-400);margin-top:4px}
.tree-groups{display:flex;flex-wrap:wrap;gap:8px}
.tree-grp-btn{padding:8px 14px;border:1.5px solid var(--primary-mid);border-radius:var(--radius-sm);background:#fff;color:var(--primary);font-size:13px;font-family:'Courier New',monospace;cursor:pointer;font-weight:700;transition:all .15s}
.tree-grp-btn:hover{background:var(--primary-light);border-color:var(--primary)}
.tree-pos-item{display:flex;align-items:center;padding:9px 12px;border-bottom:1px solid var(--gray-100);cursor:pointer;transition:background .1s}
.tree-pos-item:hover{background:var(--primary-light)}
.tree-pos-code{font-family:'Courier New',monospace;font-weight:700;color:var(--primary);width:55px;flex-shrink:0;font-size:13px}
.tree-pos-name{flex:1;font-size:12px;color:var(--gray-500);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tree-pos-cnt{font-size:11px;color:var(--gray-300);margin-left:8px;flex-shrink:0}
.tree-code-tbl{width:100%;border-collapse:collapse;font-size:12px}
.tree-code-tbl th{padding:8px 12px;background:var(--gray-50);border:1px solid var(--gray-200);font-size:11px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:.4px}
.tree-code-tbl td{padding:8px 12px;border:1px solid var(--gray-200);vertical-align:top}
.tree-code-tbl tr:hover td{background:var(--primary-light)}
.tree-code-btn{color:var(--primary);cursor:pointer;font-family:'Courier New',monospace;font-weight:700;background:none;border:none;font-size:12px;padding:0;text-decoration:underline}
.tree-load{color:var(--gray-400);font-size:13px;padding:28px;text-align:center}

</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-logo">🛃</div>
  <div class="hdr-info">
    <div class="hdr-title">Тарифный калькулятор — ТН ВЭД Узбекистан</div>
    <div class="hdr-sub">ПП-181 от 14.05.2025 · с учётом страны происхождения</div>
  </div>
  <div class="hdr-nav">
    <span class="ftr-user">👤 CURRENT_USER_PLACEHOLDER</span>
    TOKENS_BADGE_PLACEHOLDER
    <div class="ftr-sep"></div>
    ADMIN_LINK_PLACEHOLDER
    <a href="/logout">Выйти</a>
  </div>
</div>

<div class="main-wrap">

  <!-- ── Навигация по дереву ТН ВЭД ─────────────────────────────────────────── -->
  <div class="section collapsed" id="sec-tree">
    <div class="sec-hdr" onclick="openTreeSection()">
      <span class="sec-title">🌳 Навигация по дереву ТН ВЭД</span><span class="sec-arr">▲</span>
    </div>
    <div class="sec-body">
      <div id="tree-bc" class="tree-bc"></div>
      <div id="tree-content"><div class="tree-load">Нажмите для загрузки...</div></div>
    </div>
  </div>

  <!-- ── Поиск + Направление ────────────────────────────────────────────────── -->
  <div class="wcard">
    <div class="search-bar">
      <div class="search-wrap">
        <input type="text" id="search-inp" class="search-inp"
               placeholder="Введите наименование товара или код ТН ВЭД..." autocomplete="off"
               style="padding-right:32px">
        <button class="search-clear" id="search-clear" onclick="clearSearch()" title="Очистить">✕</button>
        <div id="ac-list"></div>
      </div>
      <button class="btn-search" onclick="doSearch()" title="Найти">🔍</button>
      <div class="dir-group">
        <label class="dir-lbl"><input type="radio" name="direction" id="dir-import" value="import" checked> Импорт</label>
        <label class="dir-lbl"><input type="radio" name="direction" id="dir-export" value="export"> Экспорт</label>
      </div>
      <span id="cis-badge" class="cis-badge" style="display:none">ЗСТ СНГ — 0%</span>
    </div>
    <div id="code-error" class="err-msg">Код не найден в базе ТН ВЭД</div>
  <div id="toast"></div>
    <div id="code-panel">
      <div class="cp-code" id="cp-code"></div>
      <div class="cp-name" id="cp-name"></div>
      <div class="cp-tags" id="cp-tags"></div>
      <div id="rate-info">
        <table class="ri-table" style="margin-top:6px">
          <tr><td class="lbl">Ставка МФН (ПП-181)</td><td class="val" id="ri-mfn"></td></tr>
          <tr><td class="lbl">Ставка СНГ (ЗСТ)</td><td class="val">0%</td></tr>
          <tr class="ri-highlight"><td class="lbl"><b>Применяется</b></td><td class="val" id="ri-applied"></td></tr>
          <tr><td class="lbl">НДС</td><td class="val" id="ri-nds"></td></tr>
          <tr id="ri-aksiz-row" style="display:none"><td class="lbl">Акциз</td><td class="val" id="ri-aksiz"></td></tr>
          <tr><td class="lbl">Таможенный сбор</td><td class="val">По ПКМ №700 (0.5–75 БРВ)</td></tr>
          <tr><td class="lbl">Ед. измерения</td><td class="val" id="ri-unit"></td></tr>
        </table>
        <div class="ri-formula" id="ri-formula"></div>
      </div>
    </div>
    <!-- hidden input for manual code (used by JS) -->
    <input type="hidden" id="manual-code" value="">
    <!-- action bar inside top card -->
    <div class="action-bar">
      <button class="abtn abtn-green" onclick="saveHistory()">💾 Сохранить</button>
      <button class="abtn abtn-amber" onclick="toggleHistory()">📋 История</button>
      <button class="abtn abtn-blue" onclick="loadRates()" id="rates-btn">↻ Курс ЦБ</button>
      <span id="rates-date"></span>
      <div id="loading" class="loading">⏳ Запрос к tarif.customs.uz…</div>
    </div>
  </div>

  <!-- ── Страны ─────────────────────────────────────────────────────────────── -->
  <div class="wcard">
    <div class="country-bar">
      <div class="country-row">
        <div class="cs-field">
          <label>Страна отправления</label>
          <div class="cs-wrap" id="cs-sending">
            <div class="cs-selected">— не указана —<span class="cs-arr"></span></div>
            <div class="cs-dropdown">
              <input class="cs-search-inp" type="text" placeholder="Поиск страны...">
              <div class="cs-list"></div>
            </div>
            <input type="hidden" id="country-sending" value="">
          </div>
        </div>
        <div class="cs-field">
          <label>Страна происхождения</label>
          <div class="cs-wrap" id="cs-origin">
            <div class="cs-selected">— не указана —<span class="cs-arr"></span></div>
            <div class="cs-dropdown">
              <input class="cs-search-inp" type="text" placeholder="Поиск страны...">
              <div class="cs-list"></div>
            </div>
            <input type="hidden" id="country-origin" value="">
          </div>
        </div>
        <div class="cs-field">
          <label>Торгующая страна</label>
          <div class="cs-wrap" id="cs-trade">
            <div class="cs-selected">— не указана —<span class="cs-arr"></span></div>
            <div class="cs-dropdown">
              <input class="cs-search-inp" type="text" placeholder="Поиск страны...">
              <div class="cs-list"></div>
            </div>
            <input type="hidden" id="country-trade" value="">
          </div>
        </div>
      </div>
      <div id="country-note" style="display:none"></div>
    </div>
  </div>

  <!-- ── История расчётов ──────────────────────────────────────────────────── -->
  <div id="hist-panel">
    <div class="hist-hdr">
      <span class="hist-hdr-title">📋 История расчётов</span>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="hist-clear" onclick="clearHistory()">Очистить всё</button>
        <span class="hist-close" onclick="toggleHistory()">✕</span>
      </div>
    </div>
    <div id="hist-content"></div>
  </div>

  <!-- ── Ставки ─────────────────────────────────────────────────────────────── -->
  <div class="section" id="sec-rates">
    <div class="sec-hdr" onclick="toggleSec('sec-rates')">
      <span class="sec-title">Ставки</span><span class="sec-arr">▲</span>
    </div>
    <div class="sec-body">
      <table class="rates-tbl">
        <thead>
          <tr>
            <th>Вид таможенных платежей</th>
            <th style="text-align:center">Ставка</th>
            <th>Правовая основа</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="col-type">10: Таможенный сбор</td>
            <td class="col-rate" id="rt-sbor">—</td>
            <td class="col-law" id="rt-sbor-law">ПКМ №700 от 09.11.2020г</td>
          </tr>
          <tr>
            <td class="col-type">20: Таможенная пошлина</td>
            <td class="col-rate" id="rt-duty">—</td>
            <td class="col-law" id="rt-duty-law">—</td>
          </tr>
          <tr>
            <td class="col-type">27: Акцизный налог</td>
            <td class="col-rate" id="rt-aksiz-tbl">—</td>
            <td class="col-law" id="rt-aksiz-law">—</td>
          </tr>
          <tr>
            <td class="col-type">29: НДС</td>
            <td class="col-rate" id="rt-nds-tbl">—</td>
            <td class="col-law" id="rt-nds-law">Налоговый кодекс Узбекистана</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── Документы ─────────────────────────────────────────────────────────── -->
  <div class="section" id="sec-docs">
    <div class="sec-hdr" onclick="toggleSec('sec-docs')">
      <span class="sec-title">Документы</span><span class="sec-arr">▲</span>
    </div>
    <div class="sec-body">
      <div id="docs-loading" style="display:none;text-align:center;padding:12px;color:#888;font-size:13px">⏳ Загрузка документов...</div>
      <div id="docs-restrict" style="display:none;margin-bottom:10px"></div>
      <table class="docs-tbl">
        <thead>
          <tr>
            <th style="width:30%">Наименование организации</th>
            <th>Наименование документа</th>
          </tr>
        </thead>
        <tbody id="docs-tbody">
          <tr><td colspan="2" style="text-align:center;color:#999;font-style:italic">Выберите код ТН ВЭД для просмотра требуемых документов</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ── Калькулятор ────────────────────────────────────────────────────────── -->
  <div class="section" id="sec-calc">
    <div class="sec-hdr" onclick="toggleSec('sec-calc')">
      <span class="sec-title">Калькулятор</span><span class="sec-arr">▲</span>
    </div>
    <div class="sec-body">

      <!-- Row 1: стоимость -->
      <div class="calc-row">
        <div class="cf">
          <label>Общая стоимость товара</label>
          <input type="number" id="price" min="0" step="0.01" placeholder="0.00">
        </div>
        <div class="cf">
          <label>Валюта</label>
          <select id="price-cur" onchange="onCurChange()">
            <option value="USD">USD</option><option value="EUR">EUR</option>
            <option value="RUB">RUB</option><option value="UZS">UZS</option>
          </select>
        </div>
        <div class="cf">
          <label id="rate-cur-lbl">Курс (1 USD = сум)</label>
          <input type="number" id="rate-usd" value="12800" min="1">
        </div>
        <div class="cf">
          <label id="qty-main-lbl">Количество (кг / л / м²)</label>
          <input type="number" id="qty-main" min="0" step="any" placeholder="0">
        </div>
      </div>

      <!-- Row 2: транспорт -->
      <div class="calc-row">
        <div class="cf">
          <label>Транспортный расход</label>
          <input type="number" id="transport" min="0" step="0.01" placeholder="0.00">
        </div>
        <div class="cf">
          <label>Валюта</label>
          <select id="transport-cur">
            <option value="USD">USD</option><option value="EUR">EUR</option>
            <option value="RUB">RUB</option><option value="UZS">UZS</option>
          </select>
        </div>
        <div class="cf">
          <label>Количество (штук)</label>
          <input type="number" id="qty-pcs" min="0" step="1" value="1">
        </div>
        <div id="alc-wrap" class="cf">
          <label>Содержание алкоголя, %</label>
          <input type="number" id="alc-pct" min="0" max="100" step="0.1" placeholder="40">
        </div>
      </div>

      <!-- Скрытые поля для EUR/RUB (используются при расчёте) -->
      <div id="extra-rates" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:4px 0">
        <div class="cf">
          <label>1 EUR = сум</label>
          <input type="number" id="rate-eur" value="13900" min="1">
        </div>
        <div class="cf">
          <label>1 RUB = сум</label>
          <input type="number" id="rate-rub" value="140" min="1" step="0.01">
        </div>
        <div class="cf">
          <label>БРВ (с 01.08.2025)</label>
          <input type="number" id="brv" value="412000" min="1">
        </div>
      </div>

      <!-- Таможенный досмотр -->
      <div class="dosmotr-box">
        <div class="d-title">Расчёт платежей за таможенный досмотр:</div>
        <div class="dosmotr-grid">
          <div class="di">
            <label>Во время работы</label>
            <div style="display:flex;align-items:center;gap:6px">
              <input type="number" id="dosmotr-work" value="0" min="0">
              <span style="color:#888">⏱</span>
            </div>
          </div>
          <div class="di">
            <label>Вне времени работы</label>
            <div style="display:flex;align-items:center;gap:6px">
              <input type="number" id="dosmotr-off" value="0" min="0">
              <span style="color:#888">⏱</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Цены -->
      <div class="price3">
        <div class="pf">
          <label>Цена товара по бюллетенем</label>
          <input type="number" id="price-bulletin" value="0.0" min="0" step="0.01">
        </div>
        <div class="pf">
          <label>Цена товара по сделке</label>
          <input type="number" id="price-deal" value="0.0" min="0" step="0.01">
        </div>
        <div class="pf">
          <label>Предварительный таможенный стоимость</label>
          <input type="number" id="price-prelim" value="0.0" min="0" step="0.01">
        </div>
      </div>

      <!-- Шкала сбора -->
      <details>
        <summary>Шкала таможенного сбора (ПКМ №700)</summary>
        <table>
          <tr><th>Таможенная стоимость</th><th>Сбор</th><th>= сум (БРВ 412 000)</th></tr>
          <tr><td>до $200</td><td>0.5 БРВ</td><td>206 000</td></tr>
          <tr><td>$201 – $1 000</td><td>1 БРВ</td><td>412 000</td></tr>
          <tr><td>$1 001 – $5 000</td><td>2 БРВ</td><td>824 000</td></tr>
          <tr><td>$5 001 – $20 000</td><td>5 БРВ</td><td>2 060 000</td></tr>
          <tr><td>$20 001 – $75 000</td><td>10 БРВ</td><td>4 120 000</td></tr>
          <tr><td>$75 001 – $200 000</td><td>20 БРВ</td><td>8 240 000</td></tr>
          <tr><td>$200 001 – $600 000</td><td>40 БРВ</td><td>16 480 000</td></tr>
          <tr><td>свыше $600 000</td><td>75 БРВ</td><td>30 900 000</td></tr>
        </table>
      </details>

      <!-- Кнопки -->
      <div class="calc-footer">
        <button class="btn-compare" onclick="compareWithCustoms()">Сравнить с tarif.customs.uz ↗</button>
        <button class="btn-calc" onclick="calculate()">📊 РАССЧИТАТЬ</button>
      </div>

      <!-- Результаты -->
      <div id="result-area">
        <div class="compare-grid">
          <div class="compare-col col-ours">
            <div class="col-title">📊 Наш расчёт (ПП-181)</div>
            <div class="res-row"><span class="res-label">Тамож. стоимость</span><span class="res-val" id="r-cusval"></span></div>
            <div class="res-row"><span class="res-label">Тамож. сбор</span>
              <div><div class="res-val" id="r-sbor"></div><div class="res-note" id="r-sbor-note"></div></div></div>
            <div class="res-row"><span class="res-label">Пошлина</span>
              <div><div class="res-val" id="r-poshlina"></div><div class="res-note" id="r-poshlina-note"></div></div></div>
            <div class="res-row" id="row-aksiz-our" style="display:none"><span class="res-label">Акциз</span>
              <div><div class="res-val" id="r-aksiz"></div><div class="res-note" id="r-aksiz-note"></div></div></div>
            <div class="res-row"><span class="res-label">НДС</span>
              <div><div class="res-val" id="r-nds"></div><div class="res-note" id="r-nds-note"></div></div></div>
            <div class="res-total">
              <span class="res-total-lbl">ИТОГО</span>
              <span class="res-total-val" id="r-total"></span>
            </div>
            <div style="text-align:center;color:#888;font-size:12px;margin-top:4px" id="r-total-usd"></div>
          </div>
          <div class="compare-col col-customs">
            <div class="col-title">🏛 tarif.customs.uz</div>
            <div id="customs-not-loaded" style="color:#999;font-size:12px;padding:20px 0;text-align:center">
              Нажмите «Сравнить с tarif.customs.uz»
            </div>
            <div id="customs-result" style="display:none">
              <div class="res-row"><span class="res-label">Тамож. стоимость</span><span class="res-val" id="cz-cusval"></span></div>
              <div class="res-row"><span class="res-label">Тамож. сбор</span>
                <div><div class="res-val" id="cz-sbor"></div><div class="res-note" id="cz-sbor-note"></div></div></div>
              <div class="res-row"><span class="res-label">Пошлина</span>
                <div><div class="res-val" id="cz-poshlina"></div><div class="res-note" id="cz-poshlina-note"></div></div></div>
              <div class="res-row"><span class="res-label">НДС</span>
                <div><div class="res-val" id="cz-nds"></div><div class="res-note" id="cz-nds-note"></div></div></div>
              <div class="res-total">
                <span class="res-total-lbl">ИТОГО</span>
                <span class="res-total-val" id="cz-total"></span>
              </div>
              <div style="text-align:center;color:#888;font-size:12px;margin-top:4px" id="cz-law"></div>
            </div>
          </div>
        </div>
        <div id="diff-box" class="diff-box" style="display:none"></div>
        <div class="formula-box" id="formula-detail"></div>
        <div style="font-size:11px;color:#aaa;margin-top:10px;text-align:center">
          ⚠️ Расчёт ознакомительный. Актуальные ставки проверяйте в таможенных органах.
        </div>
      </div>
      <div id="placeholder">Найдите товар, заполните данные и нажмите «📊 РАССЧИТАТЬ»</div>

    </div><!-- /sec-body calc -->
  </div>

  <!-- ── Дополнительные расходы ─────────────────────────────────────────────── -->
  <div class="section" id="sec-extra">
    <div class="sec-hdr" onclick="toggleSec('sec-extra')">
      <span class="sec-title">Дополнительные расходы</span><span class="sec-arr">▲</span>
    </div>
    <div class="sec-body">
      <table class="docs-tbl">
        <thead>
          <tr>
            <th>№</th>
            <th>Наименование организации</th>
            <th>Наименование документа</th>
            <th>Наименование услуг</th>
            <th>Единица измерения</th>
            <th>Стоимость услуги</th>
          </tr>
        </thead>
        <tbody>
          <tr><td colspan="6">Информация не найдена</td></tr>
        </tbody>
      </table>
    </div>
  </div>


</div><!-- /main-wrap -->
<script>
// ─── Country searchable dropdowns ────────────────────────────────────────────
var COUNTRIES = COUNTRIES_JSON_PLACEHOLDER;

// ─── Collapsible sections ─────────────────────────────────────────────────────
function toggleSec(id){
  var el = document.getElementById(id);
  el.classList.toggle('collapsed');
}

// ─── Currency change → update rate label ──────────────────────────────────────
function onCurChange(){
  var cur = document.getElementById('price-cur').value;
  var lbl = document.getElementById('rate-cur-lbl');
  var inp = document.getElementById('rate-usd');
  if(cur==='USD'){ lbl.textContent='Курс (1 USD = сум)'; inp.value=lastRates.USD||12800; }
  else if(cur==='EUR'){ lbl.textContent='Курс (1 EUR = сум)'; inp.value=lastRates.EUR||13900; }
  else if(cur==='RUB'){ lbl.textContent='Курс (1 RUB = сум)'; inp.value=lastRates.RUB||140; }
  else if(cur==='UZS'){ lbl.textContent='Сумма в сумах'; inp.value=1; }
}
var lastRates = {};

// ─── doSearch (кнопка 🔍) ────────────────────────────────────────────────────
function doSearch(){
  var q = document.getElementById('search-inp').value.trim();
  if(!q) return;
  // If numeric — look up by code
  if(/^\d+/.test(q)){
    var code = q.split(/\s/)[0];
    document.getElementById('manual-code').value = code;
    lookupManual();
  } else {
    // Trigger autocomplete fetch and show results
    fetchAC(q);
    document.getElementById('ac-list').style.display='block';
  }
}

function initCountrySelect(wrapId, hiddenId, onChange){
  var wrap  = document.getElementById(wrapId);
  var sel   = wrap.querySelector('.cs-selected');
  var drop  = wrap.querySelector('.cs-dropdown');
  var inp   = wrap.querySelector('.cs-search-inp');
  var list  = wrap.querySelector('.cs-list');
  var hidden= document.getElementById(hiddenId);

  function renderList(filter){
    filter = (filter||'').toLowerCase();
    list.innerHTML = '';
    var added = 0;
    // Empty option
    if(!filter){
      var el = document.createElement('div');
      el.className = 'cs-item cs-none';
      el.textContent = '— не указана —';
      el.dataset.val = '';
      el.addEventListener('mousedown', function(e){e.preventDefault(); pick('','— не указана —');});
      list.appendChild(el);
    }
    COUNTRIES.forEach(function(c){
      if(filter && c.name.toLowerCase().indexOf(filter)===-1 &&
         c.code.indexOf(filter)===-1) return;
      var el = document.createElement('div');
      el.className = 'cs-item' + (c.code === hidden.value ? ' cs-active' : '');
      el.textContent = c.code + ' — ' + c.name;
      el.dataset.val = c.code;
      el.addEventListener('mousedown', function(e){e.preventDefault(); pick(c.code, c.code+' — '+c.name);});
      list.appendChild(el);
      added++;
    });
    if(added === 0){
      var el2 = document.createElement('div');
      el2.className = 'cs-no-results';
      el2.textContent = 'Страна не найдена';
      list.appendChild(el2);
    }
  }

  function pick(val, label){
    hidden.value = val;
    sel.textContent = label || '— не указана —';
    wrap.classList.remove('open');
    inp.value = '';
    if(onChange) onChange();
  }

  sel.addEventListener('click', function(){
    var isOpen = wrap.classList.toggle('open');
    if(isOpen){ renderList(''); inp.focus(); }
  });
  inp.addEventListener('input', function(){ renderList(this.value); });
  inp.addEventListener('keydown', function(e){
    if(e.key==='Escape'){ wrap.classList.remove('open'); inp.value=''; }
  });
  document.addEventListener('click', function(e){
    if(!wrap.contains(e.target)) wrap.classList.remove('open');
  });
  renderList('');
}

// Init all three selects after DOM ready
window.addEventListener('DOMContentLoaded', function(){
  initCountrySelect('cs-sending', 'country-sending', onCountryChange);
  initCountrySelect('cs-origin',  'country-origin',  onCountryChange);
  initCountrySelect('cs-trade',   'country-trade',   onCountryChange);
  // Перезагружать документы при смене режима (импорт/экспорт)
  document.querySelectorAll('input[name="direction"]').forEach(function(r){
    r.addEventListener('change', function(){
      if(selectedCode) loadDocs(selectedCode.code);
    });
  });
});

// ─── CBU Exchange rates ───────────────────────────────────────────────────────
function loadRates(){
  var btn=document.getElementById('rates-btn');
  btn.textContent='⏳';
  fetch('/api/rates')
    .then(r=>r.json())
    .then(function(d){
      if(!d.ok){btn.textContent='↻ Курс ЦБ';alert('Ошибка: '+d.error);return;}
      var r=d.rates;
      if(r.USD){var uv=Math.round(r.USD.rate);document.getElementById('rate-usd').value=uv;lastRates.USD=uv;onCurChange();}
      if(r.EUR){var ev=Math.round(r.EUR.rate);document.getElementById('rate-eur').value=ev;lastRates.EUR=ev;}
      if(r.RUB){var rv=parseFloat(r.RUB.rate.toFixed(2));document.getElementById('rate-rub').value=rv;lastRates.RUB=rv;}
      var dEl=document.getElementById('rates-date');
      var parts=[];
      if(r.USD) parts.push('USD '+Math.round(r.USD.rate).toLocaleString('ru-RU')+' ('+(r.USD.diff>0?'+':'')+r.USD.diff+')');
      if(r.EUR) parts.push('EUR '+Math.round(r.EUR.rate).toLocaleString('ru-RU'));
      if(r.RUB) parts.push('RUB '+r.RUB.rate);
      dEl.textContent='Курс ЦБ РУз на '+d.date+': '+parts.join(' · ');
      btn.textContent='↻ Курс ЦБ';
    })
    .catch(function(){btn.textContent='↻ Курс ЦБ';});
}
// Auto-load on start
window.addEventListener('load', function(){ loadRates(); });

// ─── State ───────────────────────────────────────────────────────────────────
var selectedCode = null;
var customsData  = null;
var lastCalc     = null;   // last calculated values for comparison render

// ─── CIS countries (0% duty) ─────────────────────────────────────────────────
var CIS = {'643':1,'112':1,'398':1,'417':1,'762':1,'031':1,'051':1,'498':1,'804':1,'795':1};
// 643=Россия 112=Беларусь 398=Казахстан 417=Кыргызстан 762=Таджикистан
// 031=Азербайджан 051=Армения 498=Молдова 804=Украина 795=Туркмения

// ─── Helpers ─────────────────────────────────────────────────────────────────
function fmtUzs(n){
  if(n===null||n===undefined) return '—';
  return Math.round(n).toLocaleString('ru-RU') + ' сум';
}
function toUzs(amount, cur){
  var r={USD:+document.getElementById('rate-usd').value||12800,
         EUR:+document.getElementById('rate-eur').value||13900,
         RUB:+document.getElementById('rate-rub').value||140,UZS:1};
  return amount*(r[cur]||1);
}
function sborBrv(usd){
  var s=[[200,.5],[1000,1],[5000,2],[20000,5],[75000,10],[200000,20],[600000,40],[Infinity,75]];
  for(var i=0;i<s.length;i++) if(usd<=s[i][0]) return s[i][1];
  return 75;
}
function getOrigin(){return document.getElementById('country-origin').value;}
function isCis(code){return !!CIS[code];}
function effectiveDutyPct(){
  if(!selectedCode) return 0;
  if(isCis(getOrigin())) return 0;
  return selectedCode.poshlina_pct || 0;
}

function clearSearch(){
  var inp=document.getElementById('search-inp');
  inp.value='';
  document.getElementById('search-clear').style.display='none';
  hideAC();
  inp.focus();
}

// ─── Autocomplete ─────────────────────────────────────────────────────────────
var acTimer=null;
document.getElementById('search-inp').addEventListener('input',function(){
  document.getElementById('search-clear').style.display=this.value?'block':'none';
  clearTimeout(acTimer);
  var q=this.value.trim();
  if(q.length<2){hideAC();return;}
  acTimer=setTimeout(function(){fetchAC(q);},250);
});
document.getElementById('search-inp').addEventListener('blur',function(){setTimeout(hideAC,200);});

function fetchAC(q){
  fetch('/api/search?q='+encodeURIComponent(q))
    .then(r=>r.json()).then(function(data){
      var box=document.getElementById('ac-list');
      box.innerHTML='';
      if(!data.length){hideAC();return;}
      data.forEach(function(item){
        var d=document.createElement('div');
        d.innerHTML='<span class="ac-code">'+item.code+'</span>'+(item.name_ru||'').substring(0,80);
        d.addEventListener('mousedown',function(){selectCode(item);});
        box.appendChild(d);
      });
      box.style.display='block';
    });
}
function hideAC(){document.getElementById('ac-list').style.display='none';}

function selectCode(item){
  document.getElementById('search-inp').value=item.code+' — '+(item.name_ru||'').substring(0,50);
  document.getElementById('search-clear').style.display='block';
  document.getElementById('manual-code').value=item.code;
  hideAC();
  if(selectedCode && selectedCode.code === item.code) return;
  fetch('/api/lookup?code='+encodeURIComponent(item.code))
    .then(r=>r.json()).then(applyCodeInfo);
}

document.getElementById('search-inp').addEventListener('keydown',function(e){
  if(e.key==='Enter'){e.preventDefault();lookupManual();}
});

function lookupManual(){
  var q=document.getElementById('manual-code').value.trim();
  if(!q) q=document.getElementById('search-inp').value.trim().split(' ')[0];
  if(!q) return;
  // Не тратим токен если этот код уже загружен
  if(selectedCode && selectedCode.code === q) return;
  fetch('/api/lookup?code='+encodeURIComponent(q))
    .then(r=>r.json()).then(applyCodeInfo);
}

// ─── Apply code info ──────────────────────────────────────────────────────────
var UNIT_LBL={kg:'кг',liter:'л',liter_alc:'л спирта',m2:'м²',item:'шт.',pair:'пар',cc:'куб.см',per1000:'тыс.шт.'};
var AKSIZ_LBL={per1000:'тыс.шт.',liter:'л',liter_alc:'л спирта',kg:'кг',ml:'мл',item:'шт.'};

var _toastTimer=null;
function showToast(msg,ms){
  var t=document.getElementById('toast');
  t.innerHTML=msg;t.style.display='block';
  clearTimeout(_toastTimer);
  _toastTimer=setTimeout(function(){t.style.display='none';},ms||5000);
}

function applyCodeInfo(data){
  var errEl=document.getElementById('code-error');
  if(!data||data.error){
    if(data&&data.error==='no_tokens'){
      showToast('🚫 У вас закончились запросы.<br>Пополните баланс для продолжения.',6000);
      document.getElementById('code-panel').style.display='none';
    } else {
      errEl.style.display='block';
    }
    selectedCode=null;document.getElementById('code-panel').style.display='none';return;
  }
  errEl.style.display='none';
  selectedCode=data;
  customsData=null;

  document.getElementById('cp-code').textContent=data.code;
  document.getElementById('cp-name').textContent=(data.name_ru||'').substring(0,160);
  document.getElementById('manual-code').value=data.code;

  // Tags
  var tags=document.getElementById('cp-tags');
  tags.innerHTML='';
  var pct=data.poshlina_pct;
  var usd=data.poshlina_usd_per_unit;
  var pu=data.poshlina_unit;
  var rateStr=pct+'%';
  if(usd&&pu){rateStr+=(pu==='cc'?' + $'+usd+'/'+UNIT_LBL[pu]:', мин $'+usd+'/'+(UNIT_LBL[pu]||pu));}
  addTag(tags, 'Пошлина МФН: '+rateStr, pct===0&&!usd?'tag-green':'tag-red');
  addTag(tags, 'НДС: '+(data.nds_pct||12)+'%', 'tag-blue');
  if(data.aksiz_uzs_per_unit){
    var au=AKSIZ_LBL[data.aksiz_unit]||data.aksiz_unit;
    addTag(tags,'Акциз: '+data.aksiz_uzs_per_unit.toLocaleString('ru-RU')+' сум/'+au,'tag-orange');
  }
  addTag(tags,'Ед.: '+(data.unit1||'—'),'tag-gray');

  // Rate info table
  document.getElementById('ri-mfn').textContent=rateStr;
  document.getElementById('ri-nds').textContent=(data.nds_pct||12)+'%';
  var aksizRow=document.getElementById('ri-aksiz-row');
  if(data.aksiz_uzs_per_unit){
    var au2=AKSIZ_LBL[data.aksiz_unit]||data.aksiz_unit;
    document.getElementById('ri-aksiz').textContent=data.aksiz_uzs_per_unit.toLocaleString('ru-RU')+' сум/'+au2;
    aksizRow.style.display='';
  } else {aksizRow.style.display='none';}
  document.getElementById('ri-unit').textContent=(data.unit1||'—')+(data.unit2?' / '+data.unit2:'');

  // Formula
  var f='';
  f+='Тамож. стоимость = цена_товара + транспорт\n';
  f+='Тамож. сбор = X БРВ (по шкале ПКМ №700)\n';
  if(isCis(getOrigin())){
    f+='Пошлина = 0 (ЗСТ СНГ)\n';
  } else if(usd&&pu&&pu!=='cc'){
    f+='Пошлина = max(тамст × '+pct+'%, $'+usd+' × кол-во_'+UNIT_LBL[pu]+')\n';
  } else if(usd&&pu==='cc'){
    f+='Пошлина = тамст × '+pct+'% + $'+usd+'/куб.см × объём_двиг\n';
  } else {
    f+='Пошлина = тамст × '+pct+'%\n';
  }
  if(data.aksiz_uzs_per_unit&&data.aksiz_unit==='per1000'){
    f+='Акциз = '+data.aksiz_uzs_per_unit.toLocaleString('ru-RU')+' × кол-во/1000\n';
  } else if(data.aksiz_uzs_per_unit&&data.aksiz_unit==='liter'){
    f+='Акциз = '+data.aksiz_uzs_per_unit.toLocaleString('ru-RU')+' сум × кол-во_л\n';
  } else if(data.aksiz_uzs_per_unit&&data.aksiz_unit==='liter_alc'){
    f+='Акциз = '+data.aksiz_uzs_per_unit.toLocaleString('ru-RU')+' сум × кол-во_л × крепость%\n';
  }
  f+='НДС = (тамст + пошлина + акциз) × '+(data.nds_pct||12)+'%\n';
  f+='ИТОГО = сбор + пошлина + акциз + НДС';
  document.getElementById('ri-formula').textContent=f;

  // Show alc field
  var alcWrap=document.getElementById('alc-wrap');
  alcWrap.style.display=(data.aksiz_unit==='liter_alc')?'block':'none';

  // qty main label
  var ql=document.getElementById('qty-main-lbl');
  var pu2=data.poshlina_unit||data.aksiz_unit;
  var QL={kg:'Масса (кг)',liter:'Объём (литров)',liter_alc:'Объём (литров)',m2:'Площадь (м²)',cc:'Объём двигателя (куб.см)'};
  ql.textContent=QL[pu2]||'Количество (осн. единица: кг / л / м²)';

  document.getElementById('code-panel').style.display='block';
  document.getElementById('rate-info').style.display='block';
  onCountryChange();
  // Предварительно заполним таблицу ставок (без сумм)
  updateRatesTable(0, 0, 0, 0);
  // Загрузить документы для выбранного кода
  loadDocs(data.code);
}

function addTag(container, text, cls){
  var s=document.createElement('span');
  s.className='tag '+cls;
  s.textContent=text;
  container.appendChild(s);
}

// ─── Country change ───────────────────────────────────────────────────────────
function onCountryChange(){
  var origin=getOrigin();
  var cisBadge=document.getElementById('cis-badge');
  var noteEl=document.getElementById('country-note');
  if(isCis(origin)){
    cisBadge.style.display='inline-block';
    noteEl.textContent='✅ Страна происхождения входит в СНГ ЗСТ. Ставка таможенной пошлины = 0%.';
    noteEl.style.display='block';
  } else if(origin){
    cisBadge.style.display='none';
    noteEl.textContent='ℹ️ Применяется стандартная ставка МФН по ПП-181.';
    noteEl.style.display='block';
  } else {
    cisBadge.style.display='none';
    noteEl.style.display='none';
  }
  if(selectedCode){
    var effPct=isCis(origin)?0:(selectedCode.poshlina_pct||0);
    document.getElementById('ri-applied').textContent=
      isCis(origin)?'0% (ЗСТ СНГ)':(effPct+'%'+(selectedCode.poshlina_usd_per_unit?', + мин':''));
  }
  customsData=null;
  document.getElementById('customs-result').style.display='none';
  document.getElementById('customs-not-loaded').style.display='block';
  // Обновить ограничения по стране
  if(selectedCode) renderDocsRestrictions(lastDocsData, getOrigin());
}

// ─── Документы (разрешительные) ──────────────────────────────────────────────
var lastDocsData = null;

function getDirection(){ return document.getElementById('dir-export').checked ? 'export' : 'import'; }

function loadDocs(code){
  if(!code) return;
  var tbody = document.getElementById('docs-tbody');
  var loading = document.getElementById('docs-loading');
  tbody.innerHTML = '';
  loading.style.display = 'block';
  document.getElementById('docs-restrict').style.display = 'none';
  var dir = getDirection();
  fetch('/api/docs?code=' + encodeURIComponent(code) + '&rejim=' + dir)
    .then(function(r){ return r.json(); })
    .then(function(d){
      loading.style.display = 'none';
      lastDocsData = d;
      // Заполнить таблицу документов
      if(!d.docs || d.docs.length === 0){
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#999;font-style:italic">Нет обязательных разрешительных документов</td></tr>';
      } else {
        var html = '';
        d.docs.forEach(function(doc){
          var orgCell = doc.url
            ? '<a href="' + doc.url + '" target="_blank" rel="noopener" class="doc-org-link">' + esc(doc.org) + ' ↗</a>'
            : esc(doc.org);
          html += '<tr><td class="doc-org">' + orgCell + '</td><td class="doc-name">' + esc(doc.doc) + '</td></tr>';
        });
        tbody.innerHTML = html;
      }
      renderDocsRestrictions(d, getOrigin());
    })
    .catch(function(){
      loading.style.display = 'none';
      tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#c00">Ошибка загрузки</td></tr>';
    });
}

function renderDocsRestrictions(d, originCode){
  var el = document.getElementById('docs-restrict');
  if(!d || !d.restrictions || d.restrictions.length === 0){ el.style.display='none'; return; }
  var html = '<div class="doc-restrict-block"><div class="restrict-title">⚠️ Нетарифные ограничения / запреты</div>';
  d.restrictions.forEach(function(r){
    var relevant = !originCode || !r.condition ||
        r.condition.indexOf(getCountryName(originCode)) !== -1 ||
        r.condition.indexOf('всеми') !== -1 || r.condition.indexOf('Запрет') === 0;
    if(relevant || true) {
      html += '<div class="doc-restrict-item"><b>' + esc(r.descr) + '</b>';
      if(r.condition) html += ' — ' + esc(r.condition);
      if(r.legal) html += ' <span style="color:#888">(' + esc(r.legal) + ')</span>';
      html += '</div>';
    }
  });
  html += '</div>';
  el.innerHTML = html;
  el.style.display = 'block';
}

function getCountryName(code){
  for(var i=0;i<COUNTRIES.length;i++){
    if(COUNTRIES[i].code===code) return COUNTRIES[i].name;
  }
  return '';
}

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ─── Calculate (our method) ───────────────────────────────────────────────────
function _updateTokenBadge(tokens){
  var el=document.querySelector('.tok-badge');
  if(!el) return;
  if(tokens===null||tokens===undefined){el.textContent='∞ запросов';el.classList.remove('tok-low');return;}
  var w=tokens===1?'запрос':tokens%10>=2&&tokens%10<=4&&(tokens%100<10||tokens%100>=20)?'запроса':'запросов';
  el.textContent='🔢 '+tokens+' '+w;
  el.classList.toggle('tok-low', tokens<=5);
}

function calculate(){
  if(!selectedCode){alert('Выберите код ТН ВЭД');return;}
  fetch('/api/calc_token',{method:'POST'}).then(r=>r.json()).then(function(d){
    if(d&&d.error==='no_tokens'){showToast('🚫 У вас закончились запросы.<br>Пополните баланс для продолжения.',6000);return;}
    _updateTokenBadge(d.tokens);
    _doCalc();
  });
}
function _doCalc(){
  var price   =+document.getElementById('price').value||0;
  var priceCur=document.getElementById('price-cur').value;
  var trans   =+document.getElementById('transport').value||0;
  var transCur=document.getElementById('transport-cur').value;
  var qtyMain =+document.getElementById('qty-main').value||0;
  var qtyPcs  =+document.getElementById('qty-pcs').value||1;
  var brv     =+document.getElementById('brv').value||412000;
  var rateUsd =+document.getElementById('rate-usd').value||12800;

  var priceUzs=toUzs(price,priceCur);
  var transUzs=toUzs(trans,transCur);
  var cusval  =priceUzs+transUzs;
  var cusvalUsd=cusval/rateUsd;

  // 1. Sbor
  var sborBrvN=sborBrv(cusvalUsd);
  var sborUzs =sborBrvN*brv;

  // 2. Poshlina
  var origin=getOrigin();
  var cis=isCis(origin);
  var poshlinaUzs=0, poshlinaNote='';
  var poshlPct=cis?0:(selectedCode.poshlina_pct||0);
  var poshlUsd=selectedCode.poshlina_usd_per_unit;
  var poshlUnit=selectedCode.poshlina_unit;

  if(cis){
    poshlinaNote='0% (ЗСТ СНГ)';
  } else {
    if(poshlPct!==null){
      poshlinaUzs=cusval*poshlPct/100;
      poshlinaNote=poshlPct+'% от тамст';
    }
    if(poshlUsd&&poshlUnit&&poshlUnit!=='cc'){
      var qty;
      if(poshlUnit==='kg'||poshlUnit==='liter'||poshlUnit==='m2') qty=qtyMain;
      else if(poshlUnit==='per1000') qty=qtyPcs/1000;
      else qty=qtyPcs;
      var byUsd=poshlUsd*qty*rateUsd;
      var ul=UNIT_LBL[poshlUnit]||poshlUnit;
      if(byUsd>poshlinaUzs){poshlinaUzs=byUsd;poshlinaNote='$'+poshlUsd+'×'+qty+' '+ul;}
      else poshlinaNote+=' (мин $'+poshlUsd+'/'+ul+')';
    } else if(poshlUsd&&poshlUnit==='cc'){
      var engCC=qtyMain||0;
      if(engCC>0){poshlinaUzs+=poshlUsd*engCC*rateUsd;poshlinaNote+=' + $'+poshlUsd+'/куб.см×'+engCC;}
      else poshlinaNote+=' + $'+poshlUsd+'/куб.см (укажите объём двигателя)';
    }
  }

  // 3. Aksiz
  var aksizUzs=0, aksizNote='';
  var aksizPer=selectedCode.aksiz_uzs_per_unit;
  var aksizUnit=selectedCode.aksiz_unit;
  if(aksizPer&&aksizUnit){
    var aQty;
    if(aksizUnit==='per1000') aQty=qtyPcs/1000;
    else if(aksizUnit==='liter') aQty=qtyMain;
    else if(aksizUnit==='liter_alc'){var alc=+document.getElementById('alc-pct').value||0;aQty=qtyMain*alc/100;}
    else if(aksizUnit==='kg') aQty=qtyMain;
    else if(aksizUnit==='ml') aQty=qtyMain;
    else aQty=qtyPcs;
    aksizUzs=aksizPer*aQty;
    aksizNote=aksizPer.toLocaleString('ru-RU')+' сум × '+aQty.toFixed(3)+' '+(AKSIZ_LBL[aksizUnit]||aksizUnit);
  } else if(selectedCode.aksiz_pct){
    aksizUzs=(cusval+poshlinaUzs)*selectedCode.aksiz_pct/100;
    aksizNote=selectedCode.aksiz_pct+'% от (тамст+пошлина)';
  }

  // 4. NDS
  var ndsPct=selectedCode.nds_pct||12;
  var ndsBase=cusval+poshlinaUzs+aksizUzs;
  var ndsUzs=ndsBase*ndsPct/100;
  var ndsNote=ndsPct+'% от (тамст '+fmtUzs(cusval)+' + пошлина + акциз)';

  var total=sborUzs+poshlinaUzs+aksizUzs+ndsUzs;
  var totalUsd=total/rateUsd;

  lastCalc={cusval,cusvalUsd,sborUzs,sborBrvN,poshlinaUzs,poshlinaNote,aksizUzs,aksizNote,ndsUzs,ndsNote,total,totalUsd,brv,rateUsd,ndsPct,poshlPct};

  renderOurResult(lastCalc);

  // Formulas detail
  var fd='';
  fd+='1. Тамст = '+price.toFixed(2)+' '+priceCur;
  if(trans>0) fd+=' + '+trans.toFixed(2)+' '+transCur;
  fd+=' = '+fmtUzs(cusval)+'\n';
  fd+='   (по курсу: 1 USD = '+rateUsd.toLocaleString('ru-RU')+' сум)\n';
  fd+='\n2. Тамож. сбор = '+sborBrvN+' БРВ × '+brv.toLocaleString('ru-RU')+' = '+fmtUzs(sborUzs)+'\n';
  fd+='   (тамст $'+cusvalUsd.toFixed(2)+')\n';
  fd+='\n3. Пошлина → '+poshlinaNote+' = '+fmtUzs(poshlinaUzs)+'\n';
  if(aksizUzs>0) fd+='\n4. Акциз → '+aksizNote+' = '+fmtUzs(aksizUzs)+'\n';
  fd+='\n'+(aksizUzs>0?'5':'4')+'. НДС '+ndsPct+'% × ('+fmtUzs(cusval)+' + '+fmtUzs(poshlinaUzs)+' + '+fmtUzs(aksizUzs)+')\n';
  fd+='   = '+ndsPct+'% × '+fmtUzs(ndsBase)+' = '+fmtUzs(ndsUzs)+'\n';
  fd+='\nИТОГО = '+fmtUzs(sborUzs)+' + '+fmtUzs(poshlinaUzs);
  if(aksizUzs>0) fd+=' + '+fmtUzs(aksizUzs);
  fd+=' + '+fmtUzs(ndsUzs)+'\n      = '+fmtUzs(total);
  document.getElementById('formula-detail').textContent=fd;

  document.getElementById('placeholder').style.display='none';
  document.getElementById('result-area').style.display='block';
  document.getElementById('diff-box').style.display='none';
  document.getElementById('formula-detail').style.display='block';
  updateRatesTable(sborUzs, poshlinaUzs, aksizUzs, ndsUzs);
}

function updateRatesTable(sborUzs, poshlinaUzs, aksizUzs, ndsUzs){
  if(!selectedCode) return;
  var pct = isCis(getOrigin()) ? 0 : (selectedCode.poshlina_pct||0);
  var law = isCis(getOrigin()) ? 'ЗСТ СНГ — 0%' : 'ПП-181 от 14.05.2025';
  document.getElementById('rt-sbor').textContent = sborUzs ? fmtUzs(sborUzs) : '—';
  document.getElementById('rt-duty').textContent = pct+'%'+(poshlinaUzs?' ('+fmtUzs(poshlinaUzs)+')':'');
  document.getElementById('rt-duty-law').textContent = law;
  if(selectedCode.aksiz_uzs_per_unit){
    var au = {per1000:'340 000 сум/тыс.шт',liter:'сум/л',liter_alc:'сум/л спирта',item:'сум/шт'}[selectedCode.aksiz_unit]||'';
    document.getElementById('rt-aksiz-tbl').textContent = selectedCode.aksiz_uzs_per_unit.toLocaleString('ru-RU')+' '+au;
    document.getElementById('rt-aksiz-law').textContent = 'НК РУз, ст. 289';
  } else {
    document.getElementById('rt-aksiz-tbl').textContent = '—';
    document.getElementById('rt-aksiz-law').textContent = '—';
  }
  document.getElementById('rt-nds-tbl').textContent = (selectedCode.nds_pct||12)+'%'+(ndsUzs?' ('+fmtUzs(ndsUzs)+')':'');
}

function renderOurResult(c){
  var brv=c.brv, rateUsd=c.rateUsd;
  document.getElementById('r-cusval').textContent=fmtUzs(c.cusval);
  document.getElementById('r-sbor').textContent=fmtUzs(c.sborUzs);
  document.getElementById('r-sbor-note').textContent=c.sborBrvN+' БРВ × '+brv.toLocaleString('ru-RU');
  document.getElementById('r-poshlina').textContent=fmtUzs(c.poshlinaUzs);
  document.getElementById('r-poshlina-note').textContent=c.poshlinaNote;
  document.getElementById('r-nds').textContent=fmtUzs(c.ndsUzs);
  document.getElementById('r-nds-note').textContent=c.ndsNote;
  document.getElementById('r-total').textContent=fmtUzs(c.total);
  document.getElementById('r-total-usd').textContent='≈ '+Math.round(c.totalUsd).toLocaleString('ru-RU')+' USD';
  var aksizRow=document.getElementById('row-aksiz-our');
  if(c.aksizUzs>0){
    document.getElementById('r-aksiz').textContent=fmtUzs(c.aksizUzs);
    document.getElementById('r-aksiz-note').textContent=c.aksizNote;
    aksizRow.style.display='';
  } else aksizRow.style.display='none';
}

// ─── Compare with customs.uz ──────────────────────────────────────────────────
function compareWithCustoms(){
  if(!selectedCode){alert('Выберите код ТН ВЭД');return;}
  if(!lastCalc) calculate();
  document.getElementById('loading').style.display='block';
  var origin =document.getElementById('country-origin').value;
  var sending=document.getElementById('country-sending').value;
  var trade  =document.getElementById('country-trade').value;
  fetch('/api/customs_check?code='+encodeURIComponent(selectedCode.code)
       +'&origin='+encodeURIComponent(origin)
       +'&sending='+encodeURIComponent(sending)
       +'&trade='+encodeURIComponent(trade))
    .then(r=>r.json())
    .then(function(cz){
      document.getElementById('loading').style.display='none';
      if(!cz.ok){
        document.getElementById('diff-box').textContent='Ошибка customs.uz: '+cz.error;
        document.getElementById('diff-box').style.display='block';
        return;
      }
      renderCustomsResult(cz);
    })
    .catch(function(e){
      document.getElementById('loading').style.display='none';
      document.getElementById('diff-box').textContent='Ошибка сети: '+e;
      document.getElementById('diff-box').style.display='block';
    });
}

function renderCustomsResult(cz){
  if(!lastCalc) return;
  var c=lastCalc;
  var czDutyPct=cz.duty_pct!==null?cz.duty_pct:0;
  var czPoshlina=c.cusval*czDutyPct/100;
  var czNdsPct=cz.nds_pct||12;
  var czNds=(c.cusval+czPoshlina)*czNdsPct/100;
  var czTotal=c.sborUzs+czPoshlina+czNds;

  document.getElementById('cz-cusval').textContent=fmtUzs(c.cusval);
  document.getElementById('cz-sbor').textContent=fmtUzs(c.sborUzs);
  document.getElementById('cz-sbor-note').textContent=c.sborBrvN+' БРВ (одинаково)';
  document.getElementById('cz-poshlina').textContent=fmtUzs(czPoshlina);
  document.getElementById('cz-poshlina-note').textContent=
    (czDutyPct===0)?'0% (нет/льгота)':(czDutyPct+'%'+(cz.law_duty?' · '+cz.law_duty:''));
  document.getElementById('cz-nds').textContent=fmtUzs(czNds);
  document.getElementById('cz-nds-note').textContent=czNdsPct+'% от (тамст+пошлина)'+(cz.law_nds?' · '+cz.law_nds:'');
  document.getElementById('cz-total').textContent=fmtUzs(czTotal);
  document.getElementById('cz-law').textContent=cz.law_duty||'';
  document.getElementById('customs-not-loaded').style.display='none';
  document.getElementById('customs-result').style.display='block';

  // Diff
  var diff=c.total-czTotal;
  var pct=czTotal>0?Math.round(diff/czTotal*100):0;
  var diffEl=document.getElementById('diff-box');
  if(Math.abs(diff)<1000){
    diffEl.className='diff-box diff-ok';
    diffEl.textContent='✅ Расчёты совпадают (разница менее 1 000 сум)';
  } else {
    diffEl.className='diff-box';
    var why='';
    if(czDutyPct!==null&&czDutyPct>0&&c.poshlPct!==null&&Math.abs(czDutyPct-c.poshlPct)>0.5){
      why+=' Ставка customs.uz ('+czDutyPct+'%) ≠ ставка ПП-181 ('+c.poshlPct+'%).';
      if(czDutyPct>c.poshlPct) why+=' customs.uz использует старый ПП-4470 (2019).';
    }
    diffEl.textContent='⚠️ Разница: '+fmtUzs(Math.abs(diff))+' ('+Math.abs(pct)+'%).'+why;
  }
  diffEl.style.display='block';
}

// ─── История расчётов ─────────────────────────────────────────────────────────
var HIST_KEY = 'tnved_history';

function getHistory(){ try{return JSON.parse(localStorage.getItem(HIST_KEY)||'[]');}catch(e){return[];} }
function setHistory(arr){ localStorage.setItem(HIST_KEY, JSON.stringify(arr)); }

function saveHistory(){
  if(!lastCalc || !selectedCode){alert('Сначала выполните расчёт');return;}
  var c = lastCalc;
  var origin  = document.getElementById('country-origin').value;
  var sending = document.getElementById('country-sending').value;
  var countryName = '';
  if(origin){
    var found = COUNTRIES.filter(function(x){return x.code===origin;});
    if(found.length) countryName = found[0].name;
  }
  var entry = {
    ts:       Date.now(),
    date:     new Date().toLocaleString('ru-RU'),
    code:     selectedCode.code,
    name:     (selectedCode.name_ru||'').substring(0,60),
    country:  countryName || (sending ? sending : '—'),
    cusval:   c.cusval,
    total:    c.total,
    rateUsd:  c.rateUsd,
    poshlPct: c.poshlPct,
    totalUsd: c.totalUsd
  };
  var arr = getHistory();
  arr.unshift(entry);
  if(arr.length > 50) arr = arr.slice(0,50);
  setHistory(arr);
  var btn = document.querySelector('.btn-save');
  var orig = btn.textContent;
  btn.textContent = '✅ Сохранено!';
  setTimeout(function(){ btn.textContent = orig; }, 1500);
  // Обновить панель если открыта
  if(document.getElementById('hist-panel').style.display !== 'none') renderHistory();
}

function toggleHistory(){
  var panel = document.getElementById('hist-panel');
  var isOpen = panel.style.display !== 'none';
  if(isOpen){ panel.style.display = 'none'; }
  else { panel.style.display = 'block'; renderHistory(); }
}

function clearHistory(){
  if(!confirm('Очистить всю историю расчётов?')) return;
  setHistory([]);
  renderHistory();
}

function renderHistory(){
  var arr = getHistory();
  var el = document.getElementById('hist-content');
  if(!arr.length){
    el.innerHTML = '<div class="hist-empty">История пуста. Выполните расчёт и нажмите «💾 Сохранить».</div>';
    return;
  }
  var html = '<table class="hist-table"><thead><tr>'
    +'<th>#</th><th>Дата</th><th>Код ТН ВЭД</th><th>Наименование</th>'
    +'<th>Страна</th><th>Там. стоимость</th><th>Пошлина</th><th>ИТОГО</th><th></th>'
    +'</tr></thead><tbody>';
  arr.forEach(function(e, i){
    html += '<tr>'
      +'<td style="color:#aaa">'+(arr.length-i)+'</td>'
      +'<td style="white-space:nowrap;color:#888">'+e.date+'</td>'
      +'<td class="mono">'+e.code+'</td>'
      +'<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+e.name+'">'+e.name+'</td>'
      +'<td>'+e.country+'</td>'
      +'<td class="mono">'+Math.round(e.cusval).toLocaleString('ru-RU')+' сум</td>'
      +'<td style="color:#0f3460;font-weight:700">'+(e.poshlPct||0)+'%</td>'
      +'<td class="mono" style="color:#0f3460;font-weight:800">'+Math.round(e.total).toLocaleString('ru-RU')+' сум'
        +'<div style="color:#aaa;font-size:10px;font-weight:400">≈'+Math.round(e.totalUsd).toLocaleString('ru-RU')+' USD</div></td>'
      +'<td><span class="hist-del" onclick="deleteHistory('+i+')" title="Удалить">✕</span></td>'
      +'</tr>';
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

function deleteHistory(idx){
  var arr = getHistory();
  arr.splice(idx, 1);
  setHistory(arr);
  renderHistory();
}

// ─── Tree Navigation (Вариант 10) ────────────────────────────────────────────
var TNVED_SECS=[
  {n:'I',r:'01-05',t:'Живые животные; продукты животного происхождения'},
  {n:'II',r:'06-14',t:'Продукты растительного происхождения'},
  {n:'III',r:'15-15',t:'Жиры и масла'},
  {n:'IV',r:'16-24',t:'Готовые пищевые продукты'},
  {n:'V',r:'25-27',t:'Минеральные продукты'},
  {n:'VI',r:'28-38',t:'Продукция химической промышленности'},
  {n:'VII',r:'39-40',t:'Пластмассы и каучук'},
  {n:'VIII',r:'41-43',t:'Кожевенное сырьё; меха'},
  {n:'IX',r:'44-46',t:'Древесина и изделия'},
  {n:'X',r:'47-49',t:'Бумага и картон'},
  {n:'XI',r:'50-63',t:'Текстиль и текстильные изделия'},
  {n:'XII',r:'64-67',t:'Обувь, головные уборы, зонты'},
  {n:'XIII',r:'68-70',t:'Камень, керамика, стекло'},
  {n:'XIV',r:'71-71',t:'Жемчуг, драгоценные металлы'},
  {n:'XV',r:'72-83',t:'Металлы и изделия из них'},
  {n:'XVI',r:'84-85',t:'Машины и электрооборудование'},
  {n:'XVII',r:'86-89',t:'Транспортные средства'},
  {n:'XVIII',r:'90-92',t:'Приборы; часы; инструменты'},
  {n:'XIX',r:'93-93',t:'Оружие и боеприпасы'},
  {n:'XX',r:'94-96',t:'Разные промышленные товары'},
  {n:'XXI',r:'97-97',t:'Произведения искусства; антиквариат'},
];
var treeInited=false, treeStack=[], _treeAllGroups=null;
var _treeGroups=[], _treePositions=[], _treeCodes=[];

function openTreeSection(){
  toggleSec('sec-tree');
  if(!treeInited&&!document.getElementById('sec-tree').classList.contains('collapsed')) treeInit();
}
function treeInit(){
  treeInited=true;
  treeStack=[];
  _showTreeSections();
}
function _showTreeSections(){
  renderTreeBc();
  var h='<div class="tree-sections">';
  TNVED_SECS.forEach(function(s,i){
    h+='<div class="tree-sec-card" onclick="treeClickSec('+i+')">'
      +'<div class="tree-sec-num">Раздел '+s.n+'</div>'
      +'<div class="tree-sec-name">'+s.t+'</div>'
      +'<div class="tree-sec-range">Гр. '+s.r+'</div></div>';
  });
  document.getElementById('tree-content').innerHTML=h+'</div>';
}
function treeClickSec(i){
  var s=TNVED_SECS[i];
  treeStack=[{type:'section',label:'Раздел '+s.n,sec:s}];
  renderTreeBc();
  document.getElementById('tree-content').innerHTML='<div class="tree-load">⏳ Загрузка...</div>';
  function doRender(groups){
    var lo=parseInt(s.r.split('-')[0]),hi=parseInt(s.r.split('-')[1]);
    _treeGroups=groups.filter(function(g){var n=parseInt(g.prefix);return n>=lo&&n<=hi;});
    _showTreeGroups();
  }
  if(_treeAllGroups){doRender(_treeAllGroups);}
  else{fetch('/api/tree?prefix=').then(r=>r.json()).then(function(g){_treeAllGroups=g;doRender(g);});}
}
function _showTreeGroups(){
  var h='<div class="tree-groups">';
  _treeGroups.forEach(function(g,i){
    h+='<button class="tree-grp-btn" onclick="treeClickGrp('+i+')">'+g.prefix
      +' <span style="color:#aaa;font-weight:400;font-size:10px">('+g.count+')</span></button>';
  });
  document.getElementById('tree-content').innerHTML=h+'</div>';
}
function treeClickGrp(i){
  var g=_treeGroups[i];
  treeStack.push({type:'group',label:'Группа '+g.prefix,grp:g});
  renderTreeBc();
  document.getElementById('tree-content').innerHTML='<div class="tree-load">⏳ Загрузка...</div>';
  fetch('/api/tree?prefix='+g.prefix).then(r=>r.json()).then(function(pos){_treePositions=pos;_showTreePositions();});
}
function _showTreePositions(){
  var h='<div class="tree-pos-list">';
  _treePositions.forEach(function(p,i){
    h+='<div class="tree-pos-item" onclick="treeClickPos('+i+')">'
      +'<span class="tree-pos-code">'+p.prefix+'</span>'
      +'<span class="tree-pos-name" title="'+esc(p.name)+'">'+esc(p.name.substring(0,75))+'</span>'
      +'<span class="tree-pos-cnt">'+p.count+'</span></div>';
  });
  document.getElementById('tree-content').innerHTML=h+'</div>';
}
function treeClickPos(i){
  var p=_treePositions[i];
  treeStack.push({type:'position',label:'Позиция '+p.prefix,pos:p});
  renderTreeBc();
  document.getElementById('tree-content').innerHTML='<div class="tree-load">⏳ Загрузка...</div>';
  fetch('/api/tree?prefix='+p.prefix).then(r=>r.json()).then(function(codes){_treeCodes=codes;_showTreeCodes();});
}
function _showTreeCodes(){
  var h='<table class="tree-code-tbl"><thead><tr>'
      +'<th style="width:110px">Код</th><th>Наименование</th>'
      +'<th style="width:80px;text-align:center">Пошлина</th>'
      +'<th style="width:46px;text-align:center">НДС</th>'
      +'</tr></thead><tbody>';
  _treeCodes.forEach(function(c,i){
    var d=c.poshlina_pct||0;
    h+='<tr><td><button class="tree-code-btn" onclick="treeClickCode('+i+')">'+c.code+'</button></td>'
      +'<td style="font-size:11px;color:#555">'+esc(c.name)+'</td>'
      +'<td style="text-align:center;font-family:monospace;font-weight:700;color:'+(d>0?'#c62828':'#2e7d32')+'">'+d+'%</td>'
      +'<td style="text-align:center;font-family:monospace">'+(c.nds_pct||12)+'%</td></tr>';
  });
  document.getElementById('tree-content').innerHTML=h+'</tbody></table>';
}
function treeClickCode(i){
  var c=_treeCodes[i];
  document.getElementById('search-inp').value=c.code+' — '+(c.name||'').substring(0,50);
  document.getElementById('manual-code').value=c.code;
  fetch('/api/lookup?code='+encodeURIComponent(c.code)).then(r=>r.json()).then(applyCodeInfo);
  document.querySelector('.wcard').scrollIntoView({behavior:'smooth'});
}
function renderTreeBc(){
  var el=document.getElementById('tree-bc');
  if(!treeStack.length){el.innerHTML='';return;}
  var h='<span class="tree-bc-item" onclick="treeNavBc(-1)">Разделы</span>';
  treeStack.forEach(function(e,i){
    h+='<span class="tree-bc-sep">›</span>';
    if(i<treeStack.length-1){
      h+='<span class="tree-bc-item" onclick="treeNavBc('+i+')">'+esc(e.label)+'</span>';
    }else{
      h+='<span class="tree-bc-cur">'+esc(e.label)+'</span>';
    }
  });
  el.innerHTML=h;
}
function treeNavBc(idx){
  if(idx<0){treeStack=[];_showTreeSections();renderTreeBc();return;}
  treeStack=treeStack.slice(0,idx+1);
  renderTreeBc();
  var e=treeStack[treeStack.length-1];
  if(e.type==='section')_showTreeGroups();
  else if(e.type==='group')_showTreePositions();
  else if(e.type==='position')_showTreeCodes();
}

</script>

<div class="ftr">
  <a href="https://tarif.customs.uz/ru" target="_blank">customs.uz ↗</a>
</div>
</body>
</html>
"""

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Вход — ТН ВЭД Калькулятор</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.1);padding:40px 36px;width:100%;max-width:380px}
.logo{text-align:center;font-size:42px;margin-bottom:8px}
.title{text-align:center;font-size:20px;font-weight:700;color:#1a2942;margin-bottom:4px}
.sub{text-align:center;font-size:13px;color:#6b7280;margin-bottom:28px}
label{display:block;font-size:13px;font-weight:600;color:#374151;margin-bottom:6px}
input{width:100%;padding:11px 14px;border:1.5px solid #d1d5db;border-radius:8px;font-size:14px;font-family:inherit;outline:none;transition:border-color .15s}
input:focus{border-color:#2563eb}
.field{margin-bottom:16px}
.btn{width:100%;padding:12px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:700;font-family:inherit;cursor:pointer;transition:background .15s;margin-top:4px}
.btn:hover{background:#1d4ed8}
.btn:disabled{background:#93c5fd;cursor:not-allowed}
.err{background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:10px 14px;color:#dc2626;font-size:13px;margin-bottom:16px;display:none}
</style>
</head>
<body>
<div class="card">
  <div class="logo">🛃</div>
  <div class="title">Тарифный калькулятор</div>
  <div class="sub">ТН ВЭД Узбекистан · Войдите для доступа</div>
  <div class="err" id="err"></div>
  <form onsubmit="doLogin(event)">
    <div class="field">
      <label for="u">Логин</label>
      <input type="text" id="u" autocomplete="username" required autofocus>
    </div>
    <div class="field">
      <label for="p">Пароль</label>
      <input type="password" id="p" autocomplete="current-password" required>
    </div>
    <button class="btn" type="submit" id="btn">Войти</button>
  </form>
</div>
<script>
function doLogin(e){
  e.preventDefault();
  var btn=document.getElementById('btn'),err=document.getElementById('err');
  btn.disabled=true;btn.textContent='Вход...';err.style.display='none';
  fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('u').value,password:document.getElementById('p').value})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){location.href='/';}
    else{err.textContent=d.error||'Неверный логин или пароль';err.style.display='block';btn.disabled=false;btn.textContent='Войти';}
  }).catch(function(){err.textContent='Ошибка сети';err.style.display='block';btn.disabled=false;btn.textContent='Войти';});
}
</script>
</body>
</html>"""


ADMIN_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Пользователи — ТН ВЭД</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f0f4f8;min-height:100vh}
.hdr{background:linear-gradient(135deg,#1D4ED8 0%,#2563EB 60%,#3B82F6 100%);color:#fff;padding:14px 24px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 12px rgba(37,99,235,.35)}
.hdr-back{margin-left:auto;color:rgba(255,255,255,.9);text-decoration:none;font-size:12px;font-weight:500;padding:6px 14px;border:1px solid rgba(255,255,255,.3);border-radius:6px;transition:all .15s}
.hdr-back:hover{background:rgba(255,255,255,.2)}
.wrap{max-width:900px;margin:28px auto;padding:0 16px}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08);padding:24px;margin-bottom:24px}
.card-title{font-size:15px;font-weight:700;color:#1a2942;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e5e7eb}
table{width:100%;border-collapse:collapse;font-size:13px}
th{padding:8px 12px;background:#f9fafb;border-bottom:2px solid #e5e7eb;text-align:left;font-weight:600;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid #f3f4f6;vertical-align:middle}
tr:last-child td{border-bottom:none}
.badge-inf{font-size:20px;color:#2563eb;font-weight:700;line-height:1}
.badge-num{font-weight:700;color:#1a2942;font-size:14px}
.badge-zero{font-weight:700;color:#dc2626;font-size:14px}
.days-ok{color:#15803d;font-weight:600}
.days-warn{color:#d97706;font-weight:600}
.days-bad{color:#dc2626;font-weight:600}
.days-none{color:#9ca3af}
.btn-del{background:none;border:1.5px solid #fca5a5;color:#dc2626;padding:5px 10px;border-radius:6px;font-size:11px;font-family:inherit;cursor:pointer;transition:all .15s}
.btn-del:hover{background:#fef2f2}
.btn-edit{background:none;border:1.5px solid #93c5fd;color:#2563eb;padding:5px 10px;border-radius:6px;font-size:11px;font-family:inherit;cursor:pointer;transition:all .15s}
.btn-edit:hover{background:#eff6ff}
.btn-save{background:#2563eb;border:none;color:#fff;padding:5px 10px;border-radius:6px;font-size:11px;font-family:inherit;cursor:pointer}
.btn-save:hover{background:#1d4ed8}
.erow td{background:#eff6ff!important;padding:8px 12px}
.ei{padding:5px 8px;border:1.5px solid #93c5fd;border-radius:5px;font-size:12px;font-family:inherit;outline:none}
.ei:focus{border-color:#2563eb}
label{display:block;font-size:13px;font-weight:600;color:#374151;margin-bottom:6px;margin-top:14px}
label:first-child{margin-top:0}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
input[type=text],input[type=password],input[type=number],input[type=date]{width:100%;padding:10px 14px;border:1.5px solid #d1d5db;border-radius:8px;font-size:14px;font-family:inherit;outline:none;transition:border-color .15s}
input:focus{border-color:#2563eb}
.btn-add{width:100%;padding:11px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;margin-top:16px;transition:background .15s}
.btn-add:hover{background:#1d4ed8}
.btn-add:disabled{background:#93c5fd;cursor:not-allowed}
.hint{font-size:11px;color:#9ca3af;margin-top:4px}
.msg{border-radius:8px;padding:10px 14px;font-size:13px;margin-top:12px;display:none}
.msg.ok{background:#f0fdf4;border:1px solid #86efac;color:#15803d}
.msg.err{background:#fef2f2;border:1px solid #fca5a5;color:#dc2626}
.empty{color:#9ca3af;font-size:13px;text-align:center;padding:20px 0}
.act{display:flex;gap:6px;white-space:nowrap}
</style>
</head>
<body>
<div class="hdr">
  <span style="font-size:22px">🛃</span>
  <span style="font-size:16px;font-weight:700">Управление пользователями</span>
  <a class="hdr-back" href="/">← На сайт</a>
</div>
<div class="wrap">
  <div class="card">
    <div class="card-title">Пользователи</div>
    <div id="tbl-wrap"><div class="empty">Загрузка...</div></div>
  </div>
  <div class="card">
    <div class="card-title">Добавить пользователя</div>
    <form onsubmit="addUser(event)">
      <div class="form-row">
        <div>
          <label for="nu">Логин</label>
          <input type="text" id="nu" required autocomplete="off">
        </div>
        <div>
          <label for="np">Пароль</label>
          <input type="password" id="np" required autocomplete="new-password">
        </div>
      </div>
      <div class="form-row">
        <div>
          <label for="nt">Количество запросов</label>
          <input type="number" id="nt" min="0" placeholder="∞ — не ограничено">
          <div class="hint">Оставьте пустым для безлимитного доступа</div>
        </div>
        <div>
          <label for="nd">Дата оплаты</label>
          <input type="date" id="nd">
          <div class="hint">Срок действия — 30 дней от даты оплаты</div>
        </div>
      </div>
      <button class="btn-add" type="submit" id="btn-add">Добавить</button>
    </form>
    <div class="msg" id="msg"></div>
  </div>
</div>
<script>
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function showMsg(t,ok){
  var m=document.getElementById('msg');
  m.textContent=t;m.className='msg '+(ok?'ok':'err');m.style.display='block';
  setTimeout(function(){m.style.display='none';},3500);
}
function daysHtml(n){
  if(n===null||n===undefined)return '<span class="days-none">—</span>';
  if(n<=0)return '<span class="days-bad">Истёк</span>';
  if(n<=7)return '<span class="days-warn">'+n+'</span>';
  return '<span class="days-ok">'+n+'</span>';
}
function tokHtml(t){
  if(t===null||t===undefined)return '<span class="badge-inf">∞</span>';
  if(t===0)return '<span class="badge-zero">0</span>';
  return '<span class="badge-num">'+t+'</span>';
}
function renderTable(users){
  var w=document.getElementById('tbl-wrap');
  if(!users||!users.length){w.innerHTML='<div class="empty">Нет пользователей</div>';return;}
  var h='<table><thead><tr><th>Пользователь</th><th>Запросы</th><th>Добавлен</th><th>Дата оплаты</th><th>Срок до</th><th>Осталось дней</th><th></th></tr></thead><tbody>';
  users.forEach(function(u){
    var uid=encodeURIComponent(u.username);
    h+='<tr id="row-'+uid+'">'
      +'<td>'+esc(u.username)+'</td>'
      +'<td>'+tokHtml(u.tokens)+'</td>'
      +'<td>'+(u.created_at||'—')+'</td>'
      +'<td>'+(u.paid_at||'—')+'</td>'
      +'<td>'+(u.expires_at||'—')+'</td>'
      +'<td>'+daysHtml(u.days_left)+'</td>'
      +'<td><div class="act">'
      +'<button class="btn-edit" data-u="'+esc(u.username)+'" onclick="toggleEdit(this)">Изменить</button>'
      +'<button class="btn-del" data-u="'+esc(u.username)+'" onclick="delUser(this)">Удалить</button>'
      +'</div></td></tr>'
      +'<tr class="erow" id="erow-'+uid+'" style="display:none"><td colspan="7">'
      +'<span style="font-weight:600;margin-right:16px;color:#374151">'+esc(u.username)+'</span>'
      +'Запросы:&nbsp;<input class="ei" type="number" min="0" placeholder="∞" id="et-'+uid+'" value="'+(u.tokens!==null&&u.tokens!==undefined?u.tokens:'')+'" style="width:80px;margin-right:12px">'
      +'Дата оплаты:&nbsp;<input class="ei" type="date" id="ep-'+uid+'" value="'+(u.paid_at||'')+'" style="width:140px;margin-right:12px">'
      +'<button class="btn-save" data-u="'+esc(u.username)+'" onclick="saveEdit(this)">Сохранить</button>'
      +'</td></tr>';
  });
  h+='</tbody></table>';
  w.innerHTML=h;
}
function loadUsers(){
  fetch('/api/admin/users').then(function(r){return r.json();}).then(function(d){renderTable(d.users||[]);});
}
function toggleEdit(btn){
  var uid=encodeURIComponent(btn.getAttribute('data-u'));
  var row=document.getElementById('erow-'+uid);
  row.style.display=row.style.display==='none'?'table-row':'none';
}
function saveEdit(btn){
  var u=btn.getAttribute('data-u');
  var uid=encodeURIComponent(u);
  var tv=document.getElementById('et-'+uid).value.trim();
  var pv=document.getElementById('ep-'+uid).value;
  fetch('/api/admin/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:u,tokens:tv===''?null:parseInt(tv),paid_at:pv||null})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok)loadUsers();else alert(d.error||'Ошибка');
  });
}
function delUser(btn){
  var u=btn.getAttribute('data-u');
  if(!confirm('Удалить «'+u+'»?'))return;
  fetch('/api/admin/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:u})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){showMsg('Пользователь «'+u+'» удалён',true);loadUsers();}
    else alert(d.error||'Ошибка');
  });
}
function addUser(e){
  e.preventDefault();
  var btn=document.getElementById('btn-add');
  btn.disabled=true;btn.textContent='Добавляю...';
  var tv=document.getElementById('nt').value.trim();
  fetch('/api/admin/add',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('nu').value,password:document.getElementById('np').value,
      tokens:tv===''?null:parseInt(tv),paid_at:document.getElementById('nd').value||null})
  }).then(function(r){return r.json();}).then(function(d){
    btn.disabled=false;btn.textContent='Добавить';
    if(d.ok){['nu','np','nt','nd'].forEach(function(id){document.getElementById(id).value='';});loadUsers();showMsg('Пользователь добавлен',true);}
    else showMsg(d.error||'Ошибка',false);
  }).catch(function(){btn.disabled=false;btn.textContent='Добавить';showMsg('Ошибка сети',false);});
}
loadUsers();
</script>
</body>
</html>"""

BLOCKED_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Доступ ограничен — ТН ВЭД</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f0f4f8;min-height:100vh}
.hdr{background:linear-gradient(135deg,#1D4ED8 0%,#2563EB 60%,#3B82F6 100%);color:#fff;padding:14px 24px;display:flex;align-items:center;justify-content:center;gap:16px;box-shadow:0 2px 12px rgba(37,99,235,.35)}
.hdr-nav{margin-left:auto;display:flex;align-items:center;gap:8px}
.hdr-nav a{color:rgba(255,255,255,.9);text-decoration:none;font-size:12px;font-weight:500;padding:6px 14px;border:1px solid rgba(255,255,255,.3);border-radius:6px}
.ftr-user{font-size:12px;color:rgba(255,255,255,.85);font-weight:500}
.ftr-sep{width:1px;height:16px;background:rgba(255,255,255,.25)}
.main{display:flex;align-items:center;justify-content:center;min-height:calc(100vh - 56px);padding:40px 20px}
.box{background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.1);padding:48px 40px;text-align:center;max-width:460px;width:100%}
.ico{font-size:56px;margin-bottom:20px}
h2{font-size:20px;font-weight:700;color:#1a2942;margin-bottom:12px}
p{font-size:14px;color:#6b7280;line-height:1.7}
</style>
</head>
<body>
<div class="hdr">
  <div style="font-size:26px">🛃</div>
  <div>
    <div style="font-size:16px;font-weight:700">Тарифный калькулятор — ТН ВЭД Узбекистан</div>
    <div style="font-size:11px;opacity:.8;margin-top:1px">ПП-181 от 14.05.2025</div>
  </div>
  <div class="hdr-nav">
    <span class="ftr-user">👤 CURRENT_USER_PLACEHOLDER</span>
    <div class="ftr-sep"></div>
    <a href="/logout">Выйти</a>
  </div>
</div>
<div class="main">
  <div class="box">
    <div class="ico">🚫</div>
    <h2>У вас закончилось количество запросов</h2>
    <p>Пополните баланс чтобы продолжить пользоваться программой.</p>
  </div>
</div>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _get_user(self):
        cookie = _auth.parse_cookie(self.headers.get('Cookie', ''))
        return _auth.verify_session(cookie)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if path == '/login':
            self._send(200, 'text/html; charset=utf-8', LOGIN_PAGE.encode())
            return

        if path == '/admin':
            if self._get_user() != 'Ildar Yusupov':
                self._redirect('/')
                return
            self._send(200, 'text/html; charset=utf-8', ADMIN_PAGE.encode())
            return

        if path == '/api/admin/users':
            if self._get_user() != 'Ildar Yusupov':
                self._send_json({'error': 'forbidden'})
                return
            self._send_json({'users': _auth.get_users_with_meta()})
            return

        if path == '/logout':
            self.send_response(302)
            self.send_header('Set-Cookie', _auth.cookie_header('', clear=True))
            self.send_header('Location', '/login')
            self.end_headers()
            return

        if not self._get_user():
            self._redirect('/login')
            return

        if path in ('/', '/tariff'):
            user = self._get_user() or ''
            allowed, reason = _auth.can_access(user)
            if not allowed:
                html = BLOCKED_PAGE.replace('CURRENT_USER_PLACEHOLDER', user)
                self._send(200, 'text/html; charset=utf-8', html.encode())
                return
            admin_link = '<a href="/admin">Пользователи</a>' if user == 'Ildar Yusupov' else ''
            html = PAGE.replace('COUNTRIES_JSON_PLACEHOLDER', country_items_json())
            html = html.replace('CURRENT_USER_PLACEHOLDER', user)
            html = html.replace('ADMIN_LINK_PLACEHOLDER', admin_link)
            html = html.replace('TOKENS_BADGE_PLACEHOLDER', _auth.tokens_badge_html(user))
            self._send(200, 'text/html; charset=utf-8', html.encode())

        elif path == '/api/lookup':
            code = params.get('code', '').strip()
            conn = get_db()
            row  = conn.execute('SELECT * FROM tnved WHERE code=?', (code,)).fetchone()
            if not row:
                row = conn.execute(
                    'SELECT * FROM tnved WHERE code LIKE ? ORDER BY code LIMIT 1',
                    (code + '%',)
                ).fetchone()
            conn.close()
            self._send_json(dict(row) if row else {'error': 'not found'})

        elif path == '/api/search':
            q = params.get('q', '').strip()
            self._send_json(smart_search(q, limit=18))

        elif path == '/api/docs':
            code  = params.get('code', '').strip()
            rejim = params.get('rejim', 'import').strip()
            self._send_json(get_docs(code, rejim))

        elif path == '/api/rates':
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
                self._send_json({'ok': True, 'rates': rates, 'date': date_str})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)})

        elif path == '/api/customs_check':
            code    = params.get('code', '').strip()
            origin  = params.get('origin', '').strip()
            sending = params.get('sending', '').strip()
            trade   = params.get('trade', '').strip()
            result  = customs_uz_lookup(code, origin, sending, trade)
            self._send_json(result)

        elif path == '/api/tree':
            prefix = params.get('prefix', '').strip()
            self._send_json(get_tree(prefix))

        else:
            self._send(404, 'text/plain', b'Not found')

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == '/api/login':
            username = data.get('username', '').strip()
            password = data.get('password', '')
            users    = _auth.load_users()
            if username in users and _auth.check_password(users[username], password):
                token = _auth.make_session(username)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Set-Cookie', _auth.cookie_header(token))
                resp = json.dumps({'ok': True}).encode()
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self._send_json({'ok': False, 'error': 'Неверный логин или пароль'})

        elif path == '/api/calc_token':
            user = self._get_user()
            if not user:
                self._send_json({'error': 'unauthorized'})
                return
            if not _auth.use_token(user):
                self._send_json({'error': 'no_tokens'})
                return
            users = _auth.load_users()
            remaining = users.get(user, {}).get('tokens')
            self._send_json({'ok': True, 'tokens': remaining})

        elif path == '/api/admin/add':
            if self._get_user() != 'Ildar Yusupov':
                self._send_json({'ok': False, 'error': 'forbidden'})
                return
            username = data.get('username', '').strip()
            password = data.get('password', '')
            if not username or not password:
                self._send_json({'ok': False, 'error': 'Укажите логин и пароль'})
                return
            users = _auth.load_users()
            users[username] = {
                'password':   _auth.hash_password(password),
                'tokens':     data.get('tokens'),
                'created_at': datetime.date.today().isoformat(),
                'paid_at':    data.get('paid_at'),
            }
            _auth.save_users(users)
            self._send_json({'ok': True})

        elif path == '/api/admin/update':
            if self._get_user() != 'Ildar Yusupov':
                self._send_json({'ok': False, 'error': 'forbidden'})
                return
            username = data.get('username', '').strip()
            users = _auth.load_users()
            if username not in users:
                self._send_json({'ok': False, 'error': 'Пользователь не найден'})
                return
            users[username]['tokens']  = data.get('tokens')
            users[username]['paid_at'] = data.get('paid_at')
            _auth.save_users(users)
            self._send_json({'ok': True})

        elif path == '/api/admin/delete':
            if self._get_user() != 'Ildar Yusupov':
                self._send_json({'ok': False, 'error': 'forbidden'})
                return
            username = data.get('username', '').strip()
            users = _auth.load_users()
            if username not in users:
                self._send_json({'ok': False, 'error': 'Пользователь не найден'})
                return
            del users[username]
            _auth.save_users(users)
            self._send_json({'ok': True})

        else:
            self._send(404, 'text/plain', b'Not found')

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        self._send(200, 'application/json; charset=utf-8', body)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5002
    print(f'\n  Тарифный калькулятор (расширенный): http://localhost:{port}')
    print(f'  Простой калькулятор:                http://localhost:5001')
    print(f'  База ТН ВЭД:                        http://localhost:5000')
    print(f'  Для остановки — Ctrl+C\n')
    HTTPServer(('', port), Handler).serve_forever()
