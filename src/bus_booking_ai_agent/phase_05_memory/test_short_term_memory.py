from bus_booking_ai_agent.config.gemini import client, MODEL


def main() -> None:

    print("=" * 60)
    print("SHORT-TERM MEMORY")
    print("=" * 60)

    # ---------------------------------------------------------
    # TURN 1
    # ---------------------------------------------------------

    first_message = (
        "I am looking for a bus from Hyderabad "
        "to Bangalore on 2026-09-25."
    )

    print("\n--- TURN 1 ---")
    print(f"User: {first_message}")

    first_response = client.interactions.create(
        model=MODEL,
        input=first_message,
    )

    first_output = getattr(
        first_response,
        "output_text",
        None,
    )

    if not first_output:
        raise RuntimeError(
            "Gemini returned no response for Turn 1."
        )

    print(f"\nAssistant:\n{first_output}")

    print(
        f"\nInteraction ID:\n{getattr(first_response, 'id', '')}"
    )

    # ---------------------------------------------------------
    # TURN 2
    # ---------------------------------------------------------

    second_message = (
        "What information should I provide next "
        "to continue with this bus search?"
    )

    print("\n--- TURN 2 ---")
    print(f"User: {second_message}")

    second_response = client.interactions.create(
        model=MODEL,
        previous_interaction_id=first_response.id,
        input=second_message,
    )

    second_output = getattr(
        second_response,
        "output_text",
        None,
    )

    if not second_output:
        raise RuntimeError(
            "Gemini returned no response for Turn 2."
        )

    print(f"\nAssistant:\n{second_output}")

    print(
        f"\nInteraction ID:\n{getattr(second_response, 'id', '')}"
    )

    # ---------------------------------------------------------
    # EXPLANATION
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("SHORT-TERM MEMORY CONCEPT")
    print("=" * 60)

    print(
        "\nThe second interaction continues from "
        "the first interaction."
    )

    print(
        "\nThe previous interaction ID provides "
        "conversation continuity."
    )

    print(
        "\nThis does NOT create permanent user memory."
    )


if __name__ == "__main__":
    main()