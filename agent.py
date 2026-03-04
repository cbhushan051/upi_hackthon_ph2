"""
LLM AI Agent using LangChain + LangGraph with a CLI interface.
"""

import argparse
from typing import List, TypedDict

from langgraph.graph import StateGraph, START, END

from llm import LLM, llm


class ConversationState(TypedDict):
    """Graph state type for conversation messages."""

    messages: List[dict]


class Agent:
    """LangGraph-based AI Agent that uses an LLM for processing."""

    def __init__(self, llm_instance: LLM | None = None):
        """
        Initialize the agent.

        Args:
            llm_instance: Optional LLM instance to use (defaults to llm from llm.py)
        """
        self.llm = llm_instance or llm
        self.conversation_history: List[dict] = []
        self.graph = self._build_graph()

    def _respond(self, state: ConversationState) -> ConversationState:
        """
        Single graph node: take the latest message and produce an assistant reply.
        """
        messages = state.get("messages", [])
        response = self.llm.chat(messages)
        new_messages = messages + [
            {"role": "assistant", "content": response},
        ]
        return {"messages": new_messages}

    def _build_graph(self):
        """Build a simple LangGraph with one respond node."""
        builder = StateGraph(ConversationState)
        builder.add_node("respond", self._respond)
        builder.add_edge(START, "respond")
        builder.add_edge("respond", END)
        builder.set_entry_point("respond")
        return builder.compile()

    def process(self, user_input: str) -> str:
        """
        Process user input and generate a response.

        Args:
            user_input: User's input message

        Returns:
            Agent's response
        """
        user_message = {"role": "user", "content": user_input}
        state = {"messages": self.conversation_history + [user_message]}
        result: ConversationState = self.graph.invoke(state)
        self.conversation_history = result["messages"]
        # Last message should be the assistant response
        return self.conversation_history[-1]["content"]

    def reset(self):
        """Reset the conversation history."""
        self.conversation_history = []

    def run_interactive(self):
        """Run the agent in interactive CLI mode."""
        print("AI Agent CLI (LangGraph) - Type 'exit'/'quit' to end, 'reset' to clear history")
        print("=" * 70)

        while True:
            try:
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit", "q"]:
                    print("\nGoodbye!")
                    break

                if user_input.lower() == "reset":
                    self.reset()
                    print("Conversation history cleared.")
                    continue

                response = self.process(user_input)
                print(f"Agent: {response}")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="LLM AI Agent (LangChain + LangGraph) - Interactive command line interface"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode (default)",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        help="Process a single query and exit",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="LLM model to use",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key for the LLM service",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="Base URL for the API endpoint (useful for OpenAI-compatible APIs or local models)",
    )

    args = parser.parse_args()

    # Initialize LLM if custom parameters provided
    agent_llm = None
    if args.model or args.api_key or args.base_url:
        agent_llm = LLM(model=args.model, api_key=args.api_key, base_url=args.base_url)

    # Create agent
    agent = Agent(llm_instance=agent_llm)

    # Run based on mode
    if args.query:
        response = agent.process(args.query)
        print(response)
    else:
        agent.run_interactive()


if __name__ == "__main__":
    main()