"""Optional fast-library detection for JSON and XML acceleration."""

__all__ = ["HAS_ORJSON", "HAS_LXML", "json_loads", "json_dumps"]

try:
    import orjson as _orjson

    HAS_ORJSON = True

    def json_loads(data):
        # orjson is strict about control characters; fall back to stdlib for those.
        try:
            return _orjson.loads(data)
        except _orjson.JSONDecodeError:
            import json as _json_fallback

            text = data.decode() if isinstance(data, bytes) else data
            return _json_fallback.loads(text, strict=False)

    def json_dumps(obj) -> str:
        return _orjson.dumps(obj).decode()

except ImportError:
    import json as _json

    HAS_ORJSON = False

    def json_loads(data):
        text = data.decode() if isinstance(data, bytes) else data
        return _json.loads(text, strict=False)

    def json_dumps(obj) -> str:
        return _json.dumps(obj, separators=(",", ":"))


try:
    import lxml.etree as _lxml_ET

    HAS_LXML = True
    lxml_ET = _lxml_ET
except ImportError:
    HAS_LXML = False
    lxml_ET = None
