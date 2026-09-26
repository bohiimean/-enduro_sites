"""Каталог байков.

На переходный период мастером остаётся Google Sheets: Django импортирует лист
односторонне, редактирование в админке включается в день переключения мастера
(CLAUDE.md, «Каталог: переходный период»). `external_key` существует ради
идемпотентности этого импорта — по нему строка листа находит свою запись.
"""
from django.db import models
from django.utils.text import slugify


class Brand(models.Model):
    name = models.CharField("марка", max_length=100, unique=True)
    slug = models.SlugField("адрес", max_length=120, unique=True, blank=True)
    sort = models.PositiveIntegerField("порядок", default=0)
    is_active = models.BooleanField("активна", default=True)

    class Meta:
        verbose_name = "марка"
        verbose_name_plural = "марки"
        ordering = ["sort", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=False) or "brand"
        super().save(*args, **kwargs)


class Product(models.Model):
    brand = models.ForeignKey(
        Brand, verbose_name="марка", on_delete=models.PROTECT, related_name="products"
    )
    model = models.CharField("модель", max_length=150)
    color = models.CharField("цвет", max_length=80, blank=True)
    price = models.DecimalField("цена, ₽", max_digits=12, decimal_places=2, null=True, blank=True)
    description = models.TextField("описание", blank=True)
    in_stock = models.BooleanField("в наличии", default=True)
    is_published = models.BooleanField("опубликован", default=True)
    slug = models.SlugField("адрес", max_length=200, unique=True, blank=True)
    sort = models.PositiveIntegerField("порядок", default=0)
    # Ключ строки исходного листа — для идемпотентного импорта (этап 6).
    external_key = models.CharField("ключ импорта", max_length=120, blank=True, db_index=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "байк"
        verbose_name_plural = "байки"
        ordering = ["sort", "-created_at"]
        indexes = [models.Index(fields=["is_published", "in_stock"])]

    def __str__(self) -> str:
        parts = [self.brand.name, self.model]
        if self.color:
            parts.append(f"— {self.color}")
        return " ".join(parts)

    @property
    def title(self) -> str:
        return f"{self.brand.name} {self.model}".strip()

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.brand.name}-{self.model}-{self.color}".strip("-"))
            slug, n = base or "bike", 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)


class ProductPhoto(models.Model):
    product = models.ForeignKey(
        Product, verbose_name="байк", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("файл", upload_to="catalog/%Y/%m")
    # Откуда приехало при импорте (ссылка на Google Drive) — чтобы не тянуть
    # один и тот же файл повторно.
    source_url = models.URLField("источник", max_length=500, blank=True)
    sort = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "фото"
        verbose_name_plural = "фото"
        ordering = ["sort", "id"]

    def __str__(self) -> str:
        return f"Фото {self.product}"
