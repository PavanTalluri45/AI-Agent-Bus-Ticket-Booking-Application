from bus_booking_ai_agent.config.gemini import client, MODEL


def print_model_limits():
    """Display the token limits for the selected Gemini model."""
    model_info = client.models.get(model=MODEL)

    print("\n--- Model Limits ---")
    print(f"Model: {MODEL}")
    print(f"Input token limit: {model_info.input_token_limit}")
    print(f"Output token limit: {model_info.output_token_limit}")


def run():
    print_model_limits()


if __name__ == "__main__":
    run()
