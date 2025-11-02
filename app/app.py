# Импорт необходимых библиотек
import random
from flask import Flask, render_template, request, redirect, url_for
from faker import Faker

# Создание экземпляра Faker для генерации тестовых данных
fake = Faker()

# Создание Flask приложения
app = Flask(__name__)
application = app  # Для совместимости с WSGI серверами

# Список ID изображений для постов (соответствуют файлам в папке static/images/)
images_ids = ['7d4e9175-95ea-4c5f-8be5-92a6b708bb3c',
              '2d2ab7df-cdbc-48a8-a936-35bba702def5',
              '6e12f3de-d5fd-4ebb-855b-8cbc485278b7',
              'afc2cfe7-5cac-4b80-9b9a-d5c65ef0c728',
              'cab5b7f2-774e-4884-a200-0c0180fa777f']

def generate_comments(replies=True):
    """
    Генерирует случайные комментарии для постов
    Args:
        replies (bool): Если True, генерирует ответы на комментарии
    Returns:
        list: Список комментариев с автором, текстом и датой
    """
    comments = []
    for i in range(random.randint(1, 3)):
        comment = { 
            'author': fake.name(), 
            'text': fake.text(),
            'date': fake.date_time_between(start_date='-1y', end_date='now')
        }
        if replies:
            comment['replies'] = generate_comments(replies=False)
        comments.append(comment)
    return comments

def generate_post(i):
    """
    Генерирует один пост с случайными данными
    Args:
        i (int): Индекс поста (используется для выбора изображения)
    Returns:
        dict: Словарь с данными поста
    """
    return {
        'title': 'Заголовок поста',
        'text': fake.paragraph(nb_sentences=100),
        'author': fake.name(),
        'date': fake.date_time_between(start_date='-2y', end_date='now'),
        'image_id': f'{images_ids[i]}.jpg',
        'comments': generate_comments()
    }

# Генерация списка постов и сортировка по дате (новые сверху)
posts_list = sorted([generate_post(i) for i in range(5)], key=lambda p: p['date'], reverse=True)

# Маршруты Flask приложения

@app.route('/')
def index():
    """Главная страница с заданием лабораторной работы"""
    return render_template('index.html')

@app.route('/posts')
def posts():
    """Страница со списком всех постов"""
    return render_template('posts.html', title='Посты', posts=posts_list)

@app.route('/posts/<int:index>')
def post(index):
    """Страница отдельного поста по индексу"""
    p = posts_list[index]
    return render_template('post.html', title=p['title'], post=p)

@app.route('/about')
def about():
    """Страница об авторе"""
    return render_template('about.html', title='Об авторе')

# ----- ЛР2: Отображение данных запроса и форма авторизации -----

@app.route('/request-data', methods=['GET', 'POST'])
def request_data():
    """Страница, отображающая параметры URL, заголовки, cookie и параметры формы."""
    url_params = request.args.to_dict(flat=False)
    headers = dict(request.headers)
    cookies = request.cookies
    # Параметры формы: при POST берём из request.form, при GET — из request.args
    form_params = (
        request.form.to_dict(flat=False)
        if request.method == 'POST'
        else request.args.to_dict(flat=False)
    )
    full_url = request.url
    query_string = request.query_string.decode('utf-8')
    return render_template(
        'request_data.html',
        title='Данные запроса',
        url_params=url_params,
        headers=headers,
        cookies=cookies,
        form_params=form_params,
        method=request.method,
        full_url=full_url,
        query_string=query_string
    )

@app.route('/auth', methods=['GET'])
def auth():
    """Страница с формой авторизации, отправляющей данные на /request-data."""
    return render_template('auth.html', title='Авторизация')

# ----- ЛР2: Проверка телефона -----

def normalize_phone(digits: str) -> str:
    """Преобразует 10/11-значную строку цифр к формату 8-***-***-**-**."""
    # digits содержит только цифры
    if len(digits) == 11 and (digits.startswith('8') or digits.startswith('7')):
        core = digits[-10:]
    elif len(digits) == 10:
        core = digits
    else:
        # Сюда не дойдём при корректной предварительной проверке длины
        core = digits[-10:]
    return f"8-{core[0:3]}-{core[3:6]}-{core[6:8]}-{core[8:10]}"

@app.route('/phone-check', methods=['GET', 'POST'])
def phone_check():
    """Страница проверки телефона: форма (POST) + вывод ошибок/результата."""
    value = ''
    error = ''
    normalized = ''

    if request.method == 'POST':
        value = request.form.get('phone', '').strip()

        # Допустимые символы: цифры, пробелы, () - . +
        import re
        allowed_pattern = re.compile(r'^[0-9\s()\-\.\+]*$')
        if not allowed_pattern.match(value):
            error = 'Недопустимый ввод. В номере телефона встречаются недопустимые символы.'
        else:
            # Оставляем только цифры для проверки длины
            digits = re.sub(r'\D', '', value)
            # Определяем требуемую длину по первым числовым символам (устойчиво к замене '+' на пробел)
            first_digit = next((ch for ch in value if ch.isdigit()), '')
            starts_with_8 = first_digit == '8'
            starts_with_7 = first_digit == '7'
            required_len = 11 if (starts_with_8 or (starts_with_7 and len(digits) == 11)) else 10
            if len(digits) != required_len:
                error = 'Недопустимый ввод. Неверное количество цифр.'
            else:
                normalized = normalize_phone(digits)

    return render_template(
        'phone_check.html',
        title='Проверка телефона',
        value=value,
        error=error,
        normalized=normalized
    )
