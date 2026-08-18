import json
import os
import uuid
from typing import Optional
from ..models import StateSnapshot
from ..config import config


class ProjectService:
    def __init__(self, snapshot_dir: str = ""):
        self._snapshots: dict[str, StateSnapshot] = {}
        self._snapshot_dir = snapshot_dir or os.path.join(config.checkpoints_path, "snapshots")
        self._load_snapshots()

    def _snapshot_path(self, snapshot_id: str) -> str:
        safe = os.path.basename(snapshot_id.replace("..", ""))
        if not safe or safe.startswith("."):
            safe = f"snapshot_{abs(hash(snapshot_id)) % (10**16)}"
        return os.path.join(self._snapshot_dir, f"{safe}.json")

    def _load_snapshots(self):
        if not os.path.exists(self._snapshot_dir):
            return
        for fname in sorted(os.listdir(self._snapshot_dir)):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self._snapshot_dir, fname)) as f:
                        data = json.load(f)
                    snapshot = StateSnapshot(**data)
                    sid = data.get("_snapshot_id", os.path.splitext(fname)[0])
                    self._snapshots[sid] = snapshot
                except (json.JSONDecodeError, IOError, KeyError):
                    pass

    def save_snapshot(self, snapshot: StateSnapshot) -> str:
        sid = str(uuid.uuid4())
        os.makedirs(self._snapshot_dir, exist_ok=True)
        path = self._snapshot_path(sid)
        data = snapshot.model_dump(by_alias=True)
        data["_snapshot_id"] = sid
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._snapshots[sid] = snapshot
        return sid

    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        if not snapshot_id:
            return None
        if snapshot_id in self._snapshots:
            return self._snapshots[snapshot_id]
        for v in self._snapshots.values():
            if str(v.timestamp) == snapshot_id:
                return v
        return None

    def list_snapshots(self) -> list[StateSnapshot]:
        return sorted(self._snapshots.values(), key=lambda s: s.timestamp, reverse=True)



_service: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    global _service
    if _service is None:
        _service = ProjectService()
    return _service


def reset_project_service():
    global _service
    _service = None
