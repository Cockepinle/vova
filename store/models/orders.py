from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


from .catalog import Product
class PaymentMethod(models.Model):
    KIND_INVOICE = "invoice"
    KIND_ONLINE = "online"
    KIND_CHOICES = [(KIND_INVOICE, "Счёт"), (KIND_ONLINE, "Онлайн-оплата")]

    code = models.SlugField("Код", max_length=50, unique=True)
    name = models.CharField("Название", max_length=120)
    kind = models.CharField("Тип", max_length=20, choices=KIND_CHOICES)
    provider_code = models.CharField("Код платёжного провайдера", max_length=80, blank=True)
    is_active = models.BooleanField("Доступен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Способ оплаты"
        verbose_name_plural = "Способы оплаты"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

class DeliveryMethod(models.Model):
    KIND_CARRIER = "carrier"
    KIND_OWN = "own"
    KIND_PICKUP = "pickup"
    KIND_CUSTOM = "custom"
    KIND_CHOICES = [
        (KIND_CARRIER, "Транспортная компания"),
        (KIND_OWN, "Собственная доставка"),
        (KIND_PICKUP, "Самовывоз"),
        (KIND_CUSTOM, "Другой способ"),
    ]

    code = models.SlugField("Код", max_length=50, unique=True)
    name = models.CharField("Название", max_length=120)
    kind = models.CharField("Тип доставки", max_length=20, choices=KIND_CHOICES, default=KIND_CARRIER)
    description = models.CharField("Описание", max_length=240, blank=True)
    provider_code = models.SlugField("Код delivery provider", max_length=80, blank=True)
    handoff_url = models.URLField("Ссылка на сервис перевозчика", blank=True)
    provider_config = models.JSONField("Параметры delivery provider", default=dict, blank=True)
    is_active = models.BooleanField("Доступен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Способ доставки"
        verbose_name_plural = "Способы доставки"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_NEW = "new"
    STATUS_CHECKOUT_STARTED = "checkout_started"
    STATUS_PENDING_PAYMENT = "pending_payment"
    STATUS_AWAITING_INVOICE = "awaiting_invoice"
    STATUS_ABANDONED = "abandoned"
    STATUS_PROCESSING = "processing"
    STATUS_INVOICED = "invoiced"
    STATUS_PAID = "paid"
    STATUS_DONE = "done"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новый"),
        (STATUS_CHECKOUT_STARTED, "Оформление начато"),
        (STATUS_PENDING_PAYMENT, "Ожидает оплаты"),
        (STATUS_AWAITING_INVOICE, "Ожидает счёт"),
        (STATUS_ABANDONED, "Брошен"),
        (STATUS_PROCESSING, "В обработке"),
        (STATUS_INVOICED, "Счёт выставлен"),
        (STATUS_PAID, "Оплачен"),
        (STATUS_DONE, "Выполнен"),
        (STATUS_CANCELED, "Отменён"),
    ]
    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_CANCELLED = "cancelled"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Ожидает оплаты"),
        (PAYMENT_PAID, "Оплачен"),
        (PAYMENT_FAILED, "Ошибка оплаты"),
        (PAYMENT_CANCELLED, "Отменён"),
        (PAYMENT_REFUNDED, "Возвращён"),
    ]

    number = models.CharField("Номер заказа", max_length=32, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="orders", on_delete=models.PROTECT)
    full_name = models.CharField("ФИО", max_length=180)
    phone = models.CharField("Телефон", max_length=80)
    email = models.EmailField("Email")
    company = models.CharField("Компания", max_length=180, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    total = models.DecimalField("Итого", max_digits=14, decimal_places=2, default=0)
    stored_total_weight_kg = models.DecimalField("Общий вес на момент заказа, кг", max_digits=18, decimal_places=3, null=True, blank=True)
    stored_total_volume_m3 = models.DecimalField("Общий объём на момент заказа, м³", max_digits=36, decimal_places=15, null=True, blank=True)
    payment_method = models.ForeignKey(PaymentMethod, verbose_name="Способ оплаты", related_name="orders", on_delete=models.PROTECT, null=True, blank=True)
    payment_method_name = models.CharField("Способ оплаты на момент заказа", max_length=120, blank=True)
    payment_status = models.CharField("Статус оплаты", max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    delivery_method = models.ForeignKey(DeliveryMethod, verbose_name="Способ доставки", related_name="orders", on_delete=models.PROTECT, null=True, blank=True)
    delivery_method_name = models.CharField("Способ доставки на момент заказа", max_length=120, blank=True)
    delivery_method_kind = models.CharField("Тип доставки на момент заказа", max_length=20, blank=True)
    delivery_provider_code = models.CharField("Delivery provider на момент заказа", max_length=80, blank=True)
    delivery_origin_address = models.CharField("Адрес отправления на момент заказа", max_length=500, blank=True)
    delivery_address = models.CharField("Адрес получения", max_length=500, blank=True)
    delivery_handoff_url = models.URLField("Ссылка на сервис перевозчика", blank=True)
    delivery_provider_data = models.JSONField("Данные для delivery provider", default=dict, blank=True)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Заказ #{self.pk}"

    def save(self, *args, **kwargs):
        from django.db import transaction
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            previous = Order.objects.using(using).select_for_update().filter(pk=self.pk).values_list("status", flat=True).first() if self.pk else None
            super().save(*args, **kwargs)
            if not self.number:
                self.number = f"PL-{self.created_at:%Y%m%d}-{self.pk:05d}"
                super().save(update_fields=["number"], using=using)
            status_saved = kwargs.get("update_fields") is None or "status" in kwargs["update_fields"]
            if previous is None or (status_saved and previous != self.status):
                OrderStatusHistory.objects.using(using).create(order=self, status=self.status)

    def _delivery_total(self, field):
        items = list(self.items.all())
        if any(getattr(item, field) is None for item in items):
            return None
        return sum((getattr(item, field) * item.quantity for item in items), Decimal("0"))

    @property
    def total_weight_kg(self):
        return self.stored_total_weight_kg if self.stored_total_weight_kg is not None else self._delivery_total("weight_kg")

    @property
    def total_volume_m3(self):
        return self.stored_total_volume_m3 if self.stored_total_volume_m3 is not None else self._delivery_total("volume_m3")

    def get_delivery_method_kind_display(self):
        return dict(DeliveryMethod.KIND_CHOICES).get(self.delivery_method_kind, self.delivery_method_kind)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name="Заказ", related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Товар", related_name="order_items", on_delete=models.PROTECT)
    product_name = models.CharField("Название товара на момент заказа", max_length=220)
    product_sku = models.CharField("Артикул на момент заказа", max_length=80, blank=True)
    unit = models.CharField("Единица измерения", max_length=40, blank=True)
    quantity = models.PositiveIntegerField("Количество")
    price = models.DecimalField("Цена на момент заказа", max_digits=12, decimal_places=2)
    line_total = models.DecimalField("Сумма позиции", max_digits=14, decimal_places=2)
    vat_rate = models.DecimalField("НДС на момент заказа, %", max_digits=5, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField("Вес единицы на момент заказа, кг", max_digits=12, decimal_places=3, null=True, blank=True)
    volume_m3 = models.DecimalField("Объём единицы на момент заказа, м³", max_digits=36, decimal_places=15, null=True, blank=True)
    length_mm = models.DecimalField("Длина единицы на момент заказа, мм", max_digits=10, decimal_places=2, null=True, blank=True)
    width_mm = models.DecimalField("Ширина единицы на момент заказа, мм", max_digits=10, decimal_places=2, null=True, blank=True)
    height_mm = models.DecimalField("Высота единицы на момент заказа, мм", max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

class Payment(models.Model):
    STATUS_CHOICES = Order.PAYMENT_STATUS_CHOICES
    order = models.ForeignKey(Order, verbose_name="Заказ", related_name="payments", on_delete=models.PROTECT)
    payment_method = models.ForeignKey(PaymentMethod, verbose_name="Способ оплаты", related_name="payments", on_delete=models.PROTECT)
    provider_code = models.CharField("Провайдер", max_length=80, blank=True)
    external_id = models.CharField("Идентификатор у провайдера", max_length=160, blank=True, db_index=True)
    idempotency_key = models.CharField("Ключ идемпотентности", max_length=64, unique=True)
    amount = models.DecimalField("Сумма", max_digits=14, decimal_places=2)
    currency = models.CharField("Валюта", max_length=3, default="RUB")
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=Order.PAYMENT_PENDING)
    payment_url = models.URLField("Ссылка на оплату", blank=True)
    provider_data = models.JSONField("Данные провайдера", default=dict, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider_code", "external_id"], condition=~models.Q(external_id=""), name="unique_provider_external_payment")]

    def __str__(self):
        return f"{self.order} — {self.amount} {self.currency}"

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, verbose_name="Заказ", related_name="status_history", on_delete=models.CASCADE)
    status = models.CharField("Статус", max_length=20, choices=Order.STATUS_CHOICES)
    created_at = models.DateTimeField("Дата изменения", auto_now_add=True)

    class Meta:
        verbose_name = "Изменение статуса заказа"
        verbose_name_plural = "История статусов заказов"
        ordering = ["created_at", "pk"]

class CustomerRequest(models.Model):
    STATUS_NEW = "new"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новая"),
        (STATUS_PROCESSING, "В работе"),
        (STATUS_DONE, "Закрыта"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="requests", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField("Имя", max_length=160)
    company = models.CharField("Компания", max_length=180, blank=True)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=80, blank=True)
    text = models.TextField("Что нужно")
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} · {self.email}"
