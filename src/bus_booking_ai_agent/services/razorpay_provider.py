import os
from decimal import Decimal
from typing import Any

import razorpay
from dotenv import load_dotenv

from bus_booking_ai_agent.services.payment_service import PaymentProvider


load_dotenv()


class RazorpayProvider(PaymentProvider):
    """
    Razorpay implementation of the PaymentProvider interface.
    """

    def __init__(self) -> None:
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")

        if not key_id:
            raise RuntimeError(
                "RAZORPAY_KEY_ID is not configured."
            )

        if not key_secret:
            raise RuntimeError(
                "RAZORPAY_KEY_SECRET is not configured."
            )

        self.key_id = key_id

        self.client: Any = razorpay.Client(
            auth=(key_id, key_secret)
        )

    def create_order(
        self,
        amount: Decimal,
        currency: str,
        receipt: str,
    ) -> dict:
        """
        Create a Razorpay order.

        Razorpay expects the amount in the smallest currency unit.
        For INR, ₹1270 becomes 127000 paise.
        """

        amount_in_paise = int(amount * 100)

        order = self.client.order.create(
            {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt,
            }
        )

        return {
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "status": order["status"],
        }

    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> None:
        """
        Verify the Razorpay payment signature.

        The Razorpay SDK uses the server-side key secret
        configured when the client was created.
        """

        self.client.utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )