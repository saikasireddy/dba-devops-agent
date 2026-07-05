import os
import psycopg2
from typing import Annotated, Literal, TypedDict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from agent_skills import COCKROACH_SKILLS

# Load API keys
load_dotenv()

# 1. Initialize LLMs
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))

# 2. Configure CockroachDB tools
COCKROACH_MCP_URL = "https://cockroachlabs.cloud/mcp"
CLUSTER_ID = os.getenv("COCKROACH_CLUSTER_ID")

@tool
def fetch_cluster_metrics() -> str:
    """Useful for checking database latency, QPS, and slow queries in CockroachDB."""
    return "WARNING: Found a slow query doing a full table scan on the 'users' table. Missing index on 'status' column."

@tool
def query_database_tables() -> str:
    """Useful for seeing what tables exist in the live CockroachDB database."""
    db_url = os.getenv("COCKROACH_DB_URL").replace("sslmode=verify-full", "sslmode=require")
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES;")
            tables = cur.fetchall()
            return f"Found the following tables in the live database: {tables}"
    except Exception as e:
        return f"Failed to connect to database: {e}"
    finally:
        if 'conn' in locals() and conn:
            conn.close()

tools = [fetch_cluster_metrics, query_database_tables] + COCKROACH_SKILLS
llm_with_tools = llm.bind_tools(tools)

# --- ADK State Graph Definition ---

class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    sql_proposed: str
    qa_approved: bool

def dba_node(state: GraphState):
    """The DBA Agent analyzes the problem and writes SQL."""
    print("[DBA Agent] Thinking...")
    messages = state.get("messages", [])
    sys_msg = SystemMessage(content="You are an expert CockroachDB Database Administrator. Analyze the request, use your tools if needed, and propose a SQL fix. You MUST provide the final SQL fix wrapped exactly in ```sql ... ``` blocks. Do not end your response without providing the SQL block.")
    
    # We pass the system message + history to the LLM
    response = llm.invoke([sys_msg] + messages)
    
    # Extract SQL if present in the response
    content_str = str(response.content)
    if isinstance(response.content, list):
        text_parts = [item["text"] for item in response.content if isinstance(item, dict) and "text" in item]
        content_str = " ".join(text_parts)

    print(f"\n--- [DBA Output] ---\n{content_str}\n-------------------\n")

    sql_proposed = ""
    if "```sql" in content_str:
        try:
            sql_proposed = content_str.split("```sql")[1].split("```")[0].strip()
        except:
            pass
            
    return {"messages": [response], "sql_proposed": sql_proposed}

def qa_node(state: GraphState):
    """The QA Agent reviews the DBA's SQL."""
    print("[QA Agent] Reviewing SQL...")
    sql_proposed = state.get("sql_proposed", "")
    
    if not sql_proposed:
        return {"qa_approved": False, "messages": [AIMessage(content="[QA Agent]: No SQL was proposed by the DBA.")]}
        
    prompt = f"You are a strict QA Reviewer. Review this SQL: \n{sql_proposed}\nIf it is safe and correct CockroachDB syntax, reply ONLY with 'APPROVED'. If there is a problem, explain why and reject it."
    response = llm.invoke([HumanMessage(content=prompt)])
    
    approved = "APPROVED" in response.content.upper()
    return {"qa_approved": approved, "messages": [AIMessage(content=f"[QA Review]: {response.content}")]}

def execute_sql_node(state: GraphState):
    """Executes the approved SQL after human permission."""
    print("[Executor] Applying SQL to database...")
    sql_proposed = state.get("sql_proposed", "")
    # In a real app, we would run psycopg2 here. For safety in this demo, we mock success.
    return {"messages": [AIMessage(content=f"SUCCESS! Executed: {sql_proposed}")]}

from langgraph.prebuilt import ToolNode

def route_dba(state: GraphState) -> Literal["tools", "qa_node"]:
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        print("[DBA Agent] Calling tools...")
        return "tools"
    return "qa_node"

def route_qa(state: GraphState) -> Literal["execute_sql_node", "dba_node", END]:
    if state.get("qa_approved"):
        return "execute_sql_node"
    elif not state.get("sql_proposed"):
        return END # No SQL needed, just a conversational response
    else:
        return "dba_node" # Send back to DBA to fix

# Build the Graph
workflow = StateGraph(GraphState)
workflow.add_node("dba_node", dba_node)
workflow.add_node("tools", ToolNode(tools))
workflow.add_node("qa_node", qa_node)
workflow.add_node("execute_sql_node", execute_sql_node)

workflow.add_edge(START, "dba_node")
workflow.add_conditional_edges("dba_node", route_dba, {"tools": "tools", "qa_node": "qa_node"})
workflow.add_edge("tools", "dba_node")
workflow.add_conditional_edges("qa_node", route_qa)
workflow.add_edge("execute_sql_node", END)

# Add Memory and Human-in-the-Loop Interrupt before executing
memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory, interrupt_before=["execute_sql_node"])


# --- FastAPI Backend ---
app = FastAPI(title="ADK Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    schema_sql: str = ""
    thread_id: str = "default_session"
    action: str = "start" # 'start' or 'resume'

@app.post("/analyze")
def analyze_database(request: AnalyzeRequest):
    print(f"🤖 ADK API called. Action: {request.action}, Thread: {request.thread_id}")
    config = {"configurable": {"thread_id": request.thread_id}}
    
    try:
        if request.action == "resume":
            # Resume the graph after human approval
            response = app_graph.invoke(None, config)
        else:
            # Start a new query
            if request.schema_sql:
                task_prompt = f"Analyze this schema:\n{request.schema_sql}\nPropose a SQL fix."
            else:
                task_prompt = "Check what tables exist in the live CockroachDB database and tell me what you found."
                
            response = app_graph.invoke({"messages": [("user", task_prompt)]}, config)
            
        # Check current state to see if we are paused for Human-In-The-Loop
        current_state = app_graph.get_state(config)
        needs_approval = len(current_state.next) > 0 and current_state.next[0] == "execute_sql_node"
        
        # Extract the latest messages
        history = current_state.values.get("messages", [])
        
        # Build the response text from the DBA and QA agents
        result_text = ""
        for msg in history[-3:]: # Get the last few interactions
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, list):
                    text_parts = [item["text"] for item in content if isinstance(item, dict) and "text" in item]
                    content = " ".join(text_parts)
                
                if str(content).strip():
                    result_text += str(content) + "\n\n"
                
        sql_proposed = current_state.values.get("sql_proposed", "")
        
        return {
            "status": "success", 
            "recommendation": result_text,
            "needs_approval": needs_approval,
            "sql_proposed": sql_proposed if needs_approval else None
        }
    except Exception as e:
        error_msg = str(e)
        if "429 RESOURCE_EXHAUSTED" in error_msg:
            return {"status": "error", "recommendation": "Gemini API Rate Limit Exceeded. Please wait 30s."}
        return {"status": "error", "recommendation": f"Backend Error: {error_msg}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
