"""Order creation and the status state machine."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order, OrderItem
from app.repositories import CartRepo, OrderRepo
from app.services.cart import CartService
from app.services.permissions import require_admin

STATUSES = ("new", "confirmed", "shipped", "delivered", "cancelled")
PAYMENT_METHODS = ("cash", "card")

# status -> statuses it may move to. delivered / cancelled are final.
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new": ("confirmed", "cancelled"),
    "confirmed": ("shipped", "cancelled"),
    "shipped": ("delivered", "cancelled"),
    "delivered": (),
    "cancelled": (),
}


class OrderError(Exception):
    pass


class EmptyCartError(OrderError):
    pass


class CartChangedError(OrderError):
    """An item in the cart was disabled or removed before checkout finished."""


class OrderNotFound(OrderError):
    pass


class InvalidTransition(OrderError):
    pass


@dataclass(frozen=True)
class CheckoutData:
    name: str
    phone: str
    address: str
    payment_method: str


def allowed_next(status: str) -> tuple[str, ...]:
    return ALLOWED_TRANSITIONS.get(status, ())


def can_transition(current: str, new: str) -> bool:
    return new in allowed_next(current)


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.orders = OrderRepo(session)
        self.carts = CartRepo(session)
        self.cart_service = CartService(session)

    async def checkout(self, user_id: int, data: CheckoutData) -> Order:
        if data.payment_method not in PAYMENT_METHODS:
            raise ValueError(f"unknown payment method {data.payment_method!r}")
        view = await self.cart_service.view(user_id)
        if view.is_empty:
            raise EmptyCartError()
        for item in await self.carts.items(user_id):
            if not item.product.is_active:
                raise CartChangedError(item.product_id)
        order = Order(
            user_id=user_id,
            customer_name=data.name,
            phone=data.phone,
            address=data.address,
            payment_method=data.payment_method,
            status="new",
            total_cents=view.total_cents,
            items=[
                OrderItem(
                    product_id=line.product_id,
                    name=line.name,
                    unit_price_cents=line.unit_price_cents,
                    quantity=line.quantity,
                )
                for line in view.lines
            ],
        )
        await self.orders.add(order)
        await self.carts.clear(user_id)
        return order

    async def change_status(self, order_id: int, new_status: str, actor_id: int, admin_ids: Iterable[int]) -> Order:
        require_admin(actor_id, admin_ids)
        order = await self.orders.get(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        if not can_transition(order.status, new_status):
            raise InvalidTransition(f"{order.status} -> {new_status}")
        order.status = new_status
        await self.session.flush()
        return order
