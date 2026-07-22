"""A cooperative, single-threaded task scheduler.

The docstrings in this module are the complete specification. Trust them,
not the code.
"""

import heapq


class Scheduler:
    """A cooperative task scheduler with priorities, budgets, and callbacks.

    Tasks
    -----
    submit(fn, priority=0) registers a task and returns its id; ids are
    consecutive ints starting at 1. `fn` is called with no arguments when
    the task executes and is assumed never to raise (behavior on a raise is
    unspecified). `priority` is any int and never changes after submit.

    Ready order
    -----------
    The ready pool is ordered by (priority, ready-order): a lower priority
    number always runs first, and within one priority class tasks run in
    the order they most recently BECAME READY. Becoming ready happens at
    submit() and at requeue, and each such event takes the next slot at the
    back of its priority class. pending() returns the ids of all ready
    tasks, as a fresh list, in exactly the order run() would execute them.

    Execution
    ---------
    run(budget) executes ready tasks one at a time, always the current
    front of the pool, until the pool is empty or `budget` executions have
    happened. Every call of a task's fn counts as exactly one execution
    against the budget — including a call that ends in requeue. Skipping a
    cancelled task costs nothing. run() returns the number of executions it
    performed. run(0) is legal, executes nothing, and returns 0; a negative
    budget raises ValueError; run() on an empty pool returns 0.

    If fn returns exactly the string "again", the task is REQUEUED: it
    stays in state "ready", goes to the back of its priority class (a fresh
    ready-event), no result is recorded, no callbacks fire, and its
    registrations are kept. Any other return value COMPLETES the task:
    state becomes "done", the value becomes its result, and its
    done-callbacks fire immediately — before the next task is popped — in
    registration order, each called as cb(task_id, result). A completed
    task's registrations are discarded after firing. (Consequence: "again"
    can never be a real result.)

    Cancellation
    ------------
    cancel(task_id) cancels a ready task: its state becomes "cancelled", it
    will never execute, its callback registrations are discarded
    immediately, and its callbacks never fire — not at cancel time, not
    later.

    Reentrancy
    ----------
    submit, cancel, and add_done_callback may be called from inside a
    task's fn or from inside a done-callback. Their effects are immediate:
    a task submitted during a run joins the pool at once, is visible to
    pending() and state() right away, and executes in that same run if
    budget remains and it reaches the front.

    Errors
    ------
    Every method taking a task_id raises KeyError if the id is unknown.
    cancel and add_done_callback raise ValueError if the task is not in
    state "ready"; result raises ValueError if the task is not "done".
    """

    def __init__(self):
        self._next_id = 1
        self._seq = 0
        self._heap = []       # (priority, order, task_id)
        self._tasks = {}      # id -> {fn, priority, state, order, result}
        self._callbacks = {}  # id -> [cb, ...]

    def submit(self, fn, priority=0):
        """Register a task; return its id. See the class docstring."""
        tid = self._next_id
        self._next_id += 1
        self._seq += 1
        self._tasks[tid] = {"fn": fn, "priority": priority, "state": "ready",
                            "order": self._seq, "result": None}
        heapq.heappush(self._heap, (priority, self._seq, tid))
        return tid

    def run(self, budget):
        """Execute up to `budget` ready tasks; return how many ran."""
        if budget < 0:
            raise ValueError("budget must be >= 0")
        executed = 0
        while self._heap and executed < budget:
            priority, order, tid = heapq.heappop(self._heap)
            task = self._tasks[tid]
            if task["state"] == "cancelled":
                continue
            result = task["fn"]()
            executed += 1
            if result == "again":
                self._seq += 1
                task["order"] = self._seq
                heapq.heappush(self._heap, (priority, self._seq, tid))
                continue
            task["state"] = "done"
            task["result"] = result
            for cb in self._callbacks.pop(tid, []):
                cb(tid, result)
        return executed

    def cancel(self, task_id):
        """Cancel a ready task; discard its callback registrations."""
        task = self._tasks[task_id]
        if task["state"] != "ready":
            raise ValueError(f"task {task_id} is not ready")
        task["state"] = "cancelled"
        self._callbacks.pop(task_id, None)

    def add_done_callback(self, task_id, cb):
        """Register cb(task_id, result) to fire when the task completes."""
        task = self._tasks[task_id]
        if task["state"] != "ready":
            raise ValueError(f"task {task_id} is not ready")
        self._callbacks.setdefault(task_id, []).append(cb)

    def callback_count(self, task_id):
        """Registrations currently held; 0 for done or cancelled tasks."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return len(self._callbacks.get(task_id, []))

    def state(self, task_id):
        """'ready', 'done', or 'cancelled'."""
        return self._tasks[task_id]["state"]

    def result(self, task_id):
        """The result of a done task (ValueError otherwise)."""
        task = self._tasks[task_id]
        if task["state"] != "done":
            raise ValueError(f"task {task_id} is not done")
        return task["result"]

    def pending(self):
        """Ready ids in exact run order, as a fresh list."""
        return [tid for _, _, tid in sorted(self._heap)
                if self._tasks[tid]["state"] == "ready"]
