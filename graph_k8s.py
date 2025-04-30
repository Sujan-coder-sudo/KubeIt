import dotenv
from pathlib import Path
import os
from typing import Optional, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.globals import set_verbose
from langchain_openai import ChatOpenAI

# Import your custom components
from agents.engineer import get_k8s_engineer
from agents.expert import get_k8s_expert
from state_k8s import K8sState
from agents.k8s_tools import k8s_tool_node

set_verbose(True)

# Robust .env loading with encoding fallback
def load_environment():
    env_path = Path(__file__).parent / '.env'
    try:
        dotenv.load_dotenv(env_path, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            dotenv.load_dotenv(env_path, encoding='utf-16')
        except Exception as e:
            raise RuntimeError(f"Failed to load .env file: {str(e)}")

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in .env file")

load_environment()

# Initialize OpenAI client
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0.7,
        streaming=True
    )

# Build the workflow graph
def build_workflow() -> StateGraph:
    workflow = StateGraph(K8sState)
    
    # Add nodes
    workflow.add_node("k8s_expert", get_k8s_expert)
    workflow.add_node("k8s_engineer", get_k8s_engineer)
    workflow.add_node("tools", k8s_tool_node)
    
    # Define workflow
    workflow.set_entry_point("k8s_expert")
    workflow.add_edge("k8s_expert", "k8s_engineer")
    workflow.add_edge("k8s_engineer", "tools")
    workflow.add_edge("tools", END)
    
    return workflow.compile(checkpointer=MemorySaver())

# Main execution function
def execute_workflow(question: Optional[str] = None) -> Dict[str, Any]:
    llm = get_llm()
    app = build_workflow()
    
    question = question or input("Enter your Kubernetes query: ")
    thread_id = "user_123"  # In production, generate unique IDs
    
    # Stream the execution
    for event in app.stream(
        {"messages": [{"role": "user", "content": question}]},
        {"configurable": {"thread_id": thread_id}}
    ):
        for key, value in event.items():
            print(f"\n{'='*40}")
            print(f"{key.upper()} OUTPUT:")
            print('-'*40)
            print(value["messages"][-1].content)
    
    return app.get_state({"configurable": {"thread_id": thread_id}})

if __name__ == "__main__":
    try:
        execute_workflow()
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure your .env file contains OPENAI_API_KEY and is UTF-8 encoded")