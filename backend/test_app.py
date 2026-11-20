"""
Automated Integration and Unit Tests for Adaptive Middleware Prototype
"""
import sys
import os
import pytest

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app
from network_monitoring import NetworkMonitor, NetworkMetrics
from session_state_manager import SessionManager, ExecutionMode, SessionStateMachine
from prediction_engine import predictor


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "active_sessions" in data


def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Adaptive Middleware Prototype"
    assert "endpoints" in data


def test_normal_mode_submission(client):
    session_id = f"test_norm_{os.urandom(4).hex()}"
    res = client.post(
        "/exam/submit",
        json={
            "student_id": "test_student",
            "exam_id": "test_exam",
            "answers": [
                {"question_id": 1, "answer": "A", "time_spent": 20},
                {"question_id": 2, "answer": "B", "time_spent": 25}
            ],
            "simulated_latency": 45
        },
        headers={"X-Session-Id": session_id}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status_code"] == 200
    assert data["body"]["status"] == "success"
    assert data["body"]["mode"] == "normal"
    assert data["body"]["_meta"]["mode"] == "normal"


def test_single_answer_submission(client):
    session_id = f"test_single_{os.urandom(4).hex()}"
    res = client.post(
        "/exam/question/1/answer",
        json={
            "question_id": 1,
            "answer": "C",
            "time_spent": 15
        },
        headers={"X-Session-Id": session_id}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["body"]["status"] == "success"


def test_degraded_batch_submission(client):
    session_id = f"test_deg_{os.urandom(4).hex()}"
    # Submitting partial batch should return 202 accumulating
    res = client.post(
        "/exam/batch",
        json={
            "student_id": "test_student",
            "exam_id": "test_exam",
            "answers": [{"question_id": 1, "answer": "A", "time_spent": 30}],
            "batch_size": 5,
            "finalize": False,
            "simulated_latency": 500
        },
        headers={"X-Session-Id": session_id}
    )
    assert res.status_code in [200, 202]
    data = res.json()
    assert data["body"]["mode"] == "degraded"


def test_critical_accumulate_submission_and_status(client):
    session_id = f"test_crit_{os.urandom(4).hex()}"
    res = client.post(
        "/exam/accumulate",
        json={
            "student_id": "test_student",
            "exam_id": "test_exam",
            "answers": [
                {"question_id": 1, "answer": "A", "time_spent": 30},
                {"question_id": 2, "answer": "B", "time_spent": 35}
            ],
            "simulated_latency": 2000
        },
        headers={"X-Session-Id": session_id}
    )
    assert res.status_code in [200, 202]
    data = res.json()
    assert data["body"]["mode"] == "critical"
    
    ack = data["body"].get("ack")
    assert ack is not None
    
    # Lookup status by ack_id
    res_status_ack = client.get(f"/status/{ack}")
    assert res_status_ack.status_code == 200
    assert res_status_ack.json()["status"] == "completed"
    
    # Lookup status by session_id
    res_status_session = client.get(f"/status/{session_id}")
    assert res_status_session.status_code == 200
    assert res_status_session.json()["status"] == "completed"


def test_network_simulation(client):
    session_id = f"test_sim_{os.urandom(4).hex()}"
    res = client.post(
        f"/session/{session_id}/simulate",
        json={"condition": "terrible"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "simulation" in data
    assert "session_status" in data
    assert data["session_status"]["session"]["current_mode"] in ["critical", "degraded", "normal"]


def test_compare_modes(client):
    res = client.get("/demo/compare-modes")
    assert res.status_code == 200
    data = res.json()
    assert "comparison" in data
    assert "summary" in data
    assert "normal" in data["comparison"]
    assert "degraded" in data["comparison"]
    assert "critical" in data["comparison"]


def test_fsm_transitions():
    fsm = SessionStateMachine()
    # High score -> normal
    assert fsm.transition(ExecutionMode.NORMAL, 0.9) == ExecutionMode.NORMAL
    # Drops below 0.6 -> degraded
    assert fsm.transition(ExecutionMode.NORMAL, 0.5) == ExecutionMode.DEGRADED
    # Drops below 0.3 -> critical
    assert fsm.transition(ExecutionMode.DEGRADED, 0.2) == ExecutionMode.CRITICAL
    # Recovers above 0.5 from critical -> degraded
    assert fsm.transition(ExecutionMode.CRITICAL, 0.55) == ExecutionMode.DEGRADED
    # Recovers above 0.8 from degraded -> normal
    assert fsm.transition(ExecutionMode.DEGRADED, 0.85) == ExecutionMode.NORMAL


def test_prediction_engine():
    # Stable features
    stable_features = {
        "avg_latency": 45.0,
        "std_latency": 5.0,
        "failure_rate": 0.0,
        "timeout_rate": 0.0,
        "avg_retries": 0.0,
        "request_velocity": 1.5,
        "jitter": 2.0,
        "total_requests": 10
    }
    score = predictor.predict_stability_score(stable_features)
    assert 0.0 <= score <= 1.0
    explanation = predictor.explain_prediction(stable_features)
    assert "stability_score" in explanation
    assert "explanations" in explanation


def test_delete_session(client):
    session_id = f"test_del_{os.urandom(4).hex()}"
    # Create the session by simulating network
    sim_res = client.post(f"/session/{session_id}/simulate", json={"condition": "good"})
    assert sim_res.status_code == 200

    # Verify session exists
    status_res = client.get(f"/session/{session_id}")
    assert status_res.status_code == 200

    # Delete session
    del_res = client.delete(f"/session/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == f"Session {session_id} reset"

    # Verify session no longer exists (returns 404)
    after_res = client.get(f"/session/{session_id}")
    assert after_res.status_code == 404


def test_mode_hint_dynamics(client):
    """Verify that mode_hint on dedicated test endpoints reliably transitions session mode"""
    session_id = f"test_hint_{os.urandom(4).hex()}"
    # Initially submit a normal mode request
    res_norm = client.post(
        "/exam/submit",
        json={"student_id": "s1", "exam_id": "e1", "answers": [{"question_id": 1, "answer": "A"}]},
        headers={"X-Session-Id": session_id}
    )
    assert res_norm.status_code == 200
    assert res_norm.json()["body"]["_meta"]["mode"] == "normal"

    # Now click/test critical mode - should reliably transition to critical
    res_crit = client.post(
        "/exam/accumulate",
        json={"student_id": "s1", "exam_id": "e1", "answers": [{"question_id": 2, "answer": "B"}]},
        headers={"X-Session-Id": session_id}
    )
    assert res_crit.status_code in [200, 202]
    assert res_crit.json()["body"]["_meta"]["mode"] == "critical"
    assert res_crit.json()["body"]["_meta"]["stability_score"] < 0.35


def test_async_queue_worker():
    """Verify background worker consumes and completes tasks from async_processing_queue"""
    import time
    from adaptation_controller import async_processing_queue, queued_tasks_store
    ack_id = f"test_worker_{int(time.time() * 1000)}"
    task_item = {
        "ack_id": ack_id,
        "session_id": "worker_sess",
        "answers": [{"q": 1, "a": "X"}],
        "timestamp": time.time(),
        "status": "queued"
    }
    queued_tasks_store[ack_id] = task_item
    async_processing_queue.put(task_item)

    # Wait briefly for worker to consume
    time.sleep(0.3)
    assert queued_tasks_store[ack_id]["status"] == "completed"
    assert "completed_at" in queued_tasks_store[ack_id]

