"""极简线程安全 TTL 缓存，避免重复请求外部数据源被限流。"""
import threading
import time
from functools import wraps


class TTLCache:
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            value, expires = item
            if time.time() > expires:
                del self._store[key]
                return None
            return value

    def set(self, key, value, ttl):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)


_cache = TTLCache()


def disk_cache_load(path, max_age_seconds: int):
    """读磁盘缓存（带时效）。重量级计算结果落盘，重启后端不再触发全量重算。"""
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if time.time() - data.get("_cached_ts", 0) <= max_age_seconds:
            return data
    except Exception:
        pass
    return None


def disk_cache_save(path, data: dict) -> dict:
    import json
    from pathlib import Path
    p = Path(path)
    data["_cached_ts"] = time.time()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False))
    return data


def cached(ttl):
    """按函数名+参数缓存结果。None 结果不缓存，便于失败重试。"""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__module__, fn.__name__, args, tuple(sorted(kwargs.items())))
            hit = _cache.get(key)
            if hit is not None:
                return hit
            value = fn(*args, **kwargs)
            if value is not None:
                _cache.set(key, value, ttl)
            return value
        return wrapper
    return deco
