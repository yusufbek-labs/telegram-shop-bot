TEXTS = {
    # --- customer: general ---
    "welcome": "Welcome to <b>{shop}</b>!\nBrowse the catalog, fill your cart and check out in a few taps.",
    "menu_title": "Main menu",
    "btn_catalog": "🛍 Catalog",
    "btn_cart": "🛒 Cart",
    "btn_orders": "📦 My orders",
    "btn_language": "🌐 Language",
    "btn_help": "❓ Help",
    "btn_back": "⬅️ Back",
    "btn_menu": "🏠 Menu",
    "btn_add": "➕ Add to cart",
    "btn_checkout": "✅ Checkout",
    "btn_clear": "🗑 Clear cart",
    "btn_confirm": "✅ Confirm",
    "btn_cancel": "✖️ Cancel",
    "btn_share_phone": "📱 Share my number",
    "btn_search": "🔎 Search",
    "btn_search_again": "🔎 Search again",
    "help": (
        "<b>How it works</b>\n"
        "/start - main menu\n/catalog - browse products\n/search - find a product\n/cart - your cart\n"
        "/orders - your orders\n/language - change language\n/cancel - abort the current action"
    ),
    "help_admin": (
        "\n\n<b>Admin</b>\n/orders - orders by status\n/products - manage products\n"
        "/add_product - add a product\n/edit_product - edit a product\n/categories - manage categories\n"
        "/stats - orders and revenue\n/broadcast - message all users"
    ),
    # --- catalog / cart ---
    "catalog_title": "<b>Catalog</b>\nChoose a category:",
    "catalog_empty": "The catalog is empty for now. Please check back soon.",
    "category_empty": "No products in this category yet.",
    "category_header": "<b>{category}</b>",
    "category_footer": "That is all in <b>{category}</b> ({count} shown).",
    "product_card": "<b>{name}</b>\n{description}\n\n💰 {price}",
    "added_to_cart": "Added to cart: {name}",
    "product_unavailable": "Sorry, this product is no longer available.",
    "cart_title": "<b>Your cart</b>",
    "cart_empty": "Your cart is empty.",
    "cart_line": "{name} × {qty} = {sum}",
    "cart_total": "<b>Total: {total}</b>",
    "cart_cleared": "Cart cleared.",
    "search_prompt": "What are you looking for? Send a product name or a category.",
    "search_invalid": "Please send 2 to 50 characters to search for (or /cancel).",
    "search_header": "<b>Search: {query}</b>\nFound {count}:",
    "search_footer": "That is everything for «{query}» ({count} shown).",
    "search_footer_more": "Showing the first {shown} of {count} for «{query}». Narrow the search to see the rest.",
    "search_nothing": "Nothing found for «{query}». Try a shorter word or browse the catalog.",
    # --- checkout ---
    "checkout_name": "Checkout (1/4)\nWhat is your name?",
    "checkout_phone": "Checkout (2/4)\nSend your phone number: type it or use the button.",
    "checkout_address": "Checkout (3/4)\nEnter the delivery address.",
    "checkout_payment": "Checkout (4/4)\nChoose a payment method:",
    "payment_cash": "💵 Cash on delivery",
    "payment_card": "💳 Card on delivery",
    "payment_transfer": "🏦 Bank transfer",
    "checkout_receipt": (
        "<b>Pay by bank transfer</b>\n\n{details}\n\nAmount to pay: <b>{total}</b>\n\n"
        "Then send a photo or a PDF file of the payment receipt in this chat (or /cancel)."
    ),
    "receipt_invalid": "I need the payment receipt as a photo or a PDF file. Please send one, or /cancel.",
    "receipt_line": "\nReceipt: attached",
    "checkout_summary": (
        "<b>Please confirm your order</b>\n\n{items}\n\n<b>Total: {total}</b>\n\n"
        "Name: {name}\nPhone: {phone}\nAddress: {address}\nPayment: {payment}{receipt}"
    ),
    "invalid_name": "Please enter a name between 2 and 60 characters.",
    "invalid_phone": "That does not look like a phone number. Example: +1 555 123 4567",
    "invalid_address": "Please enter an address between 5 and 200 characters.",
    "checkout_cancelled": "Checkout cancelled. Your cart is kept.",
    "order_placed": (
        "✅ Thank you! Order <b>#{id}</b> is placed. Total: {total}.\n"
        "We will update you here when the status changes."
    ),
    "cart_changed": "Some items in your cart are no longer available. Please review your cart.",
    # --- statuses and customer orders ---
    "status_new": "🆕 New",
    "status_confirmed": "✅ Confirmed",
    "status_shipped": "🚚 Shipped",
    "status_delivered": "📬 Delivered",
    "status_cancelled": "❌ Cancelled",
    "order_status_update": "Order <b>#{id}</b>: status is now <b>{status}</b>.",
    "my_orders_title": "<b>Your orders</b>",
    "my_orders_empty": "You have no orders yet.",
    "order_line": "#{id} · {status} · {total}",
    # --- language ---
    "language_prompt": "Choose your language:",
    "language_set": "Language set to English.",
    # --- generic ---
    "unknown_input": "Sorry, I did not understand that. Please use the menu below.",
    "unknown_command": "Unknown command. Try /help.",
    "cancelled": "Cancelled.",
    "stale_button": "This button is outdated. Please open the menu again.",
    "no_permission": "You do not have permission to do that.",
    "error_generic": "Something went wrong. Please try again in a moment.",
    "text_expected": "Please send a text message (or /cancel to stop).",
    # --- admin: orders ---
    "admin_new_order": "🔔 <b>New order #{id}</b>\n\n{details}",
    "admin_order_card": (
        "<b>Order #{id}</b> · {status}\nCreated: {created}\n"
        "Customer: {name} ({phone})\nAddress: {address}\nPayment: {payment}{receipt}\n\n"
        "{items}\n\n<b>Total: {total}</b>"
    ),
    "admin_orders_title": "<b>Orders</b>\nFilter by status:",
    "filter_all": "All",
    "admin_orders_list": "<b>Orders: {status}</b> (latest {count})\nTap an order to open it.",
    "admin_no_orders": "No orders found.",
    "status_changed": "Order #{id} is now {status}.",
    "status_not_allowed": "That status change is not allowed.",
    "order_not_found": "Order not found.",
    "btn_receipt": "🧾 Receipt",
    "receipt_caption": "Payment receipt for order #{id}",
    "receipt_missing": "This order has no receipt.",
    # --- admin: products ---
    "admin_products_title": "<b>Products</b> (tap a name to show/hide it in the shop)",
    "btn_edit": "✏️ Edit",
    "product_toggled": "{name} is now {state}.",
    "state_on": "visible",
    "state_off": "hidden",
    "add_choose_category": "New product: choose a category.",
    "add_name": "Send the product name.",
    "add_price": "Send the price, for example 12.50",
    "add_description": "Send a short description.",
    "add_image": "Send a photo of the product or an image URL (http/https), or - to skip.",
    "add_confirm": "Save this product?\n\n{card}",
    "product_saved": "Saved product #{id}.",
    "invalid_price": "Invalid price. Use a positive number like 12.50",
    "invalid_text": "Please send text of 1 to 200 characters.",
    "invalid_url": "Please send a valid http(s) URL, or - to skip.",
    "no_categories": "There are no categories yet. Add one with /categories first.",
    "edit_choose_product": "Choose a product to edit:",
    "edit_choose_field": "Editing <b>{name}</b>. What do you want to change?",
    "field_name": "Name",
    "field_price": "Price",
    "field_description": "Description",
    "field_image": "Image",
    "field_category": "Category",
    "edit_ask_category": "Choose the new category:",
    "edit_ask_value": "Send the new value for: {field}\n(for the image: a photo or a URL, - removes it)",
    "image_photo": "Photo attached",
    "product_updated": "Product updated.",
    "no_products": "No products yet.",
    "btn_delete": "🗑 Delete",
    "product_delete_confirm": "Delete <b>{name}</b> from the shop? Past orders keep their lines.",
    "product_deleted": "Product deleted.",
    # --- admin: categories ---
    "admin_categories_title": (
        "<b>Categories</b>\nTap a category to rename it, 🗑 to delete it. Only empty categories can be deleted."
    ),
    "btn_add_category": "➕ Add category",
    "category_ask_en": "Send the category name in English.",
    "category_ask_ru": "Send the category name in Russian.",
    "category_rename_en": "Renaming <b>{name}</b>. Send the new English name, or - to keep it.",
    "category_rename_ru": "Send the new Russian name, or - to keep it.",
    "category_saved": "Category saved.",
    "category_not_empty": "This category still has {count} product(s). Move or delete them first.",
    "category_delete_confirm": "Delete the empty category <b>{name}</b>?",
    "category_deleted": "Category deleted.",
    # --- admin: stats / broadcast ---
    "stats": (
        "<b>Stats</b>\n\nToday: {t_orders} orders, {t_rev}\n"
        "Last 7 days: {w_orders} orders, {w_rev}\n\nCancelled orders are not counted."
    ),
    "broadcast_ask": "Send the message to broadcast to {count} users (or /cancel).",
    "broadcast_preview": "Preview:\n\n{text}\n\nSend this to {count} users?",
    "broadcast_started": "Broadcast started. I will report when it is done.",
    "broadcast_done": "Broadcast finished: sent {sent}, blocked the bot {blocked}, failed {failed}.",
    "broadcast_cancelled": "Broadcast cancelled.",
    "broadcast_no_users": "There are no users to broadcast to yet.",
}
