"""Observe actual AEA function entries/returns in both study conditions."""
from study_apptainer import ApptainerKernel
from brainbench.codeact.engine import SandboxSetupError

BOOTSTRAP = '''
import sys as _aea_sys, json as _aea_json
def _aea_observe(frame, event, argument):
    if event not in ("call", "return"):
        return
    source = frame.f_code.co_filename
    if not source.startswith("/workspace/aea/") or frame.f_code.co_name.startswith(("_", "<")):
        return
    record = {"source": source, "function": frame.f_code.co_name, "event": event}
    if event == "return" and frame.f_code.co_name == "check_outputs" and isinstance(argument, dict):
        record["self_check_passed"] = argument.get("passed")
    with open("/workspace/AEA_FUNCTION_TRACE.jsonl", "a") as stream:
        stream.write(_aea_json.dumps(record) + "\\n")
_aea_sys.setprofile(_aea_observe)
print("AEA_FUNCTION_OBSERVER_READY")
'''


class ObservedKernel(ApptainerKernel):
    def __enter__(self):
        super().__enter__()
        result = super().execute(BOOTSTRAP, timeout_sec=30)
        if "AEA_FUNCTION_OBSERVER_READY" not in result or "Traceback" in result:
            self._remove_container()
            raise SandboxSetupError("AEA function observation setup failed: " + result)
        self.context.audit['function_observer'] = {
            'conditions': 'same observer in both conditions',
            'scope': 'Actual Python AEA function entries/returns, not proof of scientific correctness.'}
        return self
