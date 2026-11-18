from aiogram import Router

from app.handlers import (
    admin_categories,
    admin_misc,
    admin_orders,
    admin_products,
    cart,
    catalog,
    checkout,
    fallback,
    search,
    start,
)


def build_router() -> Router:
    """Order matters: specific routers first, fallback last."""
    root = Router(name="root")
    root.include_routers(
        start.router,
        catalog.router,
        search.router,
        cart.router,
        checkout.router,
        admin_orders.status_router,
        admin_orders.router,
        admin_products.router,
        admin_categories.router,
        admin_misc.router,
        fallback.router,
    )
    return root
