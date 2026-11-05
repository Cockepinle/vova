"""Provider-neutral order export service.

New formats (for example XML) can be added with ``register_order_exporter``
without changing management views or order selection rules.
"""
from abc import ABC, abstractmethod
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


class BaseOrderExporter(ABC):
    format_code = ""
    content_type = "application/octet-stream"
    extension = "bin"

    @abstractmethod
    def export(self, orders):
        raise NotImplementedError


class XlsxOrderExporter(BaseOrderExporter):
    format_code = "xlsx"
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    extension = "xlsx"

    columns = [
        "Номер заказа", "Дата", "Клиент", "Аккаунт", "Email", "Телефон", "Компания",
        "Статус заказа", "Код статуса", "Статус оплаты", "Код оплаты", "Способ оплаты",
        "Способ доставки", "Товар", "Артикул", "Единица", "Количество", "Цена позиции",
        "Сумма позиции", "НДС, %", "Вес единицы, кг", "Объём единицы, м³",
        "Итого заказа", "Общий вес, кг", "Общий объём, м³", "Комментарий",
        "Тип доставки", "Перевозчик", "Адрес отправления", "Адрес получения", "Ссылка перевозчика",
        "Длина, мм", "Ширина, мм", "Высота, мм",
    ]

    def export(self, orders):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Заказы"
        sheet.append(self.columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="173B6C")

        for order in orders:
            items = list(order.items.all()) or [None]
            for item in items:
                created_at = timezone.localtime(order.created_at).replace(tzinfo=None)
                sheet.append([
                    order.number, created_at, order.full_name,
                    order.user.email or order.user.username, order.email, order.phone, order.company,
                    order.get_status_display(), order.status, order.get_payment_status_display(),
                    order.payment_status,
                    order.payment_method_name or (order.payment_method.name if order.payment_method_id else ""),
                    order.delivery_method_name or (order.delivery_method.name if order.delivery_method_id else ""),
                    item.product_name if item else "", item.product_sku if item else "",
                    item.unit if item else "", item.quantity if item else "",
                    item.price if item else "", item.line_total if item else "",
                    item.vat_rate if item else "", item.weight_kg if item else "",
                    item.volume_m3 if item else "", order.total, order.total_weight_kg,
                    order.total_volume_m3, order.comment,
                    order.get_delivery_method_kind_display(),
                    order.delivery_provider_code, order.delivery_origin_address, order.delivery_address,
                    order.delivery_handoff_url,
                    item.length_mm if item else "", item.width_mm if item else "", item.height_mm if item else "",
                ])

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        widths = [18, 20, 24, 26, 26, 18, 24, 20, 18, 20, 16, 22, 22, 34, 18, 12, 12, 16, 17, 12, 18, 20, 18, 18, 20, 36, 20, 18, 32, 32, 42, 14, 14, 14]
        for index, width in enumerate(widths, 1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        for row in sheet.iter_rows(min_row=2):
            row[1].number_format = "DD.MM.YYYY HH:MM"
            for index in (17, 18, 19, 20, 21, 22, 23, 24):
                row[index].number_format = "0.###############"

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()


_exporters = {}


def register_order_exporter(exporter):
    _exporters[exporter.format_code] = exporter


def get_order_exporter(format_code="xlsx"):
    try:
        return _exporters[format_code]
    except KeyError as error:
        raise ValueError(f"Неизвестный формат экспорта: {format_code}") from error


register_order_exporter(XlsxOrderExporter())
