class ContextSources:
    """
    Stores the context sources currently available
    to the bus booking AI agent.
    """

    def __init__(self):
        self.system_instruction = None
        self.user_message = None
        self.previous_interaction_id = None

    def set_system_instruction(self, instruction):
        self.system_instruction = instruction

    def set_user_message(self, message):
        self.user_message = message

    def set_previous_interaction_id(self, interaction_id):
        self.previous_interaction_id = interaction_id

    def get_sources(self):
        return {
            "system_instruction": self.system_instruction,
            "user_message": self.user_message,
            "previous_interaction_id": self.previous_interaction_id,
        }