import time
from dataclasses import dataclass

from base.tool_base import ToolBase, ToolResult


# role → tools it may call
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "CEO": {
        "read_emails", "send_email",
    },
    "COO": {
       ...,
    },
    "Board": {
     ...,
    },
    "Employee": {
     ...,
    },
    "Journalist": {
       ...,
    },
    "Regulator": {
        ...
    },
}


@dataclass
class StepTrace:
    step: int             # groups events by ReAct iteration
    phase: str            # PLAN | ACT | OBSERVE — where in the cycle the event happened
    tool_name: str | None
    details: str          # human-readable summary of what happened
    duration_ms: float = 0.0


class ToolExecutor:
    """The enforcement layer between the LLM's decisions and the tools.

    It asks: does this tool exist? is the caller authorised? are the arguments
    valid? should we retry on failure? Every event is logged for traceability
    so that after any query we can print exactly which tools ran, in which
    order, with what results.
    """

    def __init__(self, role: str, max_retries: int = 2, base_delay: float = 0.5) -> None:
        """
        role         - the agent role that owns this executor (e.g. "CEO", "COO")
        max_retries  - how many extra attempts after the first failure
        base_delay   - base wait in seconds; doubled on each retry attempt
        """
        if role not in _ROLE_PERMISSIONS:
            raise ValueError(
                f"Unknown role '{role}'. "
                f"Valid roles: {sorted(_ROLE_PERMISSIONS.keys())}"
            )
        self._role = role
        self._registry: dict[str, ToolBase] = {}
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._traces: list[StepTrace] = []

    def register(self, tool: ToolBase) -> None:
        """Maps tool schema names to tool instances.

        ToolAgent looks up tools by name from the LLM's JSON output — if the
        LLM invents a name that is not in the registry, execute() returns an
        error immediately instead of crashing.
        """
        self._registry[tool.schema.name] = tool

    def tool_schemas(self) -> list[dict]:
        """Returns only the schemas this role is allowed to call."""
        allowed = _ROLE_PERMISSIONS[self._role]
        return [
            {
                "name": t.schema.name,
                "description": t.schema.description,
                "parameters": t.schema.parameters,
            }
            for t in self._registry.values()
            if t.schema.name in allowed
        ]

    def execute(self, step: int, tool_name: str, args: dict) -> ToolResult:
        """Runs the named tool after three validation checks:

            1. Role permission  — rejects tools the role may not call
            2. Tool existence   — rejects invented tool names immediately
            3. Required args    — rejects calls missing mandatory parameters

        Then runs with exponential-backoff retry for idempotent tools.
        """
        # Failure matrix: role not permitted to call this tool
        if tool_name not in _ROLE_PERMISSIONS[self._role]:
            result = ToolResult(
                error=f"Role '{self._role}' is not authorised to use '{tool_name}'. "
                      f"Allowed tools: {sorted(_ROLE_PERMISSIONS[self._role])}"
            )
            self._traces.append(StepTrace(
                step, "ACT", tool_name,
                f"DENIED — role='{self._role}' not permitted  args={args}",
            ))
            return result

        # Failure matrix: invented tool name
        if tool_name not in self._registry:
            result = ToolResult(
                error=f"Unknown tool '{tool_name}'. "
                      f"Available tools: {list(self._registry.keys())}"
            )
            self._traces.append(StepTrace(
                step, "ACT", tool_name,
                f"FAIL — unknown tool  args={args}",
            ))
            return result

        tool = self._registry[tool_name]

        # Failure matrix: missing required arguments (schema enforcement)
        required = tool.schema.parameters.get("required", [])
        missing = [p for p in required if p not in args]
        if missing:
            result = ToolResult(error=f"Missing required arguments: {missing}")
            self._traces.append(StepTrace(
                step, "ACT", tool_name,
                f"FAIL — missing args {missing}  provided={list(args.keys())}",
            ))
            return result

        # Run with retry + exponential backoff
        max_attempts = self._max_retries + 1
        last_result: ToolResult | None = None

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                delay = self._base_delay * (2 ** (attempt - 2))
                time.sleep(delay)

            t0 = time.monotonic()
            try:
                last_result = tool.run(**args)
            except Exception as exc:
                last_result = ToolResult(error=f"Unexpected exception: {exc}")
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

            attempt_label = f"attempt {attempt}/{max_attempts}"

            if last_result.ok:
                self._traces.append(StepTrace(
                    step, "ACT", tool_name,
                    f"OK {attempt_label}  args={args}  -> {str(last_result.value)[:80]}",
                    elapsed_ms,
                ))
                return last_result

            # Log the failed attempt
            self._traces.append(StepTrace(
                step, "ACT", tool_name,
                f"FAIL {attempt_label}  error: {last_result.error}",
                elapsed_ms,
            ))

            # Non-idempotent: do NOT retry (side effects already happened)
            if not last_result.is_idempotent:
                break

        return last_result

    def log_trace(self, step: int, phase: str, tool_name: str | None, details: str) -> None:
        """Records a PLAN or OBSERVE trace entry (no tool execution time)."""
        self._traces.append(StepTrace(step, phase, tool_name, details))

    def get_traces(self) -> list[StepTrace]:
        return list(self._traces)

    def clear_traces(self) -> None:
        self._traces.clear()