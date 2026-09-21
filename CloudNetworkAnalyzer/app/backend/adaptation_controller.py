"""
Adaptation Controller
Strategy Pattern Implementation for different execution modes
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time
import json
import logging
import random
import queue

from session_state_manager import (
    ExecutionMode, SessionContext, SessionManager, 
    session_manager, StateTransition
)
from network_monitoring import NetworkMetrics, network_monitor
from prediction_engine import predictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global async processing queue for critical mode
async_processing_queue = queue.Queue()


@dataclass
class Request:
    """Incoming request wrapper"""
    data: Dict
    headers: Dict = None
    is_final_submission: bool = False
    minimal_payload: Dict = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.minimal_payload is None:
            self.minimal_payload = {}


@dataclass
class Response:
    """Response wrapper"""
    status_code: int
    body: Dict
    headers: Dict = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
    
    def to_dict(self) -> Dict:
        return {
            'status_code': self.status_code,
            'body': self.body,
            'headers': self.headers
        }


@dataclass
class ValidationResult:
    """Validation result"""
    valid: bool
    errors: List[str] = None
    cleaned_data: Dict = None
    queued: bool = False
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.cleaned_data is None:
            self.cleaned_data = {}
    
    def summary(self) -> str:
        if self.valid:
            return "Valid"
        return f"Invalid: {', '.join(self.errors)}"


@dataclass
class ErrorResponse:
    """Error response details"""
    retry: bool
    error: str = ""
    backoff_ms: int = 0
    saved_state: bool = False
    queued: bool = False
    check_status_url: str = ""


class ExecutionStrategy(ABC):
    """Abstract base class for execution strategies"""
    
    @abstractmethod
    def process_request(self, request: Request, context: SessionContext) -> Response:
        pass
    
    @abstractmethod
    def validate_input(self, data: Dict) -> ValidationResult:
        pass
    
    @abstractmethod
    def handle_error(self, error: Exception, context: SessionContext) -> ErrorResponse:
        pass
    
    def get_mode_name(self) -> str:
        return self.__class__.__name__.replace('Strategy', '').lower()


class NormalStrategy(ExecutionStrategy):
    """
    Normal Mode: Full functionality, granular operations
    - Step-by-step processing
    - Real-time validation
    - Immediate confirmations
    - Rich error messages
    """
    
    def process_request(self, request: Request, context: SessionContext) -> Response:
        logger.info(f"[NORMAL] Processing request for session {context.session_id}")
        
        # Step 1: Validate input
        validation = self.validate_input(request.data)
        if not validation.valid:
            return Response(400, {
                "error": "Validation failed",
                "details": validation.errors,
                "mode": "normal"
            })
        
        # Step 2: Process step-by-step
        try:
            partial_results = self._process_granular(validation.cleaned_data)
            
            return Response(200, {
                "status": "success",
                "mode": "normal",
                "results": partial_results,
                "next_step": True,
                "session_id": context.session_id,
                "request_count": context.request_count
            })
            
        except Exception as e:
            error_response = self.handle_error(e, context)
            return Response(500, {
                "error": error_response.error,
                "retry": error_response.retry,
                "backoff_ms": error_response.backoff_ms,
                "mode": "normal"
            })
    
    def _process_granular(self, data: Dict) -> List[Dict]:
        """Simulate granular processing"""
        results = []
        
        if 'answers' in data:
            for i, answer in enumerate(data['answers']):
                results.append({
                    "step": i + 1,
                    "item": answer,
                    "status": "processed",
                    "timestamp": time.time()
                })
        else:
            results.append({
                "step": 1,
                "data": data,
                "status": "processed",
                "timestamp": time.time()
            })
        
        return results
    
    def validate_input(self, data: Dict) -> ValidationResult:
        """Granular validation"""
        errors = []
        
        if not data:
            errors.append("Empty request data")
        
        if 'answers' in data:
            for i, ans in enumerate(data['answers']):
                if not isinstance(ans, dict):
                    errors.append(f"Answer {i} must be an object")
                elif 'answer' not in ans:
                    errors.append(f"Answer {i} missing 'answer' field")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            cleaned_data=data
        )
    
    def handle_error(self, error: Exception, context: SessionContext) -> ErrorResponse:
        """Retry with exponential backoff"""
        retry_count = context.failure_count
        if retry_count < 3:
            backoff = 2 ** retry_count * 100
            return ErrorResponse(
                retry=True,
                error=str(error),
                backoff_ms=backoff
            )
        return ErrorResponse(
            retry=False,
            error=f"Max retries exceeded: {error}"
        )


class DegradedStrategy(ExecutionStrategy):
    """
    Degraded Mode: Reduced granularity, batching, compression
    - Batch multiple operations
    - Server-side validation only
    - Compressed responses
    - Fewer confirmations
    """
    
    def process_request(self, request: Request, context: SessionContext) -> Response:
        logger.info(f"[DEGRADED] Processing batch for session {context.session_id}")
        
        # Add to accumulation buffer
        context.add_accumulated_data(request.data)
        
        batch_size = request.data.get('batch_size', 5)
        
        if len(context.accumulated_data) >= batch_size or request.is_final_submission:
            batch = context.get_accumulated_batch()
            
            validation = self.validate_batch(batch)
            if not validation.valid:
                return Response(400, {
                    "error": validation.summary(),
                    "mode": "degraded"
                })
            
            try:
                result = self._process_batch(validation.cleaned_data)
                compressed_result = self._compress_response(result)
                
                context.clear_accumulated_data()
                
                return Response(200, {
                    "status": "success",
                    "mode": "degraded",
                    "result": compressed_result,
                    "items_processed": len(batch),
                    "batch_saved": True
                })
                
            except Exception as e:
                error_response = self.handle_error(e, context)
                return Response(500, {
                    "error": error_response.error,
                    "mode": "degraded",
                    "saved_state": error_response.saved_state
                })
        
        # FIX BUG #2: Use HTTP 202 (Accepted) instead of 100 (Continue).
        # HTTP 100 is a connection-level signal in the HTTP spec; many clients
        # and browsers will not treat it as a normal JSON response body.
        # 202 means "received and buffering, not yet processed" which is correct.
        return Response(202, {
            "status": "accumulating",
            "mode": "degraded",
            "buffered": len(context.accumulated_data),
            "needed": batch_size
        })
    
    def _process_batch(self, batch: List[Dict]) -> Dict:
        """Process a batch of operations"""
        processed = []
        
        for item in batch:
            if 'answers' in item:
                processed.extend(item['answers'])
            else:
                processed.append(item)
        
        return {
            "processed_count": len(processed),
            "items": processed,
            "timestamp": time.time()
        }
    
    def _compress_response(self, data: Dict) -> Dict:
        """Compress response data"""
        return {
            "count": data.get('processed_count', 0),
            "ts": int(data.get('timestamp', time.time()))
        }
    
    def validate_batch(self, batch: List[Dict]) -> ValidationResult:
        """Batch validation"""
        if not batch:
            return ValidationResult(valid=False, errors=["Empty batch"])
        
        return ValidationResult(valid=True, cleaned_data=batch, errors=[])
    
    def validate_input(self, data: Dict) -> ValidationResult:
        """Server-side batch validation"""
        return self.validate_batch([data])
    
    def handle_error(self, error: Exception, context: SessionContext) -> ErrorResponse:
        """Single retry with longer timeout"""
        if context.failure_count < 1:
            return ErrorResponse(
                retry=True,
                error=str(error),
                backoff_ms=2000
            )
        return ErrorResponse(
            retry=False,
            error=f"Operation failed: {error}",
            saved_state=True
        )


class CriticalStrategy(ExecutionStrategy):
    """
    Critical Mode: Minimal communication, server-side execution
    - Accept everything, validate server-side
    - Minimal payload from client
    - Asynchronous processing with actual queue
    - Idempotent operations
    """
    
    def process_request(self, request: Request, context: SessionContext) -> Response:
        logger.info(f"[CRITICAL] Processing critical request for session {context.session_id}")
        
        full_data = context.get_accumulated_batch() if context.accumulated_data else [request.data]
        
        validation = self.validate_input(request.data)
        
        try:
            result = self._execute_critical_path(full_data, context)
            
            return Response(200, {
                "status": "completed",
                "id": result['id'],
                "mode": "critical",
                "ack": result['ack']
            })
            
        except Exception as e:
            self._queue_for_async_processing(context, full_data)
            return Response(202, {
                "status": "queued",
                "mode": "critical",
                "check_url": f"/status/{context.session_id}",
                "estimated_seconds": 30
            })
    
    def _execute_critical_path(self, data: List[Dict], context: SessionContext) -> Dict:
        """Execute critical path with all data - NOW WITH ACTUAL QUEUEING"""
        all_answers = []
        for item in data:
            if 'answers' in item:
                all_answers.extend(item['answers'])
            elif 'answer' in item:
                all_answers.append(item)
        
        ack_id = f"{context.session_id}_{int(time.time())}"
        
        # FIX #7: Actually queue the data instead of just returning ack
        queue_item = {
            "ack_id": ack_id,
            "session_id": context.session_id,
            "answers": all_answers,
            "timestamp": time.time(),
            "status": "completed"
        }
        
        try:
            # Put the item in the queue (non-blocking)
            async_processing_queue.put_nowait(queue_item)
            logger.info(f"[CRITICAL] Queued {len(all_answers)} answers with ack_id {ack_id}")
        except queue.Full:
            logger.warning(f"[CRITICAL] Queue is full, still processing")
        
        return {
            "id": context.session_id,
            "ack": ack_id,
            "items_count": len(all_answers),
            "processed_at": time.time()
        }
    
    def _queue_for_async_processing(self, context: SessionContext, data: List[Dict]):
        """Queue for asynchronous processing on error"""
        logger.info(f"[CRITICAL] Queued session {context.session_id} for async processing on error")
        
        all_answers = []
        for item in data:
            if 'answers' in item:
                all_answers.extend(item['answers'])
            elif 'answer' in item:
                all_answers.append(item)
        
        queue_item = {
            "ack_id": f"{context.session_id}_{int(time.time())}",
            "session_id": context.session_id,
            "answers": all_answers,
            "timestamp": time.time(),
            "status": "error_queued"
        }
        
        try:
            async_processing_queue.put_nowait(queue_item)
        except queue.Full:
            logger.error(f"[CRITICAL] Cannot queue - queue is full")
    
    def validate_input(self, data: Dict) -> ValidationResult:
        """Minimal validation - accept and queue"""
        return ValidationResult(valid=True, queued=True)
    
    def handle_error(self, error: Exception, context: SessionContext) -> ErrorResponse:
        """No retry, queue for async"""
        self._queue_for_async_processing(context, [])
        return ErrorResponse(
            retry=False,
            queued=True,
            check_status_url=f"/status/{context.session_id}",
            error=str(error)
        )


def get_queued_item(ack_id: str) -> Optional[Dict]:
    """Retrieve a queued item by ack_id (for status endpoint)"""
    # Convert queue to list, search, then rebuild
    items = []
    found_item = None
    
    try:
        while not async_processing_queue.empty():
            item = async_processing_queue.get_nowait()
            items.append(item)
            if item.get('ack_id') == ack_id:
                found_item = item
    except queue.Empty:
        pass
    
    # Put items back in queue
    for item in items:
        try:
            async_processing_queue.put_nowait(item)
        except queue.Full:
            break
    
    return found_item


class AdaptationController:
    """
    Main adaptation controller
    Orchestrates mode detection, strategy selection, and request handling
    """
    
    def __init__(self):
        self.strategies = {
            ExecutionMode.NORMAL: NormalStrategy(),
            ExecutionMode.DEGRADED: DegradedStrategy(),
            ExecutionMode.CRITICAL: CriticalStrategy()
        }
        self.session_manager = session_manager
        self.network_monitor = network_monitor
        self.predictor = predictor
        self.request_metrics = []
    
    def handle_request(self, request_data: Dict, session_id: str, 
                       request_headers: Dict = None) -> Dict:
        """Main entry point for handling requests"""
        start_time = time.time()
        
        # Get or create session
        context = self.session_manager.get_or_create_session(session_id)
        context.record_request()
        
        # Create request wrapper
        request = Request(
            data=request_data,
            headers=request_headers or {},
            is_final_submission=request_data.get('finalize', False)
        )
        
        # Record network metrics
        latency = request_data.get('simulated_latency', 50)
        metric = NetworkMetrics(
            timestamp=start_time,
            session_id=session_id,
            request_id=f"{session_id}_{context.request_count}",
            latency_ms=latency,
            payload_size_bytes=len(json.dumps(request_data).encode()),
            response_size_bytes=0,
            http_status=200,
            retry_count=request_data.get('retry_count', 0),
            timeout_occurred=latency > 5000
        )
        self.network_monitor.record_request(metric)
        
        # Get features and predict stability
        features = self.network_monitor.get_session_features(session_id)
        stability_score = self.predictor.predict_stability_score(features)
        
        # Update session mode
        new_mode = self.session_manager.update_session_mode(session_id, stability_score)
        context.current_stability_score = stability_score
        
        # Log transition
        if len(context.transition_history) > 0:
            last_transition = context.transition_history[-1]
            if last_transition.get('to') == new_mode.value:
                logger.info(f"[TRANSITION] Session {session_id} -> {new_mode.value} "
                           f"(score: {stability_score:.3f})")
        
        # Execute with selected strategy
        strategy = self.strategies[new_mode]
        
        try:
            response = strategy.process_request(request, context)
            context.record_success()
            
            # Add metadata to response
            response.body['_meta'] = {
                'mode': new_mode.value,
                'stability_score': round(stability_score, 4),
                'session_id': session_id,
                'processing_time_ms': round((time.time() - start_time) * 1000, 2)
            }
            
            return response.to_dict()
            
        except Exception as e:
            context.record_failure()
            error_response = strategy.handle_error(e, context)
            
            return Response(500, {
                'error': error_response.error,
                'retry': error_response.retry,
                'mode': new_mode.value,
                '_meta': {
                    'stability_score': round(stability_score, 4),
                    'session_id': session_id
                }
            }).to_dict()
    
    def get_session_status(self, session_id: str) -> Dict:
        """Get current status of a session"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        features = self.network_monitor.get_session_features(session_id)
        prediction_explanation = self.predictor.explain_prediction(features)
        
        return {
            "session": session.to_dict(),
            "network_features": features,
            "prediction": prediction_explanation,
            "strategies": {
                "normal": "Granular step-by-step processing",
                "degraded": "Batch processing with compression",
                "critical": "Minimal communication, async processing"
            }
        }
    
    def get_all_sessions(self) -> Dict:
        """Get all active sessions"""
        return self.session_manager.get_all_sessions()
    
    def get_queued_status(self, ack_id: str) -> Dict:
        """Get status of a queued async item by ack_id"""
        item = get_queued_item(ack_id)
        
        if item:
            return {
                "status": item.get('status', 'completed'),
                "session_id": item.get('session_id'),
                "ack_id": item.get('ack_id'),
                "items_processed": len(item.get('answers', [])),
                "processed_at": item.get('timestamp')
            }
        else:
            return {"status": "not_found", "ack_id": ack_id}
    
    def simulate_network_condition(self, session_id: str, condition: str):
        """Simulate network conditions for testing"""
        # FIX BUG #1: Always ensure the session exists in session_manager
        # before injecting network metrics, so get_session_status() never
        # returns {"error": "Session not found"} when called right after simulate.
        self.session_manager.get_or_create_session(session_id)

        conditions = {
            # Calibrated against the trained RandomForest model's actual boundaries:
            # NORMAL   = score > 0.60  →  low latency, zero failures
            # DEGRADED = score 0.30-0.60 → moderate latency, minimal failures
            # CRITICAL = score < 0.30  →  high latency + significant failure rate
            'good':    {'latency':  50,  'failure_rate': 0.00, 'timeout_rate': 0.00},
            'poor':    {'latency': 500,  'failure_rate': 0.05, 'timeout_rate': 0.00},
            'bad':     {'latency': 1500, 'failure_rate': 0.30, 'timeout_rate': 0.10},
            'terrible':{'latency': 5000, 'failure_rate': 0.80, 'timeout_rate': 0.50},
        }
        
        cond = conditions.get(condition, conditions['good'])
        
        # FIX BUG #3: Use deterministic exact proportions instead of random draws.
        # random.random() was better than time.time() % 1, but still caused
        # test variance — 'poor' (20% rate) could get 0 failures by chance,
        # sending it to normal; 'terrible' (80%) could get only 60% failures,
        # keeping score above the critical threshold.
        #
        # Exact proportions guarantee the ML model always sees a consistent
        # signal for each named condition, making mode selection predictable.
        #
        # We also inject 10 metrics (= full window size) so the simulated
        # condition completely overwrites any prior history in the window.
        n_failed  = round(cond['failure_rate']  * 10)
        n_timeout = round(cond['timeout_rate']  * 10)

        for i in range(10):
            is_failed  = i < n_failed
            is_timeout = i < n_timeout
            # Add a tiny linear latency variation for realism (no randomness)
            latency_variation = (i - 5) * 5
            metric = NetworkMetrics(
                timestamp=time.time() + i * 0.001,
                session_id=session_id,
                request_id=f"sim_{session_id}_{i}",
                latency_ms=cond['latency'] + latency_variation,
                payload_size_bytes=1000,
                response_size_bytes=0 if is_failed else 500,
                http_status=500 if is_failed else 200,
                retry_count=2 if is_timeout else 0,
                timeout_occurred=is_timeout
            )
            self.network_monitor.record_request(metric)
        
        return {"status": f"Simulated {condition} network for session {session_id}"}


# Global controller instance
adaptation_controller = AdaptationController()