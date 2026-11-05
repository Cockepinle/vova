from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class CustomerProfile(models.Model):
    PRICE_RETAIL = "retail"
    PRICE_WHOLESALE = "wholesale"
    PRICE_SPECIAL = "special"
    PRICE_LEVEL_CHOICES = [
        (PRICE_RETAIL, "Розничная"),
        (PRICE_WHOLESALE, "Оптовая"),
        (PRICE_SPECIAL, "Специальная"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="customer_profile", on_delete=models.CASCADE)
    company = models.CharField("Компания", max_length=180, blank=True)
    phone = models.CharField("Телефон", max_length=80, blank=True)
    price_level = models.CharField("Уровень цен", max_length=20, choices=PRICE_LEVEL_CHOICES, default=PRICE_RETAIL)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль клиента"
        verbose_name_plural = "Профили клиентов"

    def __str__(self):
        return self.user.email or self.user.username

class ExternalIdentity(models.Model):
    """Provider-neutral link for a future OAuth/social-login integration."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="external_identities", on_delete=models.CASCADE)
    provider = models.SlugField("Провайдер", max_length=80)
    subject = models.CharField("Идентификатор у провайдера", max_length=255)
    email = models.EmailField("Email у провайдера", blank=True)
    data = models.JSONField("Профиль провайдера", default=dict, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Внешняя учётная запись"
        verbose_name_plural = "Внешние учётные записи"
        constraints = [models.UniqueConstraint(fields=["provider", "subject"], name="unique_external_identity")]

    def __str__(self):
        return f"{self.provider}: {self.subject}"

class EmailVerificationCode(models.Model):
    email = models.EmailField("Email")
    code = models.CharField("Код", max_length=6)
    payload = models.JSONField("Данные регистрации", default=dict)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    is_used = models.BooleanField("Использован", default=False)

    class Meta:
        verbose_name = "Код подтверждения email"
        verbose_name_plural = "Коды подтверждения email"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} · {self.code}"

class AdminLoginThrottleBucket(models.Model):
    key_hash = models.CharField("Хеш ключа ограничения", max_length=64, unique=True)
    failure_count = models.PositiveSmallIntegerField("Неудачные попытки", default=0)
    window_started_at = models.DateTimeField("Начало окна попыток")
    locked_until = models.DateTimeField("Блокировка до", null=True, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Счётчик попыток входа в админку"
        verbose_name_plural = "Счётчики попыток входа в админку"

class AdminLoginAttempt(models.Model):
    OUTCOME_SUCCESS = "success"
    OUTCOME_FAILURE = "failure"
    OUTCOME_BLOCKED = "blocked"
    OUTCOME_CHOICES = [
        (OUTCOME_SUCCESS, "Успешный вход"),
        (OUTCOME_FAILURE, "Неудачный вход"),
        (OUTCOME_BLOCKED, "Заблокированная попытка"),
    ]

    username = models.CharField("Логин", max_length=254, blank=True)
    remote_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    outcome = models.CharField("Результат", max_length=12, choices=OUTCOME_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Учетная запись",
        related_name="admin_login_attempts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("Время попытки", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Попытка входа в админку"
        verbose_name_plural = "Журнал входов в админку"
        ordering = ["-created_at"]

class Employee(models.Model):
    STATUS_PUBLISHED = "published"
    STATUS_DRAFT = "draft"
    STATUS_HIDDEN = "hidden"

    STATUS_CHOICES = [
        (STATUS_PUBLISHED, "Опубликовано"),
        (STATUS_DRAFT, "Черновик"),
        (STATUS_HIDDEN, "Скрыто"),
    ]

    name = models.CharField("Имя", max_length=160)
    role = models.CharField("Должность", max_length=160)
    text = models.TextField("Описание", blank=True)
    image = models.ImageField("Фото", upload_to="employees/", blank=True)
    image_url = models.URLField("Ссылка на фото", blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Телефон", max_length=80, blank=True)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url

        return self.image_url
