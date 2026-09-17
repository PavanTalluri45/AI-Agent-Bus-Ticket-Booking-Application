class AgentContext:
    """
    Represents the context available to an AI agent
    while processing the current task.

    Agent context can contain information from multiple
    sources such as:

    - System instructions
    - Current user message
    - Conversation history
    - Agent state
    - Tool results

    Only the context sources that currently exist in the
    project are represented here. Agent state and tool
    results will be introduced in later phases.
    """

    def __init__(self):
        self.system_instruction = None
        self.user_message = None
        self.conversation_history = None
        self.agent_state = None
        self.tool_results = None

    def set_system_instruction(self, instruction):
        """Set the agent's system instructions."""
        self.system_instruction = instruction

    def set_user_message(self, message):
        """Set the current user message."""
        self.user_message = message

    def set_conversation_history(self, history):
        """Set conversation history."""
        self.conversation_history = history

    def set_agent_state(self, state):
        """Set the current agent state."""
        self.agent_state = state

    def set_tool_results(self, results):
        """Set results returned by tools."""
        self.tool_results = results

    def get_context(self):
        """
        Return the complete agent context.

        Empty context sources are excluded from the result.
        """

        context = {}

        if self.system_instruction:
            context["system_instruction"] = (
                self.system_instruction
            )

        if self.user_message:
            context["user_message"] = (
                self.user_message
            )

        if self.conversation_history:
            context["conversation_history"] = (
                self.conversation_history
            )

        if self.agent_state:
            context["agent_state"] = (
                self.agent_state
            )

        if self.tool_results:
            context["tool_results"] = (
                self.tool_results
            )

        return context

    def clear(self):
        """
        Clear the current agent context.
        """

        self.system_instruction = None
        self.user_message = None
        self.conversation_history = None
        self.agent_state = None
        self.tool_results = None