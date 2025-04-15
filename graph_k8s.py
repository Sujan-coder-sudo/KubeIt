import dotenv
from pathlib import Path

# Explicitly load .env with UTF-8
env_path = Path(__file__).parent / '.env'
dotenv.load_dotenv(env_path, encoding='utf-8')  # This loads environment variables from .env file

import os
import json
from typing_extensions import Union, TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.graph import END  # New import path
START = None  # START is deprecated in newer versions
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.globals import set_verbose
from langchain_openai import ChatOpenAI

from agents.engineer import get_k8s_engineer
from agents.expert import get_k8s_expert
from state_k8s import K8sState
from agents.k8s_tools import k8s_tool_node

set_verbose(True)

# Initialize OpenAI client with API key from environment
def initialize_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set. Please create a .env file or set the environment variable.")
    
    return ChatOpenAI(
        api_key=api_key,
        model="gpt-3.5-turbo"  # or your preferred model
    )

def get_graph():
    graph_builder = StateGraph(K8sState)
    graph_builder.add_node("k8s_expert", get_k8s_expert)
    graph_builder.add_node("k8s_engineer", get_k8s_engineer)
    graph_builder.add_node("k8s_tool_node", k8s_tool_node)
    graph_builder.add_edge(START, "k8s_expert")
    graph_builder.add_edge("k8s_expert", "k8s_engineer")
    graph_builder.add_edge("k8s_engineer", "k8s_tool_node")
    graph_builder.add_edge("k8s_tool_node", END)
    
    memory = MemorySaver()

    return graph_builder.compile(checkpointer=memory)

def run(question: Union[str, None]):
    # Verify OpenAI is properly initialized
    try:
        initialize_openai()
    except ValueError as e:
        print(f"Error: {e}")
        return None

    graph = get_graph()
    thread: RunnableConfig = {"configurable": {"thread_id": "default"}}
    if question is None:
        question = input("Enter request: ")

    for event in graph.stream({"messages": [question]}, thread):
        for key in event:
            print("\n*******************************************\n")
            print(key + ":")
            print("---------------------\n")
            print(event[key]["messages"][-1].content)

    return graph.get_state(thread).values["messages"][-1].content

if __name__ == "__main__":
    run(None)