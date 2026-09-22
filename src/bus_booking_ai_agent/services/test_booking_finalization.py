from uuid import UUID

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.services.booking_finalization_models import (
    finalize_booking,
)


PAYMENT_ID = UUID(
    "b5c78af9-5e19-4cad-9499-d4e7d6d1662c"
)

USER_ID = UUID(
    "7803ebf4-7421-495d-b186-ec01c7c591c3"
)


def main() -> None:
    user = AuthenticatedUser(
        id=USER_ID,
        email="talluripavankumar88@gmail.com",
        app_metadata={},
        user_metadata={},
    )

    print("Testing booking finalization...")
    print(f"Payment ID: {PAYMENT_ID}")
    print(f"User ID: {USER_ID}")
    print()

    try:
        result = finalize_booking(
            current_user=user,
            payment_id=PAYMENT_ID,
        )

        print("Booking finalization successful!")
        print()
        print("Booking:")
        print(result["booking"])
        print()
        print("Hold:")
        print(result["hold"])

    except Exception as error:
        print("Booking finalization failed.")
        print(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    main()