"""持久化的 ESP32 远程命令队列。"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from config import (
    COMMAND_CLAIM_TIMEOUT,
    COMMAND_STATE_FILE,
    DEFAULT_DEVICE_ID,
    DEVICE_ONLINE_TIMEOUT,
)


_state_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _empty_state() -> Dict:
    return {"commands": [], "devices": {}}


def _load_state() -> Dict:
    try:
        with open(COMMAND_STATE_FILE, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
            state.setdefault("commands", [])
            state.setdefault("devices", {})
            return state
    except (OSError, ValueError):
        return _empty_state()


def _save_state(state: Dict) -> None:
    os.makedirs(os.path.dirname(COMMAND_STATE_FILE), exist_ok=True)
    temp_path = COMMAND_STATE_FILE + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, ensure_ascii=False, indent=2)
    os.replace(temp_path, COMMAND_STATE_FILE)


def _touch_device(state: Dict, device_id: str, now: datetime) -> None:
    device = state["devices"].setdefault(device_id, {})
    device["last_seen"] = _iso(now)


def create_capture_command(device_id: str = DEFAULT_DEVICE_ID) -> Dict:
    """创建一条待设备领取的拍照命令。"""
    now = _now()
    command = {
        "id": uuid.uuid4().hex,
        "device_id": device_id,
        "type": "capture",
        "status": "pending",
        "created_at": _iso(now),
        "claimed_at": None,
        "completed_at": None,
        "attempts": 0,
        "message": "",
    }
    with _state_lock:
        state = _load_state()
        state["commands"].append(command)
        state["commands"] = state["commands"][-100:]
        _save_state(state)
    return command.copy()


def claim_next_command(device_id: str) -> Optional[Dict]:
    """领取下一条命令；处理超时的命令会重新投递。"""
    now = _now()
    with _state_lock:
        state = _load_state()
        _touch_device(state, device_id, now)

        selected = None
        for command in state["commands"]:
            if command.get("device_id") != device_id:
                continue
            if command.get("status") == "pending":
                selected = command
                break
            if command.get("status") == "processing":
                claimed_at = _parse(command.get("claimed_at"))
                if (
                    claimed_at is None
                    or (now - claimed_at).total_seconds()
                    >= COMMAND_CLAIM_TIMEOUT
                ):
                    selected = command
                    break

        if selected:
            selected["status"] = "processing"
            selected["claimed_at"] = _iso(now)
            selected["attempts"] = int(selected.get("attempts", 0)) + 1

        _save_state(state)
        return selected.copy() if selected else None


def complete_command(
    command_id: str,
    device_id: str,
    status: str,
    message: str = "",
) -> Optional[Dict]:
    """记录设备对命令的 completed/failed 执行结果。"""
    if status not in ("completed", "failed"):
        raise ValueError("status 必须为 completed 或 failed")

    now = _now()
    with _state_lock:
        state = _load_state()
        _touch_device(state, device_id, now)
        for command in state["commands"]:
            if (
                command.get("id") == command_id
                and command.get("device_id") == device_id
            ):
                command["status"] = status
                command["message"] = message[:200]
                command["completed_at"] = _iso(now)
                device = state["devices"].setdefault(device_id, {})
                device["last_result"] = status
                _save_state(state)
                return command.copy()
    return None


def get_command(command_id: str) -> Optional[Dict]:
    """按 ID 查询命令状态，供网页等待设备执行结果。"""
    with _state_lock:
        state = _load_state()
        for command in state["commands"]:
            if command.get("id") == command_id:
                return command.copy()
    return None


def get_device_status(device_id: str = DEFAULT_DEVICE_ID) -> Dict:
    """返回设备在线状态和该设备的待处理命令数。"""
    now = _now()
    with _state_lock:
        state = _load_state()
        device = state["devices"].get(device_id, {})
        last_seen = _parse(device.get("last_seen"))
        online = bool(
            last_seen
            and (now - last_seen).total_seconds() <= DEVICE_ONLINE_TIMEOUT
        )
        pending = sum(
            1
            for command in state["commands"]
            if command.get("device_id") == device_id
            and command.get("status") in ("pending", "processing")
        )
        return {
            "device_id": device_id,
            "device_online": online,
            "device_last_seen": device.get("last_seen"),
            "device_last_result": device.get("last_result"),
            "pending_commands": pending,
        }
