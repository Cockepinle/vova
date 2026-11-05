from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


from .catalog import Product
class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="cart_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Товар", related_name="cart_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField("Количество", default=1)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Товар в корзине"
        verbose_name_plural = "Корзины пользователей"
        unique_together = ["user", "product"]

    def __str__(self):
        return f"{self.user}: {self.product} × {self.quantity}"

class FavoriteItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="favorite_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Товар", related_name="favorite_items", on_delete=models.CASCADE)
    created_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "Избранный товар"
        verbose_name_plural = "Избранное пользователей"
        unique_together = ["user", "product"]

    def __str__(self):
        return f"{self.user}: {self.product}"
