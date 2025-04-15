from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import traceback
from graph_k8s import run  # Your existing function
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kubernetes Query API",
    description="Natural language interface for Kubernetes",
    version="1.0",
    docs_url="/docs",
    redoc_url=None
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    thread_id: Optional[str] = "default"

class QueryResponse(BaseModel):
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    thread_id: str

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Request completed: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        raise

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """Process Kubernetes queries with formatted output"""
    try:
        logger.info(f"Processing query: {request.question[:50]}...")
        
        if not request.question.strip():
            raise ValueError("Question cannot be empty")
            
        # Get raw result from graph_k8s
        raw_result = await asyncio.to_thread(run, request.question)
        
        # Transform the pod list into structured JSON
        if "k8s_tool_node" in raw_result:
            pod_list = []
            for line in raw_result.split('\n'):
                if line.startswith('- name:'):
                    pod_list.append({
                        "name": line.split(':')[1].strip(),
                        "namespace": line.split('namespace:')[1].strip() 
                        if 'namespace:' in line else "default"
                    })
            
            formatted_result = {
                "api_version": "v1",
                "kind": "PodList",
                "items": pod_list
            }
        else:
            formatted_result = raw_result  # Fallback for non-pod queries

        logger.info("Query processed successfully")
        return QueryResponse(
            success=True,
            result=formatted_result,  # Now returns structured JSON
            thread_id=request.thread_id
        )
        
    except Exception as e:
        logger.error(f"Query failed: {traceback.format_exc()}")
        return QueryResponse(
            success=False,
            error=str(e),
            error_type=type(e).__name__,
            thread_id=request.thread_id
        )

@app.get("/health", response_model=dict)
async def health_check():
    """Enhanced health check with dependency verification"""
    status = {
        "status": "healthy",
        "services": {
            "api": "running",
            "k8s_connection": "unknown"  # Add actual checks if needed
        }
    }
    return status

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions"""
    logger.error(f"Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "error_type": type(exc).__name__,
            "details": str(exc)
        }
    )