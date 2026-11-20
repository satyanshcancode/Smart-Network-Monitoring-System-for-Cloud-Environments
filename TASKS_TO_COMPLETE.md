# Tasks Needed to Complete & Audit Status

This document tracks the status of all identified bugs and inconsistencies across the project, based on the codebase audit.

---

## Audit Summary Table

| Category | Issue | Status | Details / Location |
| :--- | :--- | :---: | :--- |
| **2.A Frontend** | TypeScript Compilation Errors (`useCallback`, optional chaining) | **COMPLETED** | Fixed in `src/App.tsx`; `npm run build` passes with 0 errors. |
| **2.B Frontend** | Temporal Dead Zone (`fetchSessionStatus` before declaration) | **COMPLETED** | Fixed in `src/App.tsx` by wrapping in `useCallback` before `useEffect`. |
| **2.B Frontend** | Impure Hook (`Math.random()` in `sidebar.tsx`) | **COMPLETED** | Fixed in `src/components/ui/sidebar.tsx` with deterministic value. |
| **2.B Frontend** | Unused UI Boilerplate (40+ unused shadcn components) | **REMAINING** | 40+ unused files in `src/components/ui/` (e.g., `calendar.tsx`, `accordion.tsx`). |
| **3.A Backend** | Critical Mode Status 404 (`/status/{ack_id}`) | **COMPLETED** | Fixed in `adaptation_controller.py` & `main.py` using `queued_tasks_store`. |
| **3.B Backend** | Queue-Drain Anti-Pattern & Race Condition | **COMPLETED** | Replaced queue-drain loop with direct dict index lookup. |
| **3.B Backend** | Background Consumer Worker for `async_processing_queue` | **REMAINING** | Asynchronous jobs are enqueued but lack an active consumer thread. |
| **3.C Backend** | HTTP Status Code Masking | **COMPLETED** | Fixed in `main.py` using `JSONResponse(status_code=..., content=...)`. |
| **3.D Backend** | CORS Specification Violation | **COMPLETED** | Fixed in `main.py` with compliant `allow_credentials=False` + `allow_origins=["*"]`. |
| **4.A ML / Data** | Model Deserialization Warning (`InconsistentVersionWarning`) | **COMPLETED** | Model retrained and resaved with scikit-learn 1.6.1. |
| **4.B ML / Data** | `train_network_model.py` Output Path Bug | **COMPLETED** | Fixed with `os.path.join(script_dir, ...)` in `train_network_model.py`. |
| **4.C ML / Data** | Latency Metric Clipping at 2000ms | **COMPLETED** | Increased ceiling from 2,000ms to 10,000ms in `network_monitoring.py`. |
| **4.D ML / Data** | Mode Testing vs. Prediction Score Dynamics | **REMAINING** | Clicking "Test Critical Mode" on a clean session yields ~0.615 score (Normal mode) because 1 slow request cannot overcome 9 clean window samples. |

---

## Remaining Tasks (3 Remaining)

### Task 1: Mode Testing vs. Prediction Score Dynamics (Issue 4.D)
- **Problem**: When a user clicks **Test Degraded Mode** or **Test Critical Mode** in `src/App.tsx`, it sends a single request with `simulated_latency: 500` or `2000`. In a 10-request sliding window without prior failure history, a single request produces a stability score $> 0.60$, causing the backend to continue executing in Normal Mode.
- **Solution Options**:
  1. Have the UI simulate the matching condition (`simulateNetwork('poor')` or `simulateNetwork('terrible')`) before submitting the test request, OR
  2. Use the `/session/{id}/force-mode` endpoint to set the session state directly when testing modes.

### Task 2: Background Async Queue Consumer (Issue 3.B)
- **Problem**: When Critical Mode enqueues requests or async failures into `async_processing_queue`, there is no active worker background thread consuming from the queue and transitioning tasks from `queued` to `completed`.
- **Solution**:
  - Add a daemon background consumer thread or FastAPI `asyncio` background task that picks up queued items, processes them (e.g. simulating database storage / evaluation), and updates their status in `queued_tasks_store`.

### Task 3: Unused UI Component Pruning (Issue 2.B)
- **Problem**: 40+ shadcn UI components exist in `src/components/ui/` (e.g. `calendar.tsx`, `accordion.tsx`, `menubar.tsx`, `drawer.tsx`, etc.) that are never imported by the dashboard.
- **Solution**:
  - Prune unused UI component files, keeping only the ones actively used by `App.tsx` (`button.tsx`, `card.tsx`, `badge.tsx`, `progress.tsx`, `alert.tsx`, `tabs.tsx`, `separator.tsx`).
