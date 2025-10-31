from marshmallow import Schema, fields, validate, ValidationError
import re

class UserRegistrationSchema(Schema):
    """Схема валидации для регистрации пользователя"""
    surname = fields.Str(required=True, validate=[
        validate.Length(min=1, max=25, error="Фамилия должна быть от 1 до 25 символов"),
        validate.Regexp(r'^[а-яА-Яa-zA-Z\s-]+$', error="Фамилия может содержать только буквы, пробелы и дефисы")
    ])
    name = fields.Str(required=True, validate=[
        validate.Length(min=1, max=25, error="Имя должно быть от 1 до 25 символов"),
        validate.Regexp(r'^[а-яА-Яa-zA-Z\s-]+$', error="Имя может содержать только буквы, пробелы и дефисы")
    ])
    patronymic = fields.Str(validate=[
        validate.Length(max=25, error="Отчество не должно превышать 25 символов"),
        validate.Regexp(r'^[а-яА-Яa-zA-Z\s-]*$', error="Отчество может содержать только буквы, пробелы и дефисы")
    ])
    email = fields.Email(required=True, validate=[
        validate.Length(max=100, error="Email не должен превышать 100 символов")
    ])
    password = fields.Str(required=True, validate=[
        validate.Length(min=4, error="Пароль должен содержать минимум 4 символа")
    ])

class UserLoginSchema(Schema):
    """Схема валидации для входа пользователя: допускает любой логин (не обязательно email)"""
    email = fields.Str(required=True, validate=validate.Length(min=1))
    password = fields.Str(required=True, validate=validate.Length(min=1))

class UserUpdateSchema(Schema):
    """Схема валидации для обновления данных пользователя"""
    age = fields.Int(validate=validate.Range(min=1, max=120, error="Возраст должен быть от 1 до 120 лет"))
    height = fields.Int(validate=validate.Range(min=50, max=250, error="Рост должен быть от 50 до 250 см"))
    weight = fields.Int(validate=validate.Range(min=20, max=300, error="Вес должен быть от 20 до 300 кг"))
    firstName = fields.Str(validate=[
        validate.Length(min=1, max=25, error="Имя должно быть от 1 до 25 символов"),
        validate.Regexp(r'^[а-яА-Яa-zA-Z\s-]+$', error="Имя может содержать только буквы, пробелы и дефисы")
    ])
    lastName = fields.Str(validate=[
        validate.Length(min=1, max=25, error="Фамилия должна быть от 1 до 25 символов"),
        validate.Regexp(r'^[а-яА-Яa-zA-Z\s-]+$', error="Фамилия может содержать только буквы, пробелы и дефисы")
    ])
    email = fields.Email(validate=[
        validate.Length(max=100, error="Email не должен превышать 100 символов")
    ])
    password = fields.Str(validate=[
        validate.Length(min=4, error="Пароль должен содержать минимум 4 символа")
    ])

class ActivitySchema(Schema):
    """Схема валидации для создания активности"""
    startTime = fields.Str(required=True, validate=[
        validate.Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', error="Время должно быть в формате HH:MM")
    ])
    type = fields.Str(required=True, validate=[
        validate.Length(min=1, max=50, error="Тип активности должен быть от 1 до 50 символов")
    ])
    startDate = fields.Str(required=True, validate=[
        validate.Regexp(r'^\d{4}-\d{2}-\d{2}$', error="Дата должна быть в формате YYYY-MM-DD")
    ])
    duration = fields.Str(validate=[
        validate.Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', error="Длительность должна быть в формате HH:MM")
    ])
    distance = fields.Float(validate=validate.Range(min=0, max=10000, error="Расстояние должно быть от 0 до 10000"))
    step = fields.Int(validate=validate.Range(min=0, max=100000, error="Количество шагов должно быть от 0 до 100000"))
    description = fields.Str(validate=validate.Length(max=500, error="Описание не должно превышать 500 символов"))
    verification = fields.Str(validate=validate.Length(max=1000, error="Доказательство не должно превышать 1000 символов"))
    other = fields.Str(validate=validate.Length(max=100, error="Другая активность не должна превышать 100 символов"))

class WeightGoalSchema(Schema):
    """Схема валидации для установки цели по весу"""
    target_weight = fields.Int(required=True, validate=validate.Range(min=20, max=300, error="Целевой вес должен быть от 20 до 300 кг"))
    weight = fields.Int(required=True, validate=validate.Range(min=20, max=300, error="Текущий вес должен быть от 20 до 300 кг"))

def validate_json_data(schema_class, data):
    """Валидация JSON данных по схеме"""
    try:
        schema = schema_class()
        result = schema.load(data)
        return result, None
    except ValidationError as err:
        return None, err.messages
    except Exception as e:
        return None, {"error": f"Ошибка валидации: {str(e)}"}

def sanitize_string(value):
    """Очистка строки от потенциально опасных символов"""
    if not isinstance(value, str):
        return value
    
    import re
    value = re.sub(r'<[^>]+>', '', value)
    
    value = re.sub(r'[<>"\';\\]', '', value)
    
    return value.strip()


class AdminUserCreateSchema(Schema):
    surname = fields.Str(required=True, validate=validate.Length(min=1, max=25))
    name = fields.Str(required=True, validate=validate.Length(min=1, max=25))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=4))
    role = fields.Str(validate=validate.OneOf(['user', 'moderator', 'admin']))
    is_active = fields.Bool(missing=True)


class AdminUserUpdateSchema(Schema):
    surname = fields.Str(validate=validate.Length(min=1, max=25))
    name = fields.Str(validate=validate.Length(min=1, max=25))
    email = fields.Email()
    role = fields.Str(validate=validate.OneOf(['user', 'moderator', 'admin']))
    is_active = fields.Bool()
    banned_until = fields.DateTime(allow_none=True)


class AdminUserStatusSchema(Schema):
    is_active = fields.Bool(required=True)
    banned_until = fields.DateTime(allow_none=True)


class AdminUserRoleSchema(Schema):
    role = fields.Str(required=True, validate=validate.OneOf(['user', 'moderator', 'admin']))


class AdminChallengeSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    points = fields.Int(validate=validate.Range(min=0))
    description = fields.Str(allow_none=True)
    start_at = fields.DateTime(allow_none=True)
    end_at = fields.DateTime(allow_none=True)
    status = fields.Str(validate=validate.OneOf(['draft', 'active', 'archived']))
    league = fields.Str(allow_none=True)
    cover_image = fields.Str(allow_none=True)


class AdminChallengeStatusSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf(['draft', 'active', 'archived']))


class AdminPostStatusSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf(['visible', 'hidden', 'deleted']))


class AdminPostEditSchema(Schema):
    """Схема для редактирования поста админом"""
    activity_id = fields.Int(validate=validate.Range(min=0, max=100))
    distance = fields.Float(validate=validate.Range(min=0, max=10000))
    duration = fields.Str(validate=validate.Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', error="Формат HH:MM"))
    calories = fields.Int(validate=validate.Range(min=0, max=100000))
    points = fields.Int(validate=validate.Range(min=0, max=100000))
    steps = fields.Int(validate=validate.Range(min=0, max=100000))
    description = fields.Str(validate=validate.Length(max=500))
    status = fields.Str(validate=validate.OneOf(['visible', 'hidden']))


class AdminCommentStatusSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf(['visible', 'hidden', 'deleted']))


class AdminSettingsSchema(Schema):
    app_theme = fields.Str(allow_none=True)
    uploads_max_size_mb = fields.Int(validate=validate.Range(min=1, max=1000), allow_none=True)
    maintenance_mode = fields.Bool(allow_none=True)
    welcome_banner_text = fields.Str(allow_none=True)
    goal_target_km = fields.Int(validate=validate.Range(min=0), allow_none=True)
    rating_weights = fields.Dict(allow_none=True)
    features = fields.Dict(allow_none=True)


class AdminFeatureFlagsSchema(Schema):
    flags = fields.Dict(keys=fields.Str(), values=fields.Bool(), required=True)


class AdminErrorStatusSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf(['open', 'in_progress', 'resolved']))


class AdminRecalculateSchema(Schema):
    scope = fields.Str(required=True, validate=validate.OneOf(['participants', 'teams', 'all']))
    from_date = fields.DateTime(allow_none=True)
    to_date = fields.DateTime(allow_none=True)


class ChangePasswordSchema(Schema):
    oldPassword = fields.Str(required=True, validate=validate.Length(min=1))
    newPassword = fields.Str(required=True, validate=validate.Length(min=4))
    confirmPassword = fields.Str(required=True, validate=validate.Length(min=4))
