"""Start/stop GCE Ollama VM on demand to minimize idle LLM cost."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

_last_llm_activity: Optional[datetime] = None


def _enabled() -> bool:
    return os.getenv("GCE_LLM_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _instance_spec() -> tuple[str, str, str]:
    project = os.getenv("GCE_LLM_PROJECT", "").strip()
    zone = os.getenv("GCE_LLM_ZONE", "").strip()
    instance = os.getenv("GCE_LLM_INSTANCE", "").strip()
    if not (project and zone and instance):
        raise RuntimeError(
            "GCE_LLM_PROJECT, GCE_LLM_ZONE, and GCE_LLM_INSTANCE must be set when GCE_LLM_ENABLED=true."
        )
    return project, zone, instance


def _compute_client():
    from google.cloud import compute_v1

    return compute_v1.InstancesClient()


def get_instance_status() -> str:
    if not _enabled():
        return "disabled"
    project, zone, instance = _instance_spec()
    client = _compute_client()
    inst = client.get(project=project, zone=zone, instance=instance)
    return str(inst.status)


def start_llm_vm() -> None:
    if not _enabled():
        return
    project, zone, instance = _instance_spec()
    client = _compute_client()
    status = get_instance_status()
    if status == "RUNNING":
        return
    if status == "TERMINATED":
        client.start(project=project, zone=zone, instance=instance)
    elif status in {"STOPPING", "PROVISIONING", "STAGING"}:
        pass
    else:
        raise RuntimeError(f"Unexpected LLM VM status: {status}")


def stop_llm_vm() -> None:
    if not _enabled():
        return
    project, zone, instance = _instance_spec()
    client = _compute_client()
    status = get_instance_status()
    if status == "RUNNING":
        client.stop(project=project, zone=zone, instance=instance)


def touch_llm_activity() -> None:
    global _last_llm_activity
    _last_llm_activity = datetime.now(timezone.utc)


def idle_minutes() -> int:
    return max(1, int(os.getenv("GCE_LLM_IDLE_MINUTES", "15")))


def stop_if_idle() -> dict:
    if not _enabled():
        return {"action": "skipped", "reason": "GCE_LLM_ENABLED is false"}
    if _last_llm_activity is None:
        status = get_instance_status()
        if status == "RUNNING":
            stop_llm_vm()
            return {"action": "stopped", "reason": "no recorded LLM activity"}
        return {"action": "skipped", "reason": "vm not running"}

    elapsed = (datetime.now(timezone.utc) - _last_llm_activity).total_seconds() / 60
    if elapsed >= idle_minutes():
        stop_llm_vm()
        return {"action": "stopped", "idle_minutes": round(elapsed, 1)}
    return {"action": "skipped", "idle_minutes": round(elapsed, 1)}


def _ollama_base_url() -> str:
    host = os.getenv("OLLAMA_HOST", "").strip()
    if host:
        if host.startswith(("http://", "https://")):
            return host.rstrip("/")
        scheme = os.getenv("OLLAMA_SCHEME", "http").strip() or "http"
        port = os.getenv("OLLAMA_PORT", "11434").strip() or "11434"
        return f"{scheme}://{host}:{port}".rstrip("/")
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def wait_for_ollama(timeout_seconds: int = 300) -> None:
    base = _ollama_base_url()
    deadline = time.time() + timeout_seconds
    last_error = "Ollama did not become ready in time."
    with httpx.Client(timeout=5.0) as client:
        while time.time() < deadline:
            try:
                resp = client.get(f"{base}/api/tags")
                if resp.is_success:
                    return
                last_error = f"Ollama tags endpoint returned {resp.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(5)
    raise RuntimeError(last_error)


def ensure_llm_ready(timeout_seconds: Optional[int] = None) -> None:
    if not _enabled():
        return
    start_llm_vm()
    # Boot + model load on a cold CPU VM can take several minutes.
    ready_timeout = timeout_seconds
    if ready_timeout is None:
        ready_timeout = int(os.getenv("OLLAMA_READY_TIMEOUT", "360"))
    wait_for_ollama(timeout_seconds=ready_timeout)
