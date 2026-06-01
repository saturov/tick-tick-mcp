import os


def get_api_key() -> str:
    key = os.environ.get("TICKTICK_API_KEY", "")
    if not key:
        raise RuntimeError(
            "TICKTICK_API_KEY is not set. Export it as a Bearer token "
            "for TickTick Open API."
        )
    return key


def get_web_credentials() -> tuple[str, str]:
    username = os.environ.get("TICKTICK_USERNAME")
    password = os.environ.get("TICKTICK_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "TICKTICK_USERNAME and TICKTICK_PASSWORD must be set "
            "for Web v2 API operations."
        )
    return username, password