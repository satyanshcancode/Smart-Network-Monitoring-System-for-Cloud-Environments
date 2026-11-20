"""
Adaptive Middleware Prototype - Main FastAPI Application
Demonstrates the patent with an exam submission system
"""
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import time
import uuid
import logging

from adaptation_controller import adaptation_controller, ExecutionMode
from session_state_manager import session_manager
from network_monitoring import network_monitor
from prediction_engine import predictor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Adaptive Middleware Prototype",
    description="Session-aware cloud middleware with dynamic execution mode adaptation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic Models ==============

class ExamAnswer(BaseModel):
    question_id: int
    answer: str
    time_spent: int = 0


class ExamSubmission(BaseModel):
    student_id: str
    exam_id: str
    answers: List[ExamAnswer]
    simulated_latency: float = 50
    retry_count: int = 0


class BatchSubmission(BaseModel):
    student_id: str
    exam_id: str
    answers: List[ExamAnswer]
    batch_size: int = 5
    finalize: bool = False
    simulated_latency: float = 50


class NetworkSimulationRequest(BaseModel):
    condition: str


class ModeTransitionRequest(BaseModel):
    target_mode: str


# ============== API Endpoints ==============

@app.get("/")
def root():
    """Root endpoint with API info"""
    return {
        "name": "Adaptive Middleware Prototype",
        "version": "1.0.0",
        "description": "Session-aware cloud middleware with dynamic execution mode adaptation",
        "endpoints": {
            "exam": {
                "normal": "/exam/submit (POST)",
                "degraded": "/exam/batch (POST)",
                "critical": "/exam/accumulate (POST)"
            },
            "monitoring": {
                "session_status": "/session/{session_id} (GET)",
                "all_sessions": "/sessions (GET)",
                "simulate_network": "/session/{session_id}/simulate (POST)"
            },
            "demo": {
                "compare_modes": "/demo/compare-modes (GET)"
            }
        }
    }


@app.post("/exam/submit")
def submit_exam(
    submission: ExamSubmission,
    x_session_id: Optional[str] = Header(None),
    x_simulated_latency: Optional[float] = Header(None)
):
    """Normal Mode: Granular exam submission"""
    session_id = x_session_id or str(uuid.uuid4())
    latency = x_simulated_latency or submission.simulated_latency
    
    request_data = {
        "student_id": submission.student_id,
        "exam_id": submission.exam_id,
        "answers": [ans.dict() for ans in submission.answers],
        "simulated_latency": latency,
        "retry_count": submission.retry_count,
        "mode_hint": "normal"
    }
    
    response = adaptation_controller.handle_request(request_data, session_id)
    return response


@app.post("/exam/question/{question_id}/answer")
def submit_single_answer(
    question_id: int,
    answer: ExamAnswer,
    x_session_id: Optional[str] = Header(None),
    x_simulated_latency: Optional[float] = Header(None)
):
    """Normal Mode: Submit a single question answer"""
    session_id = x_session_id or str(uuid.uuid4())
    latency = x_simulated_latency or 50
    
    request_data = {
        "question_id": question_id,
        "answer": answer.dict(),
        "simulated_latency": latency,
        "mode_hint": "normal"
    }
    
    response = adaptation_controller.handle_request(request_data, session_id)
    return response


@app.post("/exam/batch")
def submit_batch(
    submission: BatchSubmission,
    x_session_id: Optional[str] = Header(None),
    x_simulated_latency: Optional[float] = Header(None)
):
    """Degraded Mode: Batch exam submission"""
    session_id = x_session_id or str(uuid.uuid4())
    latency = x_simulated_latency or submission.simulated_latency
    
    request_data = {
        "student_id": submission.student_id,
        "exam_id": submission.exam_id,
        "answers": [ans.dict() for ans in submission.answers],
        "batch_size": submission.batch_size,
        "finalize": submission.finalize,
        "simulated_latency": latency,
        "mode_hint": "degraded"
    }
    
    response = adaptation_controller.handle_request(request_data, session_id)
    return response


@app.post("/exam/accumulate")
def submit_accumulated(
    submission: Dict[str, Any],
    x_session_id: Optional[str] = Header(None),
    x_simulated_latency: Optional[float] = Header(None)
):
    """Critical Mode: Accumulated exam submission"""
    session_id = x_session_id or str(uuid.uuid4())
    # FIX #1: Added proper null checking for latency
    latency = x_simulated_latency
    if latency is None:
        latency = submission.get('simulated_latency')
    if latency is None:
        latency = 50
    
    # Ensure latency is a valid number
    try:
        latency = float(latency)
    except (TypeError, ValueError):
        latency = 50
    
    request_data = {
        **submission,
        "simulated_latency": latency,
        "mode_hint": "critical",
        "is_final": True
    }
    
    response = adaptation_controller.handle_request(request_data, session_id)
    return response


@app.get("/session/{session_id}")
def get_session_status(session_id: str):
    """Get detailed status of a session"""
    status = adaptation_controller.get_session_status(session_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@app.get("/sessions")
def get_all_sessions():
    """Get all active sessions"""
    return adaptation_controller.get_all_sessions()


@app.post("/session/{session_id}/simulate")
def simulate_network_condition(
    session_id: str,
    request: NetworkSimulationRequest
):
    """Simulate network conditions for a session"""
    result = adaptation_controller.simulate_network_condition(
        session_id, request.condition
    )
    status = adaptation_controller.get_session_status(session_id)
    
    return {
        "simulation": result,
        "session_status": status
    }


@app.post("/session/{session_id}/force-mode")
def force_mode(session_id: str, request: ModeTransitionRequest):
    """Force a session into a specific mode (for demo purposes)"""
    session = session_manager.get_or_create_session(session_id)
    
    mode_map = {
        'normal': ExecutionMode.NORMAL,
        'degraded': ExecutionMode.DEGRADED,
        'critical': ExecutionMode.CRITICAL
    }
    
    if request.target_mode not in mode_map:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode. Choose from: {list(mode_map.keys())}"
        )
    
    if request.target_mode == 'normal':
        adaptation_controller.simulate_network_condition(session_id, 'good')
    elif request.target_mode == 'degraded':
        adaptation_controller.simulate_network_condition(session_id, 'poor')
    else:
        adaptation_controller.simulate_network_condition(session_id, 'terrible')
    
    features = network_monitor.get_session_features(session_id)
    stability_score = predictor.predict_stability_score(features)
    new_mode = session_manager.update_session_mode(session_id, stability_score)
    
    return {
        "message": f"Session {session_id} mode set to {new_mode.value}",
        "stability_score": round(stability_score, 4),
        "session": session.to_dict()
    }


@app.get("/status/{ack_id}")
def check_async_status(ack_id: str):
    """Check status of async processing (for critical mode)"""
    # FIX #7: Actually retrieve queued data instead of returning fake status
    return adaptation_controller.get_queued_status(ack_id)


@app.delete("/session/{session_id}")
def reset_session(session_id: str):
    """Reset/clear a session"""
    network_monitor.reset_session(session_id)
    return {"message": f"Session {session_id} reset"}


@app.get("/demo/compare-modes")
def compare_modes():
    """Compare all three modes with example data"""
    test_answers = [
        {"question_id": i, "answer": chr(65 + (i % 4)), "time_spent": 30 + i * 5}
        for i in range(1, 11)
    ]
    
    results = {}
    
    for mode_name, latency in [('normal', 50), ('degraded', 500), ('critical', 2000)]:
        session_id = f"demo_{mode_name}_{int(time.time())}"
        
        if mode_name == 'normal':
            adaptation_controller.simulate_network_condition(session_id, 'good')
        elif mode_name == 'degraded':
            adaptation_controller.simulate_network_condition(session_id, 'poor')
        else:
            adaptation_controller.simulate_network_condition(session_id, 'terrible')
        
        request_data = {
            "student_id": "demo_student",
            "exam_id": "demo_exam",
            "answers": test_answers,
            "simulated_latency": latency,
            "finalize": True
        }
        
        response = adaptation_controller.handle_request(request_data, session_id)
        status = adaptation_controller.get_session_status(session_id)
        
        results[mode_name] = {
            "response": response,
            "session": status.get('session', {}),
            "prediction": status.get('prediction', {})
        }
    
    return {
        "comparison": results,
        "summary": {
            "normal": {
                "description": "Granular, step-by-step processing",
                "network_trips": "10+ (one per question)",
                "best_for": "Good network conditions"
            },
            "degraded": {
                "description": "Batch processing with compression",
                "network_trips": "2-3 (batched)",
                "best_for": "Moderate network issues"
            },
            "critical": {
                "description": "Minimal communication, async processing",
                "network_trips": "1-2 (single transmission)",
                "best_for": "Severe network degradation"
            }
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "active_sessions": len(session_manager.get_all_sessions())
    }


@app.on_event("startup")
def startup_event():
    """Initialize on startup"""
    logger.info("=" * 60)
    logger.info("Adaptive Middleware Prototype Starting...")
    logger.info("=" * 60)
    logger.info("Patent: Session-aware cloud middleware with dynamic")
    logger.info("        execution mode adaptation based on network conditions")
    logger.info("=" * 60)
    logger.info("API Documentation: http://localhost:8000/docs")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")