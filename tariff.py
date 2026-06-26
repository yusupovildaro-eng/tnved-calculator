#!/usr/bin/env python3
"""
Тарифный калькулятор — расширенная форма с выбором страны и сравнением с customs.uz
python3 tariff.py        → http://localhost:5002
python3 tariff.py 5003   → другой порт
"""
import sys, json, sqlite3, os, re, ssl
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, urlencode
import urllib.request

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

# ─── HTML PAGE ─────────────────────────────────────────────────────────────────
PAGE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Тарифный калькулятор — ТН ВЭД Узбекистан</title>
<style>
/* ══ RESET ══════════════════════════════════════════════════════════════════════ */
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f0f2f5;color:#212121;min-height:100vh}
/* ══ HEADER ═════════════════════════════════════════════════════════════════════ */
.hdr{background:#1565c0;color:#fff;padding:10px 20px;display:flex;align-items:center;gap:14px}
.hdr-logo{font-size:22px}
.hdr-info{}
.hdr-title{font-size:17px;font-weight:700;line-height:1.2}
.hdr-sub{font-size:11px;opacity:.75}
.hdr-nav{margin-left:auto;display:flex;gap:8px}
.hdr-nav a{color:#fff;text-decoration:none;font-size:11px;padding:4px 10px;border:1px solid rgba(255,255,255,.4);border-radius:3px}
.hdr-nav a:hover{background:rgba(255,255,255,.15)}
/* ══ MAIN WRAP ══════════════════════════════════════════════════════════════════ */
.main-wrap{max-width:980px;margin:0 auto;padding:14px 16px}
/* ══ WHITE CARD ═════════════════════════════════════════════════════════════════ */
.wcard{background:#fff;border:1px solid #e0e0e0;border-radius:3px;margin-bottom:6px}
/* ══ SEARCH + DIRECTION ROW ═════════════════════════════════════════════════════ */
.search-bar{display:flex;align-items:center;gap:10px;padding:12px 14px;flex-wrap:wrap}
.search-wrap{position:relative;flex:1;min-width:180px;max-width:420px}
.search-inp{width:100%;padding:8px 12px;border:1px solid #bdbdbd;border-radius:3px;font-size:14px;outline:none}
.search-inp:focus{border-color:#1565c0}
#ac-list{position:absolute;top:100%;left:0;right:0;background:#fff;border:1px solid #1565c0;
         border-top:none;border-radius:0 0 3px 3px;max-height:280px;overflow-y:auto;z-index:400;display:none;
         box-shadow:0 4px 12px rgba(0,0,0,.12)}
#ac-list div{padding:8px 12px;cursor:pointer;font-size:12px;border-bottom:1px solid #f5f5f5;line-height:1.3}
#ac-list div:hover{background:#e3f2fd}
.ac-code{font-family:monospace;font-weight:700;color:#1565c0;margin-right:6px}
.btn-search{background:#1565c0;color:#fff;border:none;padding:8px 14px;border-radius:3px;cursor:pointer;font-size:16px;line-height:1}
.btn-search:hover{background:#0d47a1}
.dir-group{display:flex;align-items:center;gap:14px;margin-left:4px}
.dir-lbl{display:flex;align-items:center;gap:5px;cursor:pointer;font-size:14px;color:#333}
.dir-lbl input{accent-color:#1565c0;width:15px;height:15px;cursor:pointer}
.cis-badge{background:#e8f5e9;color:#2e7d32;font-size:11px;font-weight:700;padding:3px 9px;border-radius:3px;border:1px solid #a5d6a7;margin-left:6px}
.err-msg{color:#c62828;font-size:12px;padding:6px 12px;background:#ffebee;border-radius:3px;margin:0 14px 10px;display:none}
/* code panel */
#code-panel{display:none;padding:0 14px 12px}
.cp-code{font-family:monospace;font-size:15px;font-weight:700;color:#0d47a1}
.cp-name{font-size:12px;color:#555;margin:3px 0 8px;line-height:1.4}
.cp-tags{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}
.tag{padding:2px 8px;border-radius:3px;font-size:11px;font-weight:700}
.tag-red{background:#ffebee;color:#c62828}
.tag-green{background:#e8f5e9;color:#1b5e20}
.tag-blue{background:#e3f2fd;color:#0d47a1}
.tag-orange{background:#fff3e0;color:#e65100}
.tag-gray{background:#f5f5f5;color:#666}
#rate-info{display:none}
.ri-table{width:100%;border-collapse:collapse;font-size:12px}
.ri-table td{padding:4px 8px;border-bottom:1px solid #f0f0f0}
.ri-table .lbl{color:#666;width:55%}
.ri-table .val{font-weight:700;text-align:right}
.ri-highlight{background:#e3f2fd}
.ri-formula{font-family:monospace;font-size:11px;color:#555;padding:7px 10px;background:#fafafa;
             border-left:3px solid #1565c0;border-radius:0 3px 3px 0;margin-top:7px;line-height:1.8}
/* ══ COUNTRY ROW ════════════════════════════════════════════════════════════════ */
.country-bar{padding:12px 14px}
.country-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:580px){.country-row{grid-template-columns:1fr}}
.cs-field>label{display:block;font-size:11px;color:#757575;margin-bottom:4px;font-weight:500}
/* ══ CUSTOM SELECT ══════════════════════════════════════════════════════════════ */
.cs-wrap{position:relative;user-select:none}
.cs-selected{display:flex;align-items:center;padding:8px 32px 8px 10px;border:1px solid #bdbdbd;
              border-radius:3px;font-size:13px;cursor:pointer;background:#fff;
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-height:36px;position:relative}
.cs-arr{position:absolute;right:10px;top:50%;transform:translateY(-50%);pointer-events:none;
         width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid #757575}
.cs-wrap.open .cs-selected{border-color:#1565c0;border-radius:3px 3px 0 0}
.cs-wrap.open .cs-arr{border-top:none;border-bottom:5px solid #1565c0}
.cs-dropdown{display:none;position:absolute;top:100%;left:0;right:0;background:#fff;
              border:1px solid #1565c0;border-top:none;border-radius:0 0 3px 3px;
              z-index:300;box-shadow:0 4px 12px rgba(0,0,0,.12)}
.cs-wrap.open .cs-dropdown{display:block}
.cs-search-inp{width:100%;padding:7px 10px;border:none;border-bottom:1px solid #e0e0e0;font-size:13px;outline:none}
.cs-list{max-height:210px;overflow-y:auto}
.cs-item{padding:6px 12px;font-size:12px;cursor:pointer;border-bottom:1px solid #f5f5f5;
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cs-item:hover,.cs-item.cs-active{background:#e3f2fd;color:#0d47a1}
.cs-item.cs-none{color:#aaa;font-style:italic}
.cs-no-results{padding:10px 12px;font-size:12px;color:#aaa;text-align:center}
#country-note{font-size:12px;margin-top:8px;padding:7px 10px;border-radius:3px;background:#fff3e0;border:1px solid #ffcc80;color:#5d4037}
/* ══ ACTION BAR ═════════════════════════════════════════════════════════════════ */
.action-bar{display:flex;align-items:center;gap:8px;padding:8px 14px;flex-wrap:wrap;
             border-top:1px solid #f5f5f5;background:#fafafa;border-radius:0 0 3px 3px}
.abtn{padding:7px 14px;border-radius:3px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid}
.abtn-green{background:#fff;color:#2e7d32;border-color:#43a047}
.abtn-green:hover{background:#e8f5e9}
.abtn-amber{background:#fff;color:#e65100;border-color:#ff8f00}
.abtn-amber:hover{background:#fff3e0}
.abtn-blue{background:#fff;color:#1565c0;border-color:#1565c0}
.abtn-blue:hover{background:#e3f2fd}
#rates-date{font-size:11px;color:#888;margin-left:2px}
.loading{display:none;font-size:13px;color:#1565c0;padding:0 8px}
/* ══ SECTIONS ═══════════════════════════════════════════════════════════════════ */
.section{background:#fff;border:1px solid #e0e0e0;border-radius:3px;margin-bottom:6px;overflow:visible}
.sec-hdr{display:flex;justify-content:space-between;align-items:center;padding:11px 18px;cursor:pointer;user-select:none}
.sec-hdr:hover{background:#fafafa}
.sec-title{font-size:16px;font-weight:600;color:#1565c0}
.sec-arr{color:#1565c0;font-size:13px;transition:transform .2s}
.section.collapsed .sec-arr{transform:rotate(180deg)}
.sec-body{padding:0 18px 16px;border-top:1px solid #eeeeee}
.section.collapsed .sec-body{display:none}
/* ══ RATES TABLE ════════════════════════════════════════════════════════════════ */
.rates-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
.rates-tbl th{padding:9px 12px;text-align:left;border:1px solid #e0e0e0;color:#757575;font-weight:500;background:#fafafa;font-size:12px}
.rates-tbl td{padding:9px 12px;border:1px solid #e0e0e0;vertical-align:middle}
.rates-tbl .col-type{color:#333;font-weight:500}
.rates-tbl .col-rate{font-weight:700;color:#0d47a1;font-family:monospace;text-align:center;width:130px}
.rates-tbl .col-law{color:#555;font-size:12px}
/* ══ DOCS TABLE ═════════════════════════════════════════════════════════════════ */
.docs-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
.docs-tbl th{padding:9px 12px;text-align:left;border:1px solid #e0e0e0;color:#757575;font-weight:500;background:#fafafa;font-size:12px}
.docs-tbl td{padding:10px 12px;border:1px solid #e0e0e0;text-align:left;color:#212121;font-size:13px}
.docs-tbl td.doc-org{color:#1565c0;font-weight:500}
.docs-tbl td.doc-name{color:#333}
.doc-org-link{color:#1565c0;text-decoration:none;font-weight:500}
.doc-org-link:hover{text-decoration:underline;color:#0d47a1}
.doc-restrict-block{background:#fff8e1;border:1px solid #ffca28;border-radius:4px;padding:10px 14px;font-size:12px}
.doc-restrict-block .restrict-title{font-weight:600;color:#e65100;margin-bottom:6px}
.doc-restrict-item{margin-bottom:4px;color:#555}
.doc-restrict-item b{color:#c62828}
/* ══ CALCULATOR ══════════════════════════════════════════════════════════════════ */
.calc-row{display:grid;grid-template-columns:1fr 80px 1fr 1fr;gap:8px;align-items:end;margin:10px 0 4px}
@media(max-width:680px){.calc-row{grid-template-columns:1fr 1fr}}
.cf label{display:block;font-size:11px;color:#757575;margin-bottom:4px;font-weight:500}
.cf input,.cf select{width:100%;padding:8px 10px;border:1px solid #bdbdbd;border-radius:3px;font-size:13px;outline:none}
.cf input:focus,.cf select:focus{border-color:#1565c0}
.dosmotr-box{background:#fafafa;border:1px solid #e0e0e0;border-radius:3px;padding:10px 14px;margin:8px 0}
.dosmotr-box .d-title{font-size:13px;font-weight:500;color:#333;margin-bottom:8px}
.dosmotr-grid{display:flex;gap:24px}
.di label{display:block;font-size:11px;color:#757575;margin-bottom:4px}
.di input{padding:6px 10px;border:1px solid #bdbdbd;border-radius:3px;font-size:13px;width:90px;outline:none}
.di input:focus{border-color:#1565c0}
.price3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:8px 0}
@media(max-width:580px){.price3{grid-template-columns:1fr}}
.price3 .pf label{display:block;font-size:11px;color:#757575;margin-bottom:4px}
.price3 .pf input{width:100%;padding:8px 10px;border:1px solid #bdbdbd;border-radius:3px;font-size:13px;outline:none}
.price3 .pf input:focus{border-color:#1565c0}
.calc-footer{display:flex;justify-content:flex-end;gap:10px;margin-top:14px;align-items:center}
.btn-calc{background:#1565c0;color:#fff;border:none;padding:10px 28px;border-radius:3px;font-size:14px;font-weight:700;cursor:pointer}
.btn-calc:hover{background:#0d47a1}
.btn-compare{background:#fff;color:#1565c0;border:1.5px solid #1565c0;padding:10px 18px;border-radius:3px;font-size:13px;font-weight:600;cursor:pointer}
.btn-compare:hover{background:#e3f2fd}
#alc-wrap{display:none}
/* ══ RESULTS ════════════════════════════════════════════════════════════════════ */
#result-area{display:none;margin-top:14px;padding-top:14px;border-top:1px solid #eeeeee}
#placeholder{text-align:center;padding:28px;color:#bbb;font-size:13px}
.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
@media(max-width:580px){.compare-grid{grid-template-columns:1fr}}
.compare-col{border-radius:3px;padding:14px;border:1px solid}
.col-ours{border-color:#1565c0;background:#e3f2fd}
.col-customs{border-color:#bdbdbd;background:#fafafa}
.col-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.col-ours .col-title{color:#0d47a1}
.col-customs .col-title{color:#666}
.res-row{display:flex;justify-content:space-between;align-items:baseline;padding:5px 0;border-bottom:1px solid rgba(0,0,0,.06);font-size:13px}
.res-row:last-child{border-bottom:none}
.res-label{color:#555}
.res-val{font-weight:700;font-family:monospace;font-size:12px}
.res-note{font-size:10px;color:#999}
.res-total{background:rgba(21,101,192,.1);border-radius:3px;padding:8px 10px;margin-top:8px;display:flex;justify-content:space-between}
.res-total-lbl{font-weight:700;font-size:13px;color:#0d47a1}
.res-total-val{font-weight:800;font-size:15px;color:#0d47a1;font-family:monospace}
.diff-box{background:#fff8e1;border:1px solid #ffe082;border-radius:3px;padding:10px 14px;font-size:12px;margin-top:10px}
.diff-ok{background:#e8f5e9;border-color:#a5d6a7}
.formula-box{background:#fafafa;border:1px solid #e0e0e0;border-radius:3px;padding:12px;margin-top:12px;font-size:11px;font-family:monospace;line-height:1.8;color:#333;display:none}
/* ══ HISTORY PANEL ══════════════════════════════════════════════════════════════ */
#hist-panel{display:none;background:#fff;border:1px solid #e0e0e0;border-radius:3px;padding:16px;margin-bottom:6px}
.hist-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.hist-hdr-title{font-size:14px;font-weight:700;color:#1565c0}
.hist-close{cursor:pointer;color:#aaa;font-size:18px;line-height:1}
.hist-clear{background:none;border:1px solid #ef5350;color:#ef5350;border-radius:3px;padding:3px 8px;font-size:11px;cursor:pointer}
.hist-tbl{width:100%;border-collapse:collapse;font-size:12px}
.hist-tbl th{background:#f5f7fa;padding:7px 10px;text-align:left;font-weight:600;color:#555;border-bottom:2px solid #e0e0e0}
.hist-tbl td{padding:7px 10px;border-bottom:1px solid #f0f0f0;vertical-align:middle}
.hist-tbl tr:hover td{background:#f8faff}
.hist-tbl .mono{font-family:monospace;font-weight:700}
.hist-del{cursor:pointer;color:#ef5350;font-size:13px;padding:0 4px}
.hist-empty{color:#bbb;text-align:center;padding:20px;font-size:13px}
/* ══ SBOR details ════════════════════════════════════════════════════════════════ */
details summary{cursor:pointer;font-size:11px;color:#1565c0;font-weight:600;margin:8px 0 0}
details table{width:100%;border-collapse:collapse;font-size:11px;margin-top:6px}
details td,details th{padding:3px 7px;border:1px solid #e0e0e0}
details th{background:#f5f7fa}
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
    <a href="http://localhost:5001/" target="_blank">Простой калькулятор</a>
    <a href="https://tarif.customs.uz/ru" target="_blank">customs.uz ↗</a>
  </div>
</div>

<div class="main-wrap">

  <!-- ── Поиск + Направление ────────────────────────────────────────────────── -->
  <div class="wcard">
    <div class="search-bar">
      <div class="search-wrap">
        <input type="text" id="search-inp" class="search-inp"
               placeholder="Введите наименование товара или код ТН ВЭД..." autocomplete="off">
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

// ─── Autocomplete ─────────────────────────────────────────────────────────────
var acTimer=null;
document.getElementById('search-inp').addEventListener('input',function(){
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
  document.getElementById('manual-code').value=item.code;
  hideAC();
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
  fetch('/api/lookup?code='+encodeURIComponent(q))
    .then(r=>r.json()).then(applyCodeInfo);
}

// ─── Apply code info ──────────────────────────────────────────────────────────
var UNIT_LBL={kg:'кг',liter:'л',liter_alc:'л спирта',m2:'м²',item:'шт.',pair:'пар',cc:'куб.см',per1000:'тыс.шт.'};
var AKSIZ_LBL={per1000:'тыс.шт.',liter:'л',liter_alc:'л спирта',kg:'кг',ml:'мл',item:'шт.'};

function applyCodeInfo(data){
  var errEl=document.getElementById('code-error');
  if(!data||data.error){errEl.style.display='block';selectedCode=null;document.getElementById('code-panel').style.display='none';return;}
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
function calculate(){
  if(!selectedCode){alert('Выберите код ТН ВЭД');return;}
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
</script>
</body>
</html>
"""



class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if path in ('/', '/tariff'):
            html = PAGE.replace('COUNTRIES_JSON_PLACEHOLDER', country_items_json())
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
