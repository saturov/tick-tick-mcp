"""TickTick HTTP client and authentication utilities."""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from getpass import getpass
from typing import Any


def _detect_venv() -> bool:
    return (
        hasattr(sys, "real_prefix")
        or sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        or bool(os.environ.get("VIRTUAL_ENV"))
    )


def ensure_venv_active() -> None:
    """Ensure a virtual environment is active."""
    if not _detect_venv():
        raise RuntimeError(
            "ERROR: venv is not activated. Create and activate it: "
            "python3 -m venv .venv && source .venv/bin/activate"
        )


def _prompt_credential(env_key: str, prompt_text: str, secret: bool = False) -> str:
    value = os.environ.get(env_key)
    if value:
        return value
    if secret:
        return getpass(prompt_text)
    return input(prompt_text)


def _session_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "x-device": json.dumps(
            {
                "platform": "web",
                "os": "OS X",
                "device": "Chrome 124.0.0.0",
                "name": "",
                "version": 5070,
                "id": "6490" + secrets.token_hex(10),
                "channel": "website",
                "campaign": "",
                "websocket": "",
            },
            separators=(",", ":"),
        ),
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": "https://ticktick.com/webapp/",
        "Origin": "https://ticktick.com",
    }


def _make_retry_session() -> Any:
    """Create a requests.Session with retry logic (replaces ticktick-py's requests_retry_session)."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class TickTickClient:
    BASE_URL = "https://api.ticktick.com/api/v2/"

    def __init__(
        self,
        username: str,
        password: str,
        session: Any,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._headers = dict(headers or {})
        self.access_token: str | None = None
        self.cookies: dict[str, str] = {}
        self.time_zone = ""
        self.profile_id = ""
        self.inbox_id = ""
        self.state: dict[str, Any] = {}
        self.reset_local_state()
        self.login()
        self._settings()
        self.sync()

    def reset_local_state(self) -> None:
        self.state = {
            "projects": [],
            "project_folders": [],
            "tags": [],
            "tasks": [],
            "user_settings": {},
            "profile": {},
        }

    def login(self) -> bool:
        if self.access_token:
            return True

        response = None
        max_attempts = 4
        for attempt in range(1, max_attempts + 1):
            for path in ("user/signon", "user/signin"):
                response = self._session.post(
                    self.BASE_URL + path,
                    json={"username": self._username, "password": self._password},
                    params={"wc": True, "remember": True},
                    headers=self._headers,
                    timeout=20,
                )
                if response.status_code != 404:
                    break
            if response is not None and response.status_code != 429:
                break
            if attempt < max_attempts:
                time.sleep(16)

        if response is None or response.status_code != 200:
            raise RuntimeError("auth failed")

        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("unexpected response")

        self.access_token = token
        self.cookies["t"] = token
        return True

    def _settings(self) -> None:
        response = self._session.get(
            self.BASE_URL + "user/preferences/settings",
            params={"includeWeb": True},
            cookies=self.cookies,
            headers=self._headers,
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError("sync failed")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

        time_zone = payload.get("timeZone")
        profile_id = payload.get("id")
        if not isinstance(time_zone, str) or not time_zone or not profile_id:
            raise RuntimeError("unexpected response")

        self.time_zone = time_zone
        self.profile_id = str(profile_id)

    def sync(self) -> dict[str, Any]:
        response = self._session.get(
            self.BASE_URL + "batch/check/0",
            cookies=self.cookies,
            headers=self._headers,
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError("sync failed")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

        self.inbox_id = payload.get("inboxId", "")
        self.state["project_folders"] = payload.get("projectGroups", [])
        self.state["projects"] = payload.get("projectProfiles", [])
        self.state["tasks"] = payload.get("syncTaskBean", {}).get("update", [])
        self.state["tags"] = payload.get("tags", [])
        return payload

    def http_get(self, url: str, **kwargs: Any) -> Any:
        response = self._session.get(url, cookies=self.cookies, headers=self._headers,
                                     timeout=20, **kwargs)
        if response.status_code != 200:
            raise RuntimeError("sync failed")
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

    def http_post(self, url: str, json_data: Any = None, **kwargs: Any) -> Any:
        kwargs.setdefault("cookies", self.cookies)
        kwargs.setdefault("headers", self._headers)
        kwargs.setdefault("timeout", 20)
        response = self._session.post(url, json=json_data, **kwargs)
        if response.status_code != 200:
            raise RuntimeError("sync failed")
        try:
            return response.json() if response.text else ""
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

    def http_put(self, url: str, json_data: Any = None, **kwargs: Any) -> Any:
        kwargs.setdefault("cookies", self.cookies)
        kwargs.setdefault("headers", self._headers)
        kwargs.setdefault("timeout", 20)
        response = self._session.put(url, json=json_data, **kwargs)
        if response.status_code != 200:
            raise RuntimeError("sync failed")
        try:
            return response.json() if response.text else ""
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

    def http_delete(self, url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("cookies", self.cookies)
        kwargs.setdefault("headers", self._headers)
        kwargs.setdefault("timeout", 20)
        response = self._session.delete(url, **kwargs)
        if response.status_code != 200:
            raise RuntimeError("sync failed")
        try:
            return response.json() if response.text else ""
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc

    def delete_task(self, task_id: str, project_id: str) -> dict[str, Any]:
        delete_payload = [{"projectId": project_id, "taskId": task_id}]
        self.http_post(self.BASE_URL + "batch/task",
                       json_data={"delete": delete_payload})
        self.sync()
        return {"id": task_id, "deleted": True}

    def delete_tasks_batch(self, items: list[dict[str, str]]) -> list[dict[str, Any]]:
        delete_payload = [{"projectId": i["projectId"], "taskId": i["taskId"]} for i in items]
        self.http_post(self.BASE_URL + "batch/task",
                       json_data={"delete": delete_payload})
        self.sync()
        return [{"id": i["taskId"], "deleted": True} for i in items]

    def move_task(self, task_id: str, from_project_id: str, to_project_id: str) -> dict[str, Any]:
        update_payload = [{"projectId": from_project_id, "taskId": task_id,
                           "projectIdNew": to_project_id}]
        self.http_post(self.BASE_URL + "batch/task",
                       json_data={"update": update_payload})
        self.sync()
        return {"id": task_id, "projectId": to_project_id}

    def make_subtask(self, task_id: str, parent_id: str, project_id: str) -> dict[str, Any]:
        update_payload = [{"projectId": project_id, "taskId": task_id,
                           "parentId": parent_id}]
        self.http_post(self.BASE_URL + "batch/task",
                       json_data={"update": update_payload})
        self.sync()
        return {"id": task_id, "parentId": parent_id}

    def remove_subtask(self, task_id: str, project_id: str) -> dict[str, Any]:
        update_payload = [{"projectId": project_id, "taskId": task_id,
                           "parentId": ""}]
        self.http_post(self.BASE_URL + "batch/task",
                       json_data={"update": update_payload})
        self.sync()
        return {"id": task_id, "parentId": None}

    def create_project(self, name: str, color: str = "#51b9e3",
                       project_type: str = "TASK",
                       folder_id: str = "") -> dict[str, Any]:
        project = {"name": name, "color": color, "kind": project_type}
        if folder_id:
            project["groupId"] = folder_id
        response = self.http_post(self.BASE_URL + "batch/project",
                                  json_data={"add": [project]})
        self.sync()
        proj_id = list(response.get("id2etag", {}).keys())[0]
        return self.get_by_id(proj_id, search="projects")

    def update_project(self, project_id: str, name: str = "",
                       color: str = "", view_mode: str = "",
                       closed: bool | None = None) -> dict[str, Any]:
        project = {"id": project_id}
        if name:
            project["name"] = name
        if color:
            project["color"] = color
        if view_mode:
            project["viewMode"] = view_mode
        if closed is not None:
            project["closed"] = closed
        self.http_post(self.BASE_URL + "batch/project",
                       json_data={"update": [project]})
        self.sync()
        return self.get_by_id(project_id, search="projects")

    def delete_project(self, project_ids: list[str]) -> list[dict[str, Any]]:
        self.http_post(self.BASE_URL + "batch/project",
                       json_data={"delete": project_ids})
        self.sync()
        return [{"id": pid, "deleted": True} for pid in project_ids]

    def create_folder(self, name: str) -> dict[str, Any]:
        response = self.http_post(self.BASE_URL + "batch/projectGroup",
                                  json_data={"add": [{"name": name, "listType": "group"}]})
        self.sync()
        folder_id = list(response.get("id2etag", {}).keys())[0]
        return self.get_by_id(folder_id, search="project_folders")

    def delete_folder(self, folder_ids: list[str]) -> list[dict[str, Any]]:
        self.http_post(self.BASE_URL + "batch/projectGroup",
                       json_data={"delete": folder_ids})
        self.sync()
        return [{"id": fid, "deleted": True} for fid in folder_ids]

    def create_tag(self, label: str, color: str = "", parent: str = "",
                   sort_type: int = 0) -> dict[str, Any]:
        SORT_MAP = {0: "project", 1: "dueDate", 2: "title", 3: "priority"}
        tag = {"name": label.lower(), "label": label}
        if color:
            tag["color"] = color
        if parent:
            tag["parent"] = parent.lower()
        if sort_type in SORT_MAP:
            tag["sortType"] = SORT_MAP[sort_type]
        response = self.http_post(self.BASE_URL + "batch/tag",
                                  json_data={"add": [tag]})
        self.sync()
        etag = response.get("id2etag", {}).get(label.lower(), "")
        return self.get_by_etag(etag, search="tags")

    def delete_tag(self, tag_name: str) -> dict[str, Any]:
        tag_obj = self.get_by_fields(name=tag_name.lower(), search="tags")
        if not tag_obj:
            raise RuntimeError(f"tag not found: {tag_name}")
        self.http_delete(self.BASE_URL + "tag",
                         params={"name": tag_obj["name"]})
        self.sync()
        return {"name": tag_name, "deleted": True}

    def update_tag(self, label: str, new_label: str = "", color: str = "",
                   parent: str = "") -> dict[str, Any]:
        tag_obj = self.get_by_fields(name=label.lower(), search="tags")
        if not tag_obj:
            raise RuntimeError(f"tag not found: {label}")
        if new_label:
            tag_obj["name"] = new_label.lower()
            tag_obj["label"] = new_label
        if color:
            tag_obj["color"] = color
        if parent is not None:
            tag_obj["parent"] = parent.lower() if parent else ""
        response = self.http_post(self.BASE_URL + "batch/tag",
                                  json_data={"update": [tag_obj]})
        self.sync()
        return self.get_by_etag(response.get("id2etag", {}).get(tag_obj["name"], ""),
                                search="tags")

    def merge_tags(self, source_label: str, target_label: str) -> dict[str, Any]:
        source = self.get_by_fields(name=source_label.lower(), search="tags")
        target = self.get_by_fields(name=target_label.lower(), search="tags")
        if not source or not target:
            raise RuntimeError("tag not found")
        self.http_put(self.BASE_URL + "tag/merge",
                       json_data={"name": source["name"], "newName": target["name"]})
        self.sync()
        return self.get_by_etag(target["etag"], search="tags")

    def get_by_id(self, obj_id: str, search: str = "") -> dict[str, Any]:
        if search and search in self.state:
            for item in self.state[search]:
                if item.get("id") == obj_id:
                    return item
        else:
            for key in self.state:
                if isinstance(self.state[key], list):
                    for item in self.state[key]:
                        if isinstance(item, dict) and item.get("id") == obj_id:
                            return item
        return {}

    def get_by_fields(self, search: str = "", **kwargs: Any) -> Any:
        collection = self.state[search] if search else [
            i for v in self.state.values() if isinstance(v, list) for i in v]
        results = []
        for item in collection:
            if isinstance(item, dict) and all(item.get(k) == v for k, v in kwargs.items()):
                results.append(item)
        return results[0] if len(results) == 1 else results

    def get_by_etag(self, etag: str, search: str = "") -> dict[str, Any]:
        if search and search in self.state:
            for item in self.state[search]:
                if item.get("etag") == etag:
                    return item
        else:
            for key in self.state:
                if isinstance(self.state[key], list):
                    for item in self.state[key]:
                        if isinstance(item, dict) and item.get("etag") == etag:
                            return item
        return {}

    def complete_task(self, task_id: str, project_id: str) -> dict[str, Any]:
        task = self.get_by_fields(id=task_id, search="tasks")
        if not task:
            raise RuntimeError(f"task not found: {task_id}")
        self.http_post(self.BASE_URL + "project/" + project_id + "/task/" + task_id +
                       "/complete", json_data={})
        self.sync()
        return {"id": task_id, "completed": True}


def build_client() -> TickTickClient:
    """Build and authenticate a TickTickClient using env vars or interactive prompt."""
    username = _prompt_credential("TICKTICK_USERNAME", "TickTick username: ")
    password = _prompt_credential("TICKTICK_PASSWORD", "TickTick password: ", secret=True)
    return TickTickClient(
        username=username,
        password=password,
        session=_make_retry_session(),
        headers=_session_headers(),
    )


def open_api_get_json(session: Any, url: str, api_key: str) -> Any:
    """GET request with rate-limit retry, returns parsed JSON."""
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        response = session.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        if response.status_code in (401, 403):
            raise RuntimeError("auth failed")
        if response.status_code == 200:
            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError("unexpected response") from exc

        is_rate_limited = False
        try:
            error_payload = response.json()
            is_rate_limited = error_payload.get("errorCode") == "exceed_query_limit"
        except Exception:
            is_rate_limited = response.status_code == 429

        if is_rate_limited and attempt < max_attempts:
            time.sleep(16)
            continue

        raise RuntimeError("sync failed")

    raise RuntimeError("sync failed")
