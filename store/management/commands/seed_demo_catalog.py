from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from store.models import Category, PageContent, Product, SiteSettings


BOX_PHOTO = (
    "https://images.unsplash.com/photo-1494412519320-aa613dfb7738"
    "?auto=format&fit=crop&w=900&q=80"
)
WAREHOUSE_PHOTO = (
    "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d"
    "?auto=format&fit=crop&w=1200&q=80"
)
PACKING_PHOTO = (
    "https://images.unsplash.com/photo-1558060370-d644479cb6f7"
    "?auto=format&fit=crop&w=900&q=80"
)
MARKETPLACE_PHOTO = (
    "https://images.unsplash.com/photo-1494412519320-aa613dfb7738"
    "?auto=format&fit=crop&w=900&q=80"
)
ARCHIVE_PHOTO = (
    "https://images.unsplash.com/photo-1618354691373-d851c5c3a990"
    "?auto=format&fit=crop&w=900&q=80"
)

CATEGORY_DATA = [
    {
        "slug": "corrugated-boxes",
        "legacy_slug": "картон",
        "name": "Коробки из гофрокартона",
        "description": "Демонстрационные короба из трех- и пятислойного гофрокартона.",
        "image_url": BOX_PHOTO,
        "children": [
            {
                "slug": "three-layer-boxes",
                "legacy_slug": "картон-копия",
                "name": "Трехслойные короба",
                "description": "Типовые коробки для легких и средних грузов.",
                "image_url": BOX_PHOTO,
            },
            {
                "slug": "five-layer-boxes",
                "name": "Пятислойные короба",
                "description": "Примеры усиленных коробок для более тяжелых грузов.",
                "image_url": WAREHOUSE_PHOTO,
            },
        ],
    },
    {
        "slug": "postal-boxes",
        "name": "Почтовые коробки",
        "description": "Коробки для отправлений, интернет-магазинов и маркетплейсов.",
        "image_url": MARKETPLACE_PHOTO,
        "children": [
            {
                "slug": "self-assembly-postal-boxes",
                "name": "Самосборные коробки",
                "description": "Примеры коробок, которые собираются без отдельной крышки.",
                "image_url": BOX_PHOTO,
            },
            {
                "slug": "marketplace-boxes",
                "name": "Для маркетплейсов",
                "description": "Демонстрационные размеры для отправки заказов.",
                "image_url": MARKETPLACE_PHOTO,
            },
        ],
    },
    {
        "slug": "moving-boxes",
        "name": "Коробки для переезда",
        "description": "Короба для вещей, книг и бытовых предметов.",
        "image_url": WAREHOUSE_PHOTO,
        "children": [
            {
                "slug": "book-moving-boxes",
                "name": "Для книг и вещей",
                "description": "Небольшие и универсальные короба для переезда.",
                "image_url": BOX_PHOTO,
            },
            {
                "slug": "wardrobe-moving-boxes",
                "name": "Гардеробные",
                "description": "Пример высокого короба для одежды.",
                "image_url": WAREHOUSE_PHOTO,
            },
        ],
    },
    {
        "slug": "archive-boxes",
        "name": "Архивные коробки",
        "description": "Примеры коробок для хранения документов и папок.",
        "image_url": ARCHIVE_PHOTO,
        "children": [
            {
                "slug": "document-boxes",
                "name": "Для документов",
                "description": "Короба для документов и папок стандартного формата.",
                "image_url": ARCHIVE_PHOTO,
            },
            {
                "slug": "archive-storage-boxes",
                "name": "Для длительного хранения",
                "description": "Коробки для систематизации архивных материалов.",
                "image_url": BOX_PHOTO,
            },
        ],
    },
    {
        "slug": "boxes-with-lids",
        "name": "Коробки с крышкой",
        "description": "Коробки с отдельной крышкой для хранения и подарочной упаковки.",
        "image_url": PACKING_PHOTO,
        "children": [
            {
                "slug": "gift-boxes",
                "name": "Подарочные",
                "description": "Демонстрационные коробки для комплектов и подарков.",
                "image_url": PACKING_PHOTO,
            },
            {
                "slug": "storage-boxes-with-lid",
                "name": "Для хранения",
                "description": "Короба с крышкой для хранения товаров и комплектующих.",
                "image_url": BOX_PHOTO,
            },
        ],
    },
]

PRODUCT_DATA = [
    {
        "sku": "DEMO-3L-151010",
        "slug": "box-150-100-100-three-layer",
        "category": "three-layer-boxes",
        "name": "Коробка 150 × 100 × 100 мм, 3 слоя",
        "description": "Компактный демонстрационный короб для небольших отправлений и комплектующих.",
        "price": "24.00",
        "image_url": BOX_PHOTO,
        "dimensions": (150, 100, 100),
        "min_quantity": 20,
        "is_hit": True,
    },
    {
        "sku": "DEMO-3L-302015",
        "slug": "box-300-200-150-three-layer",
        "category": "three-layer-boxes",
        "name": "Коробка 300 × 200 × 150 мм, 3 слоя",
        "description": "Демонстрационный средний формат для товаров интернет-магазина.",
        "price": "38.00",
        "image_url": MARKETPLACE_PHOTO,
        "dimensions": (300, 200, 150),
        "min_quantity": 20,
        "is_new": True,
    },
    {
        "sku": "DEMO-5L-403030",
        "slug": "box-400-300-300-five-layer",
        "category": "five-layer-boxes",
        "name": "Усиленная коробка 400 × 300 × 300 мм",
        "description": "Демонстрационный короб из пятислойного гофрокартона для более тяжелых отправлений.",
        "price": "98.00",
        "image_url": WAREHOUSE_PHOTO,
        "dimensions": (400, 300, 300),
        "min_quantity": 10,
        "is_hit": True,
    },
    {
        "sku": "DEMO-POST-201510",
        "slug": "postal-box-200-150-100",
        "category": "self-assembly-postal-boxes",
        "name": "Самосборная коробка 200 × 150 × 100 мм",
        "description": "Небольшая почтовая коробка для аксессуаров и компактных товаров.",
        "price": "28.00",
        "image_url": BOX_PHOTO,
        "dimensions": (200, 150, 100),
        "min_quantity": 20,
    },
    {
        "sku": "DEMO-POST-302010",
        "slug": "postal-box-300-200-100",
        "category": "self-assembly-postal-boxes",
        "name": "Самосборная коробка 300 × 200 × 100 мм",
        "description": "Демонстрационный формат для одежды, книг и небольших заказов.",
        "price": "39.00",
        "image_url": MARKETPLACE_PHOTO,
        "dimensions": (300, 200, 100),
        "min_quantity": 20,
        "is_new": True,
    },
    {
        "sku": "DEMO-MP-403020",
        "slug": "marketplace-box-400-300-200",
        "category": "marketplace-boxes",
        "name": "Коробка для отправлений 400 × 300 × 200 мм",
        "description": "Пример универсальной коробки для комплектации заказов.",
        "price": "76.00",
        "image_url": WAREHOUSE_PHOTO,
        "dimensions": (400, 300, 200),
        "min_quantity": 10,
        "is_hit": True,
    },
    {
        "sku": "DEMO-MOVE-403030",
        "slug": "moving-box-400-300-300",
        "category": "book-moving-boxes",
        "name": "Коробка для книг 400 × 300 × 300 мм",
        "description": "Демонстрационный формат для книг, посуды и бытовых вещей.",
        "price": "92.00",
        "image_url": BOX_PHOTO,
        "dimensions": (400, 300, 300),
        "min_quantity": 10,
    },
    {
        "sku": "DEMO-MOVE-604040",
        "slug": "moving-box-600-400-400",
        "category": "book-moving-boxes",
        "name": "Универсальная коробка 600 × 400 × 400 мм",
        "description": "Крупный демонстрационный короб для переезда и хранения.",
        "price": "180.00",
        "image_url": WAREHOUSE_PHOTO,
        "dimensions": (600, 400, 400),
        "min_quantity": 10,
        "is_hit": True,
    },
    {
        "sku": "DEMO-MOVE-WARDROBE",
        "slug": "wardrobe-box-500-500-1000",
        "category": "wardrobe-moving-boxes",
        "name": "Гардеробная коробка 500 × 500 × 1000 мм",
        "description": "Демонстрационный высокий короб для транспортировки одежды.",
        "price": "390.00",
        "image_url": PACKING_PHOTO,
        "dimensions": (500, 500, 1000),
        "min_quantity": 5,
        "is_new": True,
    },
    {
        "sku": "DEMO-ARCH-332515",
        "slug": "archive-box-330-250-150",
        "category": "document-boxes",
        "name": "Архивный короб 330 × 250 × 150 мм",
        "description": "Короб для хранения бумаг, папок и офисных документов.",
        "price": "42.00",
        "image_url": ARCHIVE_PHOTO,
        "dimensions": (330, 250, 150),
        "min_quantity": 10,
    },
    {
        "sku": "DEMO-ARCH-332535",
        "slug": "archive-box-330-250-350",
        "category": "document-boxes",
        "name": "Архивный короб 330 × 250 × 350 мм",
        "description": "Увеличенный демонстрационный формат для документов и папок.",
        "price": "78.00",
        "image_url": BOX_PHOTO,
        "dimensions": (330, 250, 350),
        "min_quantity": 10,
        "is_new": True,
    },
    {
        "sku": "DEMO-ARCH-LID",
        "slug": "archive-storage-box-with-lid",
        "category": "archive-storage-boxes",
        "name": "Короб для хранения с крышкой",
        "description": "Демонстрационная коробка с крышкой для систематизации документов и небольших предметов.",
        "price": "125.00",
        "image_url": ARCHIVE_PHOTO,
        "dimensions": (350, 260, 200),
        "min_quantity": 10,
        "is_hit": True,
    },
    {
        "sku": "DEMO-GIFT-201508",
        "slug": "gift-box-200-150-80",
        "category": "gift-boxes",
        "name": "Подарочная коробка 200 × 150 × 80 мм",
        "description": "Пример коробки с крышкой для подарочных наборов и небольших комплектов.",
        "price": "115.00",
        "image_url": PACKING_PHOTO,
        "dimensions": (200, 150, 80),
        "min_quantity": 10,
    },
    {
        "sku": "DEMO-GIFT-302010",
        "slug": "gift-box-300-200-100",
        "category": "gift-boxes",
        "name": "Подарочная коробка 300 × 200 × 100 мм",
        "description": "Демонстрационный размер для наборов, сувениров и корпоративных подарков.",
        "price": "245.00",
        "image_url": MARKETPLACE_PHOTO,
        "dimensions": (300, 200, 100),
        "min_quantity": 10,
        "is_new": True,
    },
    {
        "sku": "DEMO-STORAGE-302020",
        "slug": "storage-box-with-lid-300-200-200",
        "category": "storage-boxes-with-lid",
        "name": "Коробка для хранения 300 × 200 × 200 мм",
        "description": "Коробка с отдельной крышкой для хранения товаров и комплектующих.",
        "price": "160.00",
        "image_url": BOX_PHOTO,
        "dimensions": (300, 200, 200),
        "min_quantity": 10,
        "is_hit": True,
    },
]


class Command(BaseCommand):
    help = "Добавить демонстрационные категории и товары для оптового каталога коробок."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}

        for root_data in CATEGORY_DATA:
            root = self.save_category(root_data, None)
            categories[root.slug] = root
            for child_data in root_data["children"]:
                child = self.save_category(child_data, root)
                categories[child.slug] = child

        for item in PRODUCT_DATA:
            length, width, height = item["dimensions"]
            Product.objects.update_or_create(
                sku=item["sku"],
                defaults={
                    "slug": item["slug"],
                    "category": categories[item["category"]],
                    "name": item["name"],
                    "description": (
                        f'{item["description"]} Демонстрационная позиция: '
                        "стоимость и параметры необходимо подтвердить перед заказом."
                    ),
                    "keywords": "картонная коробка, гофрокороб, опт, демонстрационный товар",
                    "price": Decimal(item["price"]),
                    "unit": "шт",
                    "min_quantity": item["min_quantity"],
                    "stock_quantity": 0,
                    "availability": Product.AVAILABILITY_PREORDER,
                    "status": Product.STATUS_PUBLISHED,
                    "image_url": item["image_url"],
                    "length_mm": Decimal(length),
                    "width_mm": Decimal(width),
                    "height_mm": Decimal(height),
                    "is_hit": item.get("is_hit", False),
                    "is_new": item.get("is_new", False),
                    "is_special": False,
                },
            )

        self.update_site_content()
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: {len(CATEGORY_DATA)} категорий, "
                f"{sum(len(item['children']) for item in CATEGORY_DATA)} подкатегорий "
                f"и {len(PRODUCT_DATA)} демонстрационных товаров."
            )
        )

    @staticmethod
    def save_category(data, parent):
        category = Category.objects.filter(slug=data["slug"]).first()
        if category is None and data.get("legacy_slug"):
            category = Category.objects.filter(slug=data["legacy_slug"]).first()
        if category is None:
            category = Category(slug=data["slug"])

        category.name = data["name"]
        category.slug = data["slug"]
        category.parent = parent
        category.description = data["description"]
        category.image_url = data["image_url"]
        category.is_active = True
        category.save()
        return category

    @staticmethod
    def update_site_content():
        settings = SiteSettings.objects.order_by("pk").first()
        if settings is None:
            settings = SiteSettings()

        settings.home_hero_label = "Оптовые поставки картонных коробок"
        settings.home_hero_title = "Картонные коробки для бизнеса"
        settings.home_hero_subtitle = (
            "Короба для отправлений, переезда, хранения и маркетплейсов. "
            "Каталог содержит демонстрационные товары и цены — уточняйте "
            "характеристики и условия перед заказом."
        )
        settings.catalog_title = "Коробки оптом"
        settings.catalog_subtitle = (
            "Демонстрационные размеры и цены. Подтвердите параметры, наличие "
            "и стоимость перед оформлением заказа."
        )
        settings.team_hero_label = "Упаковка для бизнеса"
        settings.team_hero_title = "Подбор коробок под вашу задачу"
        settings.team_hero_subtitle = (
            "Сравните типовые форматы и оставьте запрос, если нужен другой размер "
            "или конструкция."
        )
        settings.contacts_hero_title = "Запрос на картонные коробки"
        settings.contacts_form_title = "Запросить расчет оптового заказа"
        settings.contacts_b2b_title = "Оптовые заказы"
        settings.contacts_b2b_subtitle = "Размеры, тираж и условия согласуются отдельно"
        settings.contacts_b2b_text = (
            "Укажите размеры коробки, тип гофрокартона и нужное количество. "
            "Цены и сроки на сайте приведены как демонстрационные примеры."
        )
        settings.stat_1_value = "5"
        settings.stat_1_label = "демо-категорий"
        settings.stat_2_value = "15"
        settings.stat_2_label = "примеров товаров"
        settings.stat_3_value = "3–5"
        settings.stat_3_label = "слоев гофрокартона"
        settings.stat_4_value = "Опт"
        settings.stat_4_label = "для бизнеса"
        settings.footer_description = (
            "Демонстрационный каталог картонных коробок для оптовых заказов. "
            "Проверьте цены, характеристики и реквизиты перед публикацией."
        )
        settings.seo_description = (
            "Демонстрационный каталог картонных коробок оптом: коробки для "
            "отправлений, переезда, архива и хранения."
        )
        settings.save()

        page_data = {
            "home": {
                "title": "Картонные коробки для бизнеса",
                "hero_label": "Оптовые поставки картонных коробок",
                "subtitle": settings.home_hero_subtitle,
                "hero_button_text": "Смотреть каталог",
                "h1": "Картонные коробки оптом",
                "seo_title": "Картонные коробки оптом — PakLine",
                "meta_description": settings.seo_description,
                "is_visible": True,
            },
            "catalog": {
                "title": "Коробки оптом",
                "subtitle": settings.catalog_subtitle,
                "h1": "Каталог картонных коробок",
                "seo_title": "Каталог картонных коробок оптом — PakLine",
                "meta_description": settings.seo_description,
                "is_visible": True,
            },
            "contacts": {
                "title": "Запрос на картонные коробки",
                "hero_label": "Оптовый запрос",
                "h1": "Запросить расчет заказа",
                "content_title": "Получить расчет оптового заказа",
                "content_subtitle": "Размеры, тираж и условия согласуются отдельно",
                "content_text": settings.contacts_b2b_text,
                "b2b_title": "Оптовые заказы",
                "seo_title": "Запрос на коробки оптом — PakLine",
                "meta_description": "Оставьте запрос на расчет партии картонных коробок.",
                "is_visible": True,
            },
            "team": {
                "title": "Подбор коробок под вашу задачу",
                "hero_label": "Упаковка для бизнеса",
                "h1": "Подбор коробок под вашу задачу",
                "subtitle": settings.team_hero_subtitle,
                "seo_title": "Подбор картонных коробок — PakLine",
                "meta_description": "Подберите формат картонной коробки для товара, отправления или хранения.",
                "is_visible": True,
            },
        }
        for page, defaults in page_data.items():
            PageContent.objects.update_or_create(page=page, defaults=defaults)
