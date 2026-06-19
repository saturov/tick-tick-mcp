from __future__ import annotations

from typing import Any

from session import get_session


def handle_list_tags() -> dict[str, Any]:
    session = get_session()
    tags = session.list_tags()
    return {"tags": tags, "count": len(tags)}


def handle_create_tag(
    label: str,
    color: str = "",
    parent: str = "",
    sort_type: int = 0,
) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.create_tag(
        label=label, color=color, parent=parent, sort_type=sort_type
    )
    return {"tag": result}


def handle_update_tag(
    label: str,
    new_label: str = "",
    color: str = "",
    parent: str = "",
) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.update_tag(
        label=label, new_label=new_label, color=color, parent=parent
    )
    return {"tag": result}


def handle_delete_tag(label: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.delete_tag(tag_name=label)
    return {"tag": result}


def handle_merge_tags(source_label: str, target_label: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.merge_tags(source_label=source_label, target_label=target_label)
    return {"tag": result}


def handle_batch_create_tags(tags: list[dict[str, Any]]) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    results = []
    for tag in tags:
        result = client.create_tag(
            label=tag["label"],
            color=tag.get("color", ""),
            parent=tag.get("parent", ""),
            sort_type=tag.get("sort_type", 0),
        )
        results.append(result)
    return {"tags": results}