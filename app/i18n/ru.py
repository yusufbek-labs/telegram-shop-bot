TEXTS = {
    # --- customer: general ---
    "welcome": "Добро пожаловать в <b>{shop}</b>!\nВыбирайте товары в каталоге, собирайте корзину и оформляйте заказ в пару касаний.",
    "menu_title": "Главное меню",
    "btn_catalog": "🛍 Каталог",
    "btn_cart": "🛒 Корзина",
    "btn_orders": "📦 Мои заказы",
    "btn_language": "🌐 Язык",
    "btn_help": "❓ Помощь",
    "btn_back": "⬅️ Назад",
    "btn_menu": "🏠 Меню",
    "btn_add": "➕ В корзину",
    "btn_checkout": "✅ Оформить заказ",
    "btn_clear": "🗑 Очистить корзину",
    "btn_confirm": "✅ Подтвердить",
    "btn_cancel": "✖️ Отмена",
    "btn_share_phone": "📱 Отправить мой номер",
    "btn_search": "🔎 Поиск",
    "btn_search_again": "🔎 Искать ещё",
    "help": (
        "<b>Как это работает</b>\n"
        "/start - главное меню\n/catalog - каталог товаров\n/search - найти товар\n/cart - корзина\n"
        "/orders - ваши заказы\n/language - сменить язык\n/cancel - отменить текущее действие"
    ),
    "help_admin": (
        "\n\n<b>Администратору</b>\n/orders - заказы по статусам\n/products - управление товарами\n"
        "/add_product - добавить товар\n/edit_product - изменить товар\n/categories - управление категориями\n"
        "/stats - заказы и выручка\n/broadcast - рассылка всем пользователям"
    ),
    # --- catalog / cart ---
    "catalog_title": "<b>Каталог</b>\nВыберите категорию:",
    "catalog_empty": "Каталог пока пуст. Загляните позже.",
    "category_empty": "В этой категории пока нет товаров.",
    "category_header": "<b>{category}</b>",
    "category_footer": "Это всё в категории <b>{category}</b> (показано: {count}).",
    "product_card": "<b>{name}</b>\n{description}\n\n💰 {price}",
    "added_to_cart": "Добавлено в корзину: {name}",
    "product_unavailable": "К сожалению, этот товар больше недоступен.",
    "cart_title": "<b>Ваша корзина</b>",
    "cart_empty": "Корзина пуста.",
    "cart_line": "{name} × {qty} = {sum}",
    "cart_total": "<b>Итого: {total}</b>",
    "cart_cleared": "Корзина очищена.",
    "search_prompt": "Что вы ищете? Отправьте название товара или категории.",
    "search_invalid": "Введите для поиска от 2 до 50 символов (или /cancel).",
    "search_header": "<b>Поиск: {query}</b>\nНайдено: {count}",
    "search_footer": "Это всё по запросу «{query}» (показано: {count}).",
    "search_footer_more": "Показаны первые {shown} из {count} по запросу «{query}». Уточните запрос, чтобы увидеть остальные.",
    "search_nothing": "По запросу «{query}» ничего не найдено. Попробуйте более короткое слово или откройте каталог.",
    # --- checkout ---
    "checkout_name": "Оформление (1/4)\nКак вас зовут?",
    "checkout_phone": "Оформление (2/4)\nОтправьте номер телефона: введите его или нажмите кнопку.",
    "checkout_address": "Оформление (3/4)\nВведите адрес доставки.",
    "checkout_payment": "Оформление (4/4)\nВыберите способ оплаты:",
    "payment_cash": "💵 Наличными при получении",
    "payment_card": "💳 Картой при получении",
    "payment_transfer": "🏦 Банковский перевод",
    "checkout_receipt": (
        "<b>Оплата банковским переводом</b>\n\n{details}\n\nСумма к оплате: <b>{total}</b>\n\n"
        "Затем отправьте в этот чат фото или PDF-файл квитанции об оплате (или /cancel)."
    ),
    "receipt_invalid": "Нужна квитанция об оплате в виде фото или PDF-файла. Отправьте её или нажмите /cancel.",
    "receipt_line": "\nКвитанция: прикреплена",
    "checkout_summary": (
        "<b>Проверьте заказ</b>\n\n{items}\n\n<b>Итого: {total}</b>\n\n"
        "Имя: {name}\nТелефон: {phone}\nАдрес: {address}\nОплата: {payment}{receipt}"
    ),
    "invalid_name": "Введите имя длиной от 2 до 60 символов.",
    "invalid_phone": "Это не похоже на номер телефона. Пример: +7 900 123 45 67",
    "invalid_address": "Введите адрес длиной от 5 до 200 символов.",
    "checkout_cancelled": "Оформление отменено. Корзина сохранена.",
    "order_placed": (
        "✅ Спасибо! Заказ <b>№{id}</b> оформлен. Сумма: {total}.\n"
        "Мы сообщим здесь, когда статус изменится."
    ),
    "cart_changed": "Некоторые товары из корзины больше недоступны. Проверьте корзину.",
    # --- statuses and customer orders ---
    "status_new": "🆕 Новый",
    "status_confirmed": "✅ Подтверждён",
    "status_shipped": "🚚 Отправлен",
    "status_delivered": "📬 Доставлен",
    "status_cancelled": "❌ Отменён",
    "order_status_update": "Заказ <b>№{id}</b>: новый статус - <b>{status}</b>.",
    "my_orders_title": "<b>Ваши заказы</b>",
    "my_orders_empty": "У вас пока нет заказов.",
    "order_line": "№{id} · {status} · {total}",
    # --- language ---
    "language_prompt": "Выберите язык:",
    "language_set": "Язык переключён на русский.",
    # --- generic ---
    "unknown_input": "Извините, я не понял. Воспользуйтесь меню ниже.",
    "unknown_command": "Неизвестная команда. Попробуйте /help.",
    "cancelled": "Отменено.",
    "stale_button": "Эта кнопка устарела. Откройте меню заново.",
    "no_permission": "У вас нет прав для этого действия.",
    "error_generic": "Что-то пошло не так. Попробуйте ещё раз чуть позже.",
    "text_expected": "Отправьте текстовое сообщение (или /cancel для отмены).",
    # --- admin: orders ---
    "admin_new_order": "🔔 <b>Новый заказ №{id}</b>\n\n{details}",
    "admin_order_card": (
        "<b>Заказ №{id}</b> · {status}\nСоздан: {created}\n"
        "Клиент: {name} ({phone})\nАдрес: {address}\nОплата: {payment}{receipt}\n\n"
        "{items}\n\n<b>Итого: {total}</b>"
    ),
    "admin_orders_title": "<b>Заказы</b>\nФильтр по статусу:",
    "filter_all": "Все",
    "admin_orders_list": "<b>Заказы: {status}</b> (последние {count})\nНажмите на заказ, чтобы открыть.",
    "admin_no_orders": "Заказов не найдено.",
    "status_changed": "Заказ №{id} теперь: {status}.",
    "status_not_allowed": "Такое изменение статуса недопустимо.",
    "order_not_found": "Заказ не найден.",
    "btn_receipt": "🧾 Квитанция",
    "receipt_caption": "Квитанция об оплате заказа №{id}",
    "receipt_missing": "К этому заказу не прикреплена квитанция.",
    # --- admin: products ---
    "admin_products_title": "<b>Товары</b> (нажмите на название, чтобы показать/скрыть товар в магазине)",
    "btn_edit": "✏️ Изменить",
    "product_toggled": "{name}: теперь {state}.",
    "state_on": "виден",
    "state_off": "скрыт",
    "add_choose_category": "Новый товар: выберите категорию.",
    "add_name": "Отправьте название товара.",
    "add_price": "Отправьте цену, например 12.50",
    "add_description": "Отправьте краткое описание.",
    "add_image": "Отправьте фото товара или ссылку на изображение (http/https), либо - чтобы пропустить.",
    "add_confirm": "Сохранить этот товар?\n\n{card}",
    "product_saved": "Товар №{id} сохранён.",
    "invalid_price": "Неверная цена. Введите положительное число, например 12.50",
    "invalid_text": "Отправьте текст длиной от 1 до 200 символов.",
    "invalid_url": "Отправьте корректную ссылку http(s) или - чтобы пропустить.",
    "no_categories": "Категорий пока нет. Сначала добавьте категорию командой /categories.",
    "edit_choose_product": "Выберите товар для изменения:",
    "edit_choose_field": "Изменение: <b>{name}</b>. Что поменять?",
    "field_name": "Название",
    "field_price": "Цена",
    "field_description": "Описание",
    "field_image": "Изображение",
    "field_category": "Категория",
    "edit_ask_category": "Выберите новую категорию:",
    "edit_ask_value": "Отправьте новое значение: {field}\n(для изображения: фото или ссылка, - удаляет его)",
    "image_photo": "Фото прикреплено",
    "product_updated": "Товар обновлён.",
    "no_products": "Товаров пока нет.",
    "btn_delete": "🗑 Удалить",
    "product_delete_confirm": "Удалить <b>{name}</b> из магазина? Прошлые заказы сохранят свои позиции.",
    "product_deleted": "Товар удалён.",
    # --- admin: categories ---
    "admin_categories_title": (
        "<b>Категории</b>\nНажмите на категорию, чтобы переименовать её, 🗑 - чтобы удалить. Удалить можно только пустую категорию."
    ),
    "btn_add_category": "➕ Добавить категорию",
    "category_ask_en": "Отправьте название категории на английском.",
    "category_ask_ru": "Отправьте название категории на русском.",
    "category_rename_en": "Переименование: <b>{name}</b>. Отправьте новое название на английском или - чтобы оставить.",
    "category_rename_ru": "Отправьте новое название на русском или - чтобы оставить.",
    "category_saved": "Категория сохранена.",
    "category_not_empty": "В этой категории ещё есть товары: {count}. Сначала перенесите или удалите их.",
    "category_delete_confirm": "Удалить пустую категорию <b>{name}</b>?",
    "category_deleted": "Категория удалена.",
    # --- admin: stats / broadcast ---
    "stats": (
        "<b>Статистика</b>\n\nСегодня: заказов {t_orders}, выручка {t_rev}\n"
        "За 7 дней: заказов {w_orders}, выручка {w_rev}\n\nОтменённые заказы не учитываются."
    ),
    "broadcast_ask": "Отправьте сообщение для рассылки ({count} получателей) или /cancel.",
    "broadcast_preview": "Предпросмотр:\n\n{text}\n\nОтправить {count} пользователям?",
    "broadcast_started": "Рассылка запущена. Сообщу, когда закончу.",
    "broadcast_done": "Рассылка завершена: отправлено {sent}, заблокировали бота {blocked}, ошибок {failed}.",
    "broadcast_cancelled": "Рассылка отменена.",
    "broadcast_no_users": "Пока некому отправлять рассылку.",
}
