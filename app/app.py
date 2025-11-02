# Импорт необходимых библиотек
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from faker import Faker
from functools import wraps
from io import StringIO
import csv

# Создание экземпляра Faker для генерации тестовых данных
fake = Faker()

# Создание Flask приложения
app = Flask(__name__)
application = app  # Для совместимости с WSGI серверами
app.secret_key = 'dev-secret-key'  # Требуется для работы session и защиты cookies

# ----- База данных (SQLite через Flask-SQLAlchemy) -----
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    users = db.relationship('User', back_populates='role')

# ----- Создание таблицы пользователей -----
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(64), nullable=True)
    middle_name = db.Column(db.String(64), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    role = db.relationship('Role', back_populates='users')
# ----- Работа с паролем -----
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class VisitLog(db.Model):
    __tablename__ = 'visit_logs'
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

# ----- Инициализация аутентификации (Flask-Login) -----
login_manager = LoginManager(app)
login_manager.login_view = 'auth'
login_manager.login_message = 'Для доступа требуется аутентификация.'


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


# ----- Права и авторизация -----
# Правила прав по ролям
ROLE_RIGHTS = {
    'Администратор': {
        'create_users',
        'edit_users',
        'view_user',
        'delete_users',
        'view_visits',
    },
    'Пользователь': {
        'edit_self',
        'view_self',
        'view_visits',
    },
}


def user_has_right(user: User, right: str) -> bool:
    if user is None or not getattr(user, 'role', None):
        return False
    rights = ROLE_RIGHTS.get(user.role.name or '', set())
    return right in rights


def check_rights(required_right: str | None = None, allow_self: tuple[str, str] | None = None):
    """Декоратор проверки прав.
    required_right: право, необходимое для доступа.
    allow_self: кортеж (self_right, kwarg_name_with_user_id) — если пользователь имеет право self_right
                и обращается к собственному ресурсу (id из kwargs), доступ разрешается.
    При недостатке прав — редирект на главную с сообщением.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('У вас недостаточно прав для доступа к данной странице.', 'danger')
                return redirect(url_for('index'))

            # Сценарий 1: есть прямое право
            if required_right and user_has_right(current_user, required_right):
                return view_func(*args, **kwargs)

            # Сценарий 2: есть право на собственные данные и доступ к своему id
            if allow_self is not None:
                self_right, id_kwarg = allow_self
                target_id = kwargs.get(id_kwarg)
                try:
                    is_self = (int(getattr(current_user, 'id', -1)) == int(target_id))
                except Exception:
                    is_self = False
                if is_self and user_has_right(current_user, self_right):
                    return view_func(*args, **kwargs)

            flash('У вас недостаточно прав для доступа к данной странице.', 'danger')
            return redirect(url_for('index'))
        return wrapped
    return decorator


@app.context_processor
def inject_rights_helpers():
    return {
        'has_right': lambda right: (current_user.is_authenticated and user_has_right(current_user, right))
    }


@app.before_request
def log_visit():
    try:
        # Пропускаем статические файлы и служебные пути
        p = request.path or '/'
        if p.startswith('/static') or p == '/favicon.ico':
            return
        uid = current_user.id if current_user.is_authenticated else None
        # Ограничим длину пути безопасно
        path_value = p[:100]
        db.session.add(VisitLog(path=path_value, user_id=uid))
        db.session.commit()
    except Exception:
        db.session.rollback()

def init_db_seed() -> None:
    """Создаёт таблицы и минимальные данные (роли и пользователя user/qwerty), если их нет."""
    db.create_all()
    # Роли по умолчанию
    role_user = Role.query.filter_by(name='Пользователь').first()
    if role_user is None:
        role_user = Role(name='Пользователь', description='Базовая роль пользователя')
        db.session.add(role_user)
        db.session.commit()
    role_admin = Role.query.filter_by(name='Администратор').first()
    if role_admin is None:
        role_admin = Role(name='Администратор', description='Полные права')
        db.session.add(role_admin)
        db.session.commit()
    # Пользователь user/qwerty
    user = User.query.filter_by(username='user').first()
    if user is None:
        # Сделаем тестового пользователя администратором для удобства проверки прав
        user = User(username='user', last_name=None, first_name='User', middle_name=None, role=role_admin)
        user.set_password('qwerty')
        db.session.add(user)
        db.session.commit()


@app.before_request
def ensure_db_initialized():
    """Гарантируем, что все таблицы существуют и минимальные данные созданы.
    Flask 3+: заменяем before_first_request одноразовым выполнением под флагом.
    """
    if getattr(app, '_db_inited', False):
        return
    try:
        init_db_seed()
        app._db_inited = True
    except Exception:
        db.session.rollback()

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

# (устаревшая главная страница ЛР2/ЛР3 удалена, актуальная версия ниже в блоке ЛР4)

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

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    """Страница входа: форма (GET) и обработка (POST) с remember-me."""
    error = ''
    username = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user_record = User.query.filter_by(username=username).first()
        if user_record and user_record.check_password(password):
            login_user(user_record, remember=remember)
            flash('Вы успешно вошли в систему.', 'success')
            # Сохраняем целевую страницу, если пришли с редиректа login_required
            next_url = request.form.get('next') or request.args.get('next')
            return redirect(next_url or url_for('index'))
        else:
            error = 'Неверный логин или пароль.'

    return render_template('auth.html', title='Аутентификация', error=error, username=username)


@app.route('/logout')
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

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

# ----- ЛР3: Счётчик посещений с использованием session -----

@app.route('/visit-logs')
@check_rights('view_visits')
def visit_logs():
    """Журнал посещений с пагинацией: админ видит всё, пользователь — свои записи."""
    try:
        page = int(request.args.get('page', '1'))
        if page < 1:
            page = 1
    except Exception:
        page = 1
    per_page = 20
    offset = (page - 1) * per_page

    # Базовый запрос с присоединением пользователя для отображения ФИО
    q = (
        db.session.query(
            VisitLog.id,
            VisitLog.path,
            VisitLog.user_id,
            VisitLog.created_at,
            User.last_name,
            User.first_name,
            User.middle_name,
        )
        .outerjoin(User, VisitLog.user_id == User.id)
        .order_by(VisitLog.created_at.desc(), VisitLog.id.desc())
    )
    if not user_has_right(current_user, 'view_user'):
        q = q.filter(VisitLog.user_id == current_user.id)

    total = q.count()
    rows = q.offset(offset).limit(per_page).all()

    items = []
    for r in rows:
        if r.user_id is None:
            fio = 'Неаутентифицированный пользователь'
        else:
            fio = f"{r.last_name or ''} {r.first_name or ''} {r.middle_name or ''}".strip()
            if not fio:
                fio = f"id={r.user_id}"
        items.append({
            'id': r.id,
            'path': r.path,
            'fio': fio,
            'created_at': r.created_at,
        })

    has_prev = page > 1
    has_next = offset + len(items) < total

    return render_template(
        'visit_logs.html',
        title='Журнал посещений',
        logs=items,
        page=page,
        per_page=per_page,
        total=total,
        start_index=offset + 1,
        has_prev=has_prev,
        has_next=has_next,
    )


@app.route('/visit-logs/pages')
@check_rights('view_visits')
def visit_logs_pages():
    """Отчёт: посещения по страницам."""
    rows = (
        db.session.query(VisitLog.path, func.count(VisitLog.id).label('cnt'))
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )
    items = [{'path': r.path, 'cnt': r.cnt} for r in rows]
    return render_template('visit_logs_pages.html', title='Отчёт по страницам', items=items)


@app.route('/visit-logs/pages.csv')
@check_rights('view_visits')
def visit_logs_pages_csv():
    rows = (
        db.session.query(VisitLog.path, func.count(VisitLog.id).label('cnt'))
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Страница', 'Количество посещений'])
    for r in rows:
        writer.writerow([r.path, r.cnt])
    resp = app.response_class(output.getvalue(), mimetype='text/csv; charset=utf-8')
    resp.headers['Content-Disposition'] = 'attachment; filename="visit_logs_pages.csv"'
    return resp


@app.route('/visit-logs/users')
@check_rights('view_visits')
def visit_logs_users():
    """Отчёт: посещения по пользователям (ФИО или Неаутентифицированный пользователь)."""
    rows = (
        db.session.query(
            VisitLog.user_id,
            User.last_name,
            User.first_name,
            User.middle_name,
            func.count(VisitLog.id).label('cnt'),
        )
        .outerjoin(User, VisitLog.user_id == User.id)
        .group_by(VisitLog.user_id, User.last_name, User.first_name, User.middle_name)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )
    items = []
    for r in rows:
        if r.user_id is None:
            fio = 'Неаутентифицированный пользователь'
        else:
            fio = f"{r.last_name or ''} {r.first_name or ''} {r.middle_name or ''}".strip() or f"id={r.user_id}"
        items.append({'fio': fio, 'cnt': r.cnt})
    return render_template('visit_logs_users.html', title='Отчёт по пользователям', items=items)


@app.route('/visit-logs/users.csv')
@check_rights('view_visits')
def visit_logs_users_csv():
    rows = (
        db.session.query(
            VisitLog.user_id,
            User.last_name,
            User.first_name,
            User.middle_name,
            func.count(VisitLog.id).label('cnt'),
        )
        .outerjoin(User, VisitLog.user_id == User.id)
        .group_by(VisitLog.user_id, User.last_name, User.first_name, User.middle_name)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Пользователь', 'Количество посещений'])
    for r in rows:
        fio = 'Неаутентифицированный пользователь' if r.user_id is None else (f"{r.last_name or ''} {r.first_name or ''} {r.middle_name or ''}".strip() or f"id={r.user_id}")
        writer.writerow([fio, r.cnt])
    resp = app.response_class(output.getvalue(), mimetype='text/csv; charset=utf-8')
    resp.headers['Content-Disposition'] = 'attachment; filename="visit_logs_users.csv"'
    return resp


# ----- ЛР4: Пользователи — список и просмотр -----

@app.route('/')
def index():
    """Главная: список пользователей (таблица)."""
    # Выбираем пользователей вместе с названием роли (outer join)
    users = (
        db.session.query(
            User.id,
            User.username,
            User.last_name,
            User.first_name,
            User.middle_name,
            Role.name.label('role_name'),
        )
        .select_from(User)
        .join(Role, User.role_id == Role.id, isouter=True)
        .order_by(User.id)
        .all()
    )
    # Передадим в шаблон как список dict для совместимости с текущим index.html
    users_payload = [
        {
            'id': u.id,
            'username': u.username,
            'last_name': u.last_name,
            'first_name': u.first_name,
            'middle_name': u.middle_name,
            'role_name': u.role_name,
        }
        for u in users
    ]
    return render_template('index.html', title='Пользователи', users=users_payload)


@app.route('/users/<int:user_id>')
@check_rights('view_user', allow_self=('view_self', 'user_id'))
def user_view(user_id: int):
    """Просмотр данных пользователя."""
    u = (
        db.session.query(
            User.id,
            User.username,
            User.last_name,
            User.first_name,
            User.middle_name,
            Role.name.label('role_name'),
        )
        .select_from(User)
        .join(Role, User.role_id == Role.id, isouter=True)
        .filter(User.id == user_id)
        .first()
    )
    if u is None:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('index'))
    user = {
        'id': u.id,
        'username': u.username,
        'last_name': u.last_name,
        'first_name': u.first_name,
        'middle_name': u.middle_name,
        'role_name': u.role_name,
    }
    return render_template('user_view.html', title='Просмотр пользователя', user=user)


@app.route('/users/create', methods=['GET', 'POST'])
@check_rights('create_users')
def user_create():
    """Создание пользователя (только для аутентифицированных)."""
    # Данные формы (для повторного рендера при ошибках)
    form = {
        'username': request.form.get('username', ''),
        'password': request.form.get('password', ''),
        'last_name': request.form.get('last_name', ''),
        'first_name': request.form.get('first_name', ''),
        'middle_name': request.form.get('middle_name', ''),
        'role_id': request.form.get('role_id', ''),
    }

    roles = Role.query.order_by(Role.name).all()
    errors = {}
# ----- Обработка POST-запроса (валидация и сохранение) -----
    if request.method == 'POST':
        try:
            import re
            # Обязательные поля
            if not form['username']:
                errors['username'] = 'Поле не может быть пустым.'
            if not form['password']:
                errors['password'] = 'Поле не может быть пустым.'
            if not form['last_name']:
                errors['last_name'] = 'Поле не может быть пустым.'
            if not form['first_name']:
                errors['first_name'] = 'Поле не может быть пустым.'

            # Логин: латиница и цифры, длина >= 5
            if form['username'] and not re.fullmatch(r'[A-Za-z0-9]{5,}', form['username']):
                errors['username'] = 'Логин: только латиница и цифры, не менее 5 символов.'

            # Пароль проверки
            if form['password']:
                pwd = form['password']
                if not (8 <= len(pwd) <= 128):
                    errors['password'] = 'Пароль: длина от 8 до 128 символов.'
                if ' ' in pwd:
                    errors['password'] = 'Пароль: без пробелов.'
                # хотя бы одна строчная и одна заглавная
                if not re.search(r'[a-z]', pwd) or not re.search(r'[A-Z]', pwd):
                    errors['password'] = 'Пароль: хотя бы одна заглавная и одна строчная буква.'
                # хотя бы одна цифра
                if not re.search(r'[0-9]', pwd):
                    errors['password'] = 'Пароль: хотя бы одна цифра.'
                # допустимые символы (латиница/кириллица, цифры и заданные спецсимволы)
                allowed_special = r"~!?@#$%^&*_\-+()\[\]{}></\\|\"'\.,:;"
                allowed_pattern = rf"^[A-Za-zА-Яа-я0-9{allowed_special}]+$"
                if not re.fullmatch(allowed_pattern, pwd):
                    errors['password'] = 'Пароль содержит недопустимые символы.'

            # Уникальность логина
            if form['username'] and User.query.filter_by(username=form['username']).first():
                errors['username'] = 'Пользователь с таким логином уже существует.'

            if errors:
                return render_template('user_create.html', title='Создание пользователя', form=form, roles=roles, errors=errors)

            new_user = User(
                username=form['username'].strip(),
                last_name=form['last_name'].strip() or None,
                first_name=form['first_name'].strip() or None,
                middle_name=form['middle_name'].strip() or None,
                role_id=int(form['role_id']) if form['role_id'] else None,
            )
            new_user.set_password(form['password'])
            db.session.add(new_user)
            db.session.commit()

            flash('Пользователь успешно создан.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return render_template('user_create.html', title='Создание пользователя', form=form, roles=roles, errors=errors)

    return render_template('user_create.html', title='Создание пользователя', form=form, roles=roles, errors=errors)


@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@check_rights('edit_users', allow_self=('edit_self', 'user_id'))
def user_edit(user_id: int):
    """Редактирование пользователя (без логина/пароля)."""
    u = db.session.get(User, user_id)
    if u is None:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('index'))

    roles = Role.query.order_by(Role.name).all()
    errors = {}
    form = {
        'last_name': u.last_name or '',
        'first_name': u.first_name or '',
        'middle_name': u.middle_name or '',
        'role_id': str(u.role_id) if u.role_id else '',
    }

    if request.method == 'POST':
        # Обновляем по входящим данным
        form['last_name'] = request.form.get('last_name', '')
        form['first_name'] = request.form.get('first_name', '')
        form['middle_name'] = request.form.get('middle_name', '')
        form['role_id'] = request.form.get('role_id', '')
        try:
            if not form['last_name']:
                errors['last_name'] = 'Поле не может быть пустым.'
            if not form['first_name']:
                errors['first_name'] = 'Поле не может быть пустым.'
            if errors:
                return render_template('user_edit.html', title='Редактирование пользователя', form=form, roles=roles, user=u, errors=errors)
            u.last_name = form['last_name'].strip() or None
            u.first_name = form['first_name'].strip() or None
            u.middle_name = form['middle_name'].strip() or None
            u.role_id = int(form['role_id']) if form['role_id'] else None
            db.session.commit()
            flash('Данные пользователя обновлены.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return render_template('user_edit.html', title='Редактирование пользователя', form=form, roles=roles, user=u, errors=errors)

    return render_template('user_edit.html', title='Редактирование пользователя', form=form, roles=roles, user=u, errors=errors)


@app.route('/users/<int:user_id>/delete', methods=['POST'])
@check_rights('delete_users')
def user_delete(user_id: int):
    """Удаление пользователя (только для аутентифицированных)."""
    try:
        u = db.session.get(User, user_id)
        if u is None:
            flash('Пользователь не найден.', 'danger')
            return redirect(url_for('index'))
        db.session.delete(u)
        db.session.commit()
        flash('Пользователь удалён.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка удаления: {e}', 'danger')
    return redirect(url_for('index'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Смена пароля текущего пользователя."""
    errors = {}
    form = {
        'old_password': request.form.get('old_password', ''),
        'new_password': request.form.get('new_password', ''),
        'new_password2': request.form.get('new_password2', ''),
    }

    if request.method == 'POST':
        import re
        # Проверка старого пароля
        if not form['old_password']:
            errors['old_password'] = 'Поле не может быть пустым.'
        elif not current_user.check_password(form['old_password']):
            errors['old_password'] = 'Старый пароль указан неверно.'

        # Проверки нового пароля
        pwd = form['new_password']
        if not pwd:
            errors['new_password'] = 'Поле не может быть пустым.'
        else:
            if not (8 <= len(pwd) <= 128):
                errors['new_password'] = 'Пароль: длина от 8 до 128 символов.'
            if ' ' in pwd:
                errors['new_password'] = 'Пароль: без пробелов.'
            if not re.search(r'[a-z]', pwd) or not re.search(r'[A-Z]', pwd):
                errors['new_password'] = 'Пароль: хотя бы одна заглавная и одна строчная буква.'
            if not re.search(r'[0-9]', pwd):
                errors['new_password'] = 'Пароль: хотя бы одна цифра.'
            allowed_special = r"~!?@#$%^&*_\-+()\[\]{}></\\|\"'\.,:;"
            allowed_pattern = rf"^[A-Za-zА-Яа-я0-9{allowed_special}]+$"
            if not re.fullmatch(allowed_pattern, pwd):
                errors['new_password'] = 'Пароль содержит недопустимые символы.'

        # Подтверждение нового пароля
        if not form['new_password2']:
            errors['new_password2'] = 'Поле не может быть пустым.'
        elif form['new_password2'] != form['new_password']:
            errors['new_password2'] = 'Пароли не совпадают.'

        if not errors:
            try:
                u = db.session.get(User, current_user.id)
                u.set_password(form['new_password'])
                db.session.commit()
                flash('Пароль успешно изменён.', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash(str(e), 'danger')

    return render_template('change_password.html', title='Изменить пароль', form=form, errors=errors)
