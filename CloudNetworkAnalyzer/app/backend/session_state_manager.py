"""
Session State Manager
Finite State Machine for managing session execution modes
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime
import time
import os


class ExecutionMode(Enum):
    """Execution modes for adaptive behavior"""
    NORMAL = "normal"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class StateTransition:
    """Represents a state transition event"""
    def __init__(self, from_mode: ExecutionMode, to_mode: ExecutionMode, 
                 stability_score: float, timestamp: float = None):
        self.from_mode = from_mode
        self.to_mode = to_mode
        self.stability_score = stability_score
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict:
        return {
            'from_mode': self.from_mode.value,
            'to_mode': self.to_mode.value,
            'stability_score': round(self.stability_score, 4),
            'timestamp': self.timestamp,
            'datetime': datetime.fromtimestamp(self.timestamp).isoformat()
        }


class SessionStateMachine:
    """Finite State Machine for session mode transitions"""
    
    # FIX #10: Thresholds now read from environment variables with sensible defaults.
    # To override, set these before starting the backend:
    #   export FSM_THRESHOLD_TO_DEGRADED=0.6
    #   export FSM_THRESHOLD_TO_CRITICAL=0.3
    #   export FSM_THRESHOLD_DEGRADED_TO_NORMAL=0.8
    #   export FSM_THRESHOLD_CRITICAL_TO_DEGRADED=0.5
    THRESHOLDS = {
        'to_degraded':          float(os.environ.get('FSM_THRESHOLD_TO_DEGRADED',          0.6)),
        'to_critical':          float(os.environ.get('FSM_THRESHOLD_TO_CRITICAL',           0.3)),
        'degraded_to_normal':   float(os.environ.get('FSM_THRESHOLD_DEGRADED_TO_NORMAL',   0.8)),
        'critical_to_degraded': float(os.environ.get('FSM_THRESHOLD_CRITICAL_TO_DEGRADED', 0.5)),
    }
    
    def __init__(self):
        self.transitions: List[StateTransition] = []
        self._transition_callbacks: List[Callable] = []
    
    def on_transition(self, callback: Callable):
        """Register a callback for state transitions"""
        self._transition_callbacks.append(callback)
    
    def transition(self, current_mode: ExecutionMode, stability_score: float) -> ExecutionMode:
        """Determine next state based on current state and stability score"""
        new_mode = self._calculate_transition(current_mode, stability_score)
        
        if new_mode != current_mode:
            transition = StateTransition(current_mode, new_mode, stability_score)
            self.transitions.append(transition)
            
            # Notify callbacks
            for callback in self._transition_callbacks:
                callback(transition)
        
        return new_mode
    
    def _calculate_transition(self, current_mode: ExecutionMode, stability_score: float) -> ExecutionMode:
        """Core FSM logic"""
        if current_mode == ExecutionMode.NORMAL:
            if stability_score < self.THRESHOLDS['to_critical']:
                return ExecutionMode.CRITICAL
            elif stability_score < self.THRESHOLDS['to_degraded']:
                return ExecutionMode.DEGRADED
            return ExecutionMode.NORMAL
            
        elif current_mode == ExecutionMode.DEGRADED:
            if stability_score < self.THRESHOLDS['to_critical']:
                return ExecutionMode.CRITICAL
            elif stability_score > self.THRESHOLDS['degraded_to_normal']:
                return ExecutionMode.NORMAL
            return ExecutionMode.DEGRADED
            
        elif current_mode == ExecutionMode.CRITICAL:
            if stability_score > self.THRESHOLDS['critical_to_degraded']:
                return ExecutionMode.DEGRADED
            return ExecutionMode.CRITICAL
        
        return current_mode
    
    def get_transition_history(self) -> List[Dict]:
        """Get history of all transitions"""
        return [t.to_dict() for t in self.transitions]


@dataclass
class SessionContext:
    """Complete session context including state, metrics, and accumulated data"""
    session_id: str
    current_mode: ExecutionMode = ExecutionMode.NORMAL
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    accumulated_data: List[Dict] = field(default_factory=list)
    transition_history: List[Dict] = field(default_factory=list)
    current_stability_score: float = 1.0
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    def record_request(self):
        """Record a new request"""
        self.request_count += 1
        self.update_activity()
    
    def record_success(self):
        """Record a successful operation"""
        self.success_count += 1
        self.update_activity()
    
    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.update_activity()
    
    def add_accumulated_data(self, data: Dict):
        """Add data to accumulation buffer (for batching)"""
        self.accumulated_data.append(data)
    
    def clear_accumulated_data(self):
        """Clear accumulation buffer"""
        self.accumulated_data = []
    
    def get_accumulated_batch(self) -> List[Dict]:
        """Get accumulated data as a batch"""
        return self.accumulated_data.copy()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'current_mode': self.current_mode.value,
            'created_at': self.created_at,
            'last_activity': self.last_activity,
            'request_count': self.request_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'accumulated_count': len(self.accumulated_data),
            'current_stability_score': round(self.current_stability_score, 4),
            'transition_history': self.transition_history
        }


class SessionManager:
    """Manages all active sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionContext] = {}
        self.state_machines: Dict[str, SessionStateMachine] = {}
    
    def get_or_create_session(self, session_id: str) -> SessionContext:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionContext(session_id=session_id)
            self.state_machines[session_id] = SessionStateMachine()
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session if it exists"""
        return self.sessions.get(session_id)
    
    def get_state_machine(self, session_id: str) -> Optional[SessionStateMachine]:
        """Get state machine for session"""
        return self.state_machines.get(session_id)
    
    def update_session_mode(self, session_id: str, stability_score: float) -> ExecutionMode:
        """Update session mode based on stability score"""
        session = self.get_or_create_session(session_id)
        state_machine = self.state_machines[session_id]
        
        new_mode = state_machine.transition(session.current_mode, stability_score)
        
        if new_mode != session.current_mode:
            session.transition_history.append({
                'from': session.current_mode.value,
                'to': new_mode.value,
                'stability_score': round(stability_score, 4),
                'timestamp': time.time()
            })
            session.current_mode = new_mode
        
        session.current_stability_score = stability_score
        return new_mode
    
    def get_all_sessions(self) -> Dict[str, Dict]:
        """Get all sessions as dictionaries"""
        return {sid: session.to_dict() for sid, session in self.sessions.items()}
    
    def cleanup_inactive_sessions(self, max_inactive_seconds: float = 3600):
        """Remove inactive sessions"""
        current_time = time.time()
        inactive_sessions = [
            sid for sid, session in self.sessions.items()
            if current_time - session.last_activity > max_inactive_seconds
        ]
        for sid in inactive_sessions:
            del self.sessions[sid]
            del self.state_machines[sid]
        return len(inactive_sessions)


# Global session manager
session_manager = SessionManager()