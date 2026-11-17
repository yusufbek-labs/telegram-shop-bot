"""Service layer: cart math, order totals, status transitions, permissions."""
import pytest

from app.db.models import User
from app.repositories import CatalogRepo, OrderRepo
from app.services.cart import CartLine, CartService, ProductUnavailable, cart_total
from app.services.orders import (
    ALLOWED_TRANSITIONS,
    STATUSES,
    CartChangedError,
    CheckoutData,
    EmptyCartError,
    InvalidTransition,
    OrderNotFound,
    OrderService,
    can_transition,
)
from app.services.permissions import PermissionDenied, is_admin

ADMINS = [1000]
DATA = CheckoutData("Ann Lee", "+15551234567", "12 Birch Street", "cash")


@pytest.fixture
async def session(seeded):
    async with seeded() as s:
        s.add(User(id=7, full_name="Buyer", language="en"))
        await s.flush()
        yield s


# ---------- cart math ----------
def test_cart_total_pure_function():
    lines = [CartLine(1, "A", 1250, 2), CartLine(2, "B", 999, 3)]
    assert cart_total(lines) == 1250 * 2 + 999 * 3
    assert cart_total([]) == 0


async def test_add_same_product_twice_increments_quantity(session):
    svc = CartService(session)
    await svc.add(7, 1)
    await svc.add(7, 1)
    view = await svc.view(7)
    assert [(l.product_id, l.quantity) for l in view.lines] == [(1, 2)]
    assert view.total_cents == 2 * 1250


async def test_change_quantity_and_removal(session):
    svc = CartService(session)
    await svc.add(7, 1)
    await svc.add(7, 4)
    await svc.change_quantity(7, 1, +2)
    assert {l.product_id: l.quantity for l in (await svc.view(7)).lines} == {1: 3, 4: 1}
    await svc.change_quantity(7, 4, -1)  # down to zero removes the line
    assert [l.product_id for l in (await svc.view(7)).lines] == [1]
    await svc.remove(7, 1)
    assert (await svc.view(7)).is_empty


async def test_quantity_is_capped(session):
    svc = CartService(session)
    await svc.add(7, 1, quantity=500)
    assert (await svc.view(7)).lines[0].quantity == 99


async def test_cannot_add_disabled_product(session):
    product = await CatalogRepo(session).product(1)
    product.is_active = False
    with pytest.raises(ProductUnavailable):
        await CartService(session).add(7, 1)
    with pytest.raises(ProductUnavailable):
        await CartService(session).add(7, 9999)


# ---------- order totals ----------
async def test_checkout_snapshots_prices_and_clears_cart(session):
    cart = CartService(session)
    await cart.add(7, 1, quantity=2)  # 12.50 x 2
    await cart.add(7, 4)  # 19.00
    order = await OrderService(session).checkout(7, DATA)
    assert order.total_cents == 2 * 1250 + 1900
    assert order.status == "new"
    assert (await cart.view(7)).is_empty

    # later price changes must not alter an existing order
    (await CatalogRepo(session).product(1)).price_cents = 99999
    await session.flush()
    stored = await OrderRepo(session).get(order.id)
    assert stored.total_cents == 4400
    assert [(i.name, i.unit_price_cents, i.quantity) for i in stored.items][0] == ("Alpine Green Tea, 100 g", 1250, 2)


async def test_checkout_rejects_empty_cart_and_bad_payment(session):
    with pytest.raises(EmptyCartError):
        await OrderService(session).checkout(7, DATA)
    await CartService(session).add(7, 1)
    with pytest.raises(ValueError):
        await OrderService(session).checkout(7, CheckoutData("A B", "+15551234567", "Somewhere 1", "bitcoin"))


async def test_checkout_fails_when_product_disabled_meanwhile(session):
    await CartService(session).add(7, 1)
    (await CatalogRepo(session).product(1)).is_active = False
    with pytest.raises(CartChangedError):
        await OrderService(session).checkout(7, DATA)


# ---------- status transitions ----------
EXPECTED = {
    ("new", "confirmed"), ("new", "cancelled"),
    ("confirmed", "shipped"), ("confirmed", "cancelled"),
    ("shipped", "delivered"), ("shipped", "cancelled"),
}


@pytest.mark.parametrize("current", STATUSES)
@pytest.mark.parametrize("target", STATUSES)
def test_transition_matrix(current, target):
    assert can_transition(current, target) == ((current, target) in EXPECTED)


def test_final_statuses_have_no_exits():
    assert ALLOWED_TRANSITIONS["delivered"] == () and ALLOWED_TRANSITIONS["cancelled"] == ()


async def _order(session):
    await CartService(session).add(7, 1)
    return await OrderService(session).checkout(7, DATA)


async def test_admin_walks_order_through_happy_path(session):
    order = await _order(session)
    svc = OrderService(session)
    for status in ("confirmed", "shipped", "delivered"):
        order = await svc.change_status(order.id, status, 1000, ADMINS)
        assert order.status == status


async def test_invalid_transition_is_rejected_and_state_kept(session):
    order = await _order(session)
    with pytest.raises(InvalidTransition):
        await OrderService(session).change_status(order.id, "delivered", 1000, ADMINS)
    assert (await OrderRepo(session).get(order.id)).status == "new"


async def test_cancelled_order_cannot_be_reopened(session):
    order = await _order(session)
    svc = OrderService(session)
    await svc.change_status(order.id, "cancelled", 1000, ADMINS)
    with pytest.raises(InvalidTransition):
        await svc.change_status(order.id, "confirmed", 1000, ADMINS)


async def test_missing_order(session):
    with pytest.raises(OrderNotFound):
        await OrderService(session).change_status(424242, "confirmed", 1000, ADMINS)


# ---------- permissions ----------
async def test_non_admin_cannot_change_status(session):
    order = await _order(session)
    with pytest.raises(PermissionDenied):
        await OrderService(session).change_status(order.id, "confirmed", 7, ADMINS)
    assert (await OrderRepo(session).get(order.id)).status == "new"


def test_is_admin():
    assert is_admin(1000, [1000, 2]) and not is_admin(7, [1000]) and not is_admin(None, [1000])
    assert not is_admin(1000, [])
