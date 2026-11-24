import stripe
from django.conf import settings

stripe.api_key = settings.SECRET_KEY_1


def create_stripe_product(name: str, description: str = "") -> str:
    """
    Создает продукт в Stripe.
    Принимает примитивы (строки), возвращает строку (ID продукта).
    Ничего не знает о моделях Course/Lesson.
    """
    product = stripe.Product.create(
        name=name,
        description=description,
    )
    return product.id


def create_stripe_price(product_id: str, amount: float, currency: str = "rub") -> str:
    """
    Создает цену для продукта.
    amount — в обычных рублях (например, 1999.00).
    Внутри превращаем в копейки: 1999.00 -> 199900.
    """
    price = stripe.Price.create(
        product=product_id,
        unit_amount=int(amount * 100),
        currency=currency,
    )
    return price.id

def create_checkout_session(
    price_id: str,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
) -> dict:
    """
    Создает сессию оплаты.
    Возвращает {'session_id': ..., 'payment_url': ...}.
    """
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )
    return {"session_id": session.id, "payment_url": session.url}


def retrieve_checkout_session(session_id: str) -> dict:
    """
    Запрашивает у Stripe актуальный статус сессии.
    Используется в дополнительном задании.
    """
    session = stripe.checkout.Session.retrieve(session_id)
    return {
        "id": session.id,
        "payment_status": session.payment_status, 
        "status": session.status,                  
        "amount_total": session.amount_total,      
        "currency": session.currency,
    }