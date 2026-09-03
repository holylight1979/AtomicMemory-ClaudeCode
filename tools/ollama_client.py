"""
ollama_client.py — Multi-Backend Ollama Client

統一所有 Ollama 呼叫，支援多 backend 優先順序 + 自動切換。
三階段退避：正常 → 短DIE (60s) → 長DIE (等到下一個 6h 時間段)。

純 stdlib，不引入新依賴。
"""

import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ollama_client")

CLAUDE_DIR = Path.home() / ".claude"
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"
TOKEN_PATH = CLAUDE_DIR / "workflow" / ".rdchat_token.json"

# Health check cache TTL
HEALTH_TTL = 60  # seconds

# Short DIE: fallback 後 60s 重試
SHORT_DIE_COOLDOWN = 60  # seconds

# Long DIE: 10 分鐘內 2 次短DIE → 等到下一個時間段
LONG_DIE_WINDOW = 600  # 10 minutes

# 時間段邊界（每天 4 個）
TIME_BOUNDARIES = [0, 6, 12, 18]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OllamaBackend:
    name: str
    base_url: str  # e.g. "https://rdchat.uj.com.tw/ollama" or "http://127.0.0.1:11434"
    auth: Optional[Dict[str, str]] = None  # {"type", "login_url", "user", ...}
    llm_model: Optional[str] = None
    embedding_model: Optional[str] = None
    priority: int = 99
    enabled: bool = True  # 靜態旗標：false 時完全跳過此 backend
    think: bool = False  # 此 backend 的 LLM 是否支援/啟用 thinking mode
    llm_num_predict: int = 2048  # 此 backend 的 LLM num_predict 預設值


@dataclass
class BackendState:
    status: str = "normal"  # "normal" | "short_die" | "long_die"
    consecutive_failures: int = 0
    last_failure_at: float = 0.0
    short_die_count: int = 0
    first_short_die_at: float = 0.0
    long_die_until: Optional[float] = None


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------

class OllamaClient:

    def __init__(self, backends: List[OllamaBackend]):
        self._backends = sorted(backends, key=lambda b: b.priority)
        self._health_cache: Dict[str, Tuple[bool, float]] = {}
        self._token_cache: Dict[str, str] = {}
        self._state: Dict[str, BackendState] = {}
        # 載入已快取的 token
        self._load_cached_tokens()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def generate(self, prompt: str, model: str = None,
                 timeout: int = 120, format: str = None,
                 think=False, **options) -> str:
        """LLM text generation. Internally uses /api/chat.

        think=False: no reasoning tokens.
        think=True: 啟用 reasoning.
        think="auto": 依 backend config 自動決定（rdchat=True, local=False）.
        """
        backend = self._pick_backend("llm")
        if not backend:
            return ""
        # think="auto" → 依 backend 設定決定
        effective_think = backend.think if think == "auto" else think
        payload: Dict[str, Any] = {
            "model": model or backend.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": effective_think,
        }
        if format:
            payload["format"] = format
        # think="auto" 時，也套用 backend 的 num_predict（除非呼叫端已指定）
        if think == "auto" and "num_predict" not in options:
            options["num_predict"] = backend.llm_num_predict
        if options:
            payload["options"] = options
        result = self._request_with_failover(
            "llm", "/api/chat", payload, timeout,
            explicit_model=model,
            auto_think=think == "auto",
        )
        if result is None:
            return ""
        if not isinstance(result, dict):
            return str(result) if result else ""
        msg = result.get("message", {})
        if isinstance(msg, str):
            return msg
        if isinstance(msg, dict):
            return msg.get("content", "")
        return ""

    def chat(self, messages: List[Dict[str, str]], system: str = "",
             model: str = None, timeout: int = 30) -> str:
        """POST /api/chat — 替換 reranker + conflict-detector"""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        backend = self._pick_backend("llm")
        if not backend:
            return ""
        payload = {
            "model": model or backend.llm_model,
            "messages": msgs,
            "stream": False,
            "think": False,
        }
        result = self._request_with_failover(
            "llm", "/api/chat", payload, timeout,
            explicit_model=model,
        )
        if result is None:
            return ""
        if not isinstance(result, dict):
            return str(result) if result else ""
        msg = result.get("message", {})
        if isinstance(msg, str):
            return msg
        if isinstance(msg, dict):
            return msg.get("content", "")
        return ""

    def embed(self, texts: List[str], model: str = None,
              timeout: int = 120) -> List[List[float]]:
        """POST embedding request.

        Uses /api/embed (Ollama native) for direct backends,
        /api/v1/embeddings (OpenAI-compatible) for Open WebUI proxied backends.
        Open WebUI's OpenAI endpoint is at root (not under /ollama/ proxy path).
        """
        backend = self._pick_backend("embedding")
        if not backend:
            return []
        emb_model = model or backend.embedding_model
        if backend.auth:
            # Open WebUI: try OpenAI-compatible endpoint first
            # Strip /ollama proxy prefix to get OWU root URL
            result = self._owu_embed(backend, emb_model, texts, timeout)
            if result is not None:
                return result
            # Fallback: try Ollama native through proxy
        payload = {"model": emb_model, "input": texts}
        result = self._request_with_failover(
            "embedding", "/api/embed", payload, timeout,
            explicit_model=model,
        )
        if result is None:
            return []
        return result.get("embeddings", [])

    def _owu_embed(self, backend: OllamaBackend, model: str,
                   texts: List[str], timeout: int) -> Optional[List[List[float]]]:
        """Embed via Open WebUI's OpenAI-compatible /api/v1/embeddings."""
        base = backend.base_url.rstrip("/")
        # Strip Ollama proxy path to get OWU root
        for suffix in ("/ollama", "/ollama/"):
            if base.endswith(suffix.rstrip("/")):
                base = base[:-len(suffix.rstrip("/"))]
                break
        url = base + "/api/v1/embeddings"
        payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        token = self._ensure_auth(backend)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            ctx = None
            if url.startswith("https"):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read())
                return [item["embedding"] for item in data.get("data", [])
                        if "embedding" in item]
        except Exception as e:
            logger.warning("[%s] OWU embed failed: %s", backend.name, e)
            return None

    def is_available(self, need: str = "llm") -> bool:
        """Check if any backend with the needed capability is reachable."""
        return self._pick_backend(need) is not None

    # -----------------------------------------------------------------------
    # Request with failover
    # -----------------------------------------------------------------------

    def _request_with_failover(self, need: str, endpoint: str,
                               payload: dict, timeout: int,
                               explicit_model: str = None,
                               auto_think: bool = False) -> Optional[dict]:
        """Try backends in priority order, with failover on failure.

        When explicit_model is None, model field is updated per-backend
        to match each backend's configured model (fixes failover using
        wrong model name on fallback backend).

        auto_think=True: failover 時也依 backend config 調整 think + num_predict.
        """
        tried = set()
        while True:
            backend = self._pick_backend(need, exclude=tried)
            if not backend:
                return None
            tried.add(backend.name)
            # Skip backend when explicit_model doesn't match its configured model
            # (don't count as failure — avoids poisoning health_cache for subsequent calls).
            model_attr = "embedding_model" if need == "embedding" else "llm_model"
            if explicit_model:
                backend_model = getattr(backend, model_attr, None)
                if backend_model and backend_model != explicit_model:
                    continue
            actual_payload = payload
            needs_copy = False
            # Adjust model for this backend (unless caller specified explicit model)
            if not explicit_model and "model" in payload:
                backend_model = getattr(backend, model_attr, None)
                if backend_model and payload["model"] != backend_model:
                    if not needs_copy:
                        actual_payload = dict(payload)
                        needs_copy = True
                    actual_payload["model"] = backend_model
            # auto_think: adjust think + num_predict per backend
            if auto_think:
                if not needs_copy:
                    actual_payload = dict(payload)
                    needs_copy = True
                actual_payload["think"] = backend.think
                opts = dict(actual_payload.get("options", {}))
                opts["num_predict"] = backend.llm_num_predict
                actual_payload["options"] = opts
            result = self._do_request(backend, endpoint, actual_payload, timeout)
            if result is not None:
                self._record_success(backend)
                return result
            self._record_failure(backend)

    def _do_request(self, backend: OllamaBackend, endpoint: str,
                    payload: dict, timeout: int) -> Optional[dict]:
        """Single request attempt to one backend."""
        url = backend.base_url.rstrip("/") + endpoint
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        # Auth
        if backend.auth:
            token = self._ensure_auth(backend)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        try:
            ctx = None
            if url.startswith("https"):
                ctx = ssl.create_default_context()
                # 公司內網可能自簽憑證
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read())

        except urllib.error.HTTPError as e:
            if e.code == 401 and backend.auth:
                # Token 過期，重新登入一次
                logger.info("[%s] 401, re-authenticating...", backend.name)
                self._token_cache.pop(backend.name, None)
                token = self._ensure_auth(backend, force=True)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        req2 = urllib.request.Request(url, data=data, headers=headers, method="POST")
                        with urllib.request.urlopen(req2, timeout=timeout, context=ctx) as resp2:
                            return json.loads(resp2.read())
                    except Exception:
                        pass
            logger.warning("[%s] HTTP %s: %s", backend.name, e.code, endpoint)
            return None
        except Exception as e:
            logger.warning("[%s] %s: %s", backend.name, type(e).__name__, e)
            return None

    # -----------------------------------------------------------------------
    # Backend selection with 3-stage backoff
    # -----------------------------------------------------------------------

    def _pick_backend(self, need: str, exclude: set = None) -> Optional[OllamaBackend]:
        """Pick the best available backend for the given need."""
        now = time.time()
        exclude = exclude or set()

        for backend in self._backends:
            if backend.name in exclude:
                continue
            if not backend.enabled:
                continue

            # Check capability
            if need == "embedding" and not backend.embedding_model:
                continue
            if need == "llm" and not backend.llm_model:
                continue

            state = self._get_state(backend)

            # Long DIE: skip until time boundary
            if state.status == "long_die":
                if state.long_die_until and now < state.long_die_until:
                    continue
                # Time boundary reached — reset to normal
                logger.info("[%s] long_die expired, resetting to normal", backend.name)
                self._reset_state(backend)

            # Short DIE: skip if within cooldown
            if state.status == "short_die":
                if (now - state.last_failure_at) < SHORT_DIE_COOLDOWN:
                    continue
                # Cooldown passed — try again

            # Health check (cached)
            cached = self._health_cache.get(backend.name)
            if cached:
                healthy, ts = cached
                if (now - ts) < HEALTH_TTL:
                    if healthy:
                        return backend
                    continue  # known unhealthy within TTL

            # Actual health check
            healthy = self._check_health(backend)
            self._health_cache[backend.name] = (healthy, now)
            if healthy:
                return backend

        return None

    def _record_success(self, backend: OllamaBackend):
        """Any success resets state to normal."""
        state = self._get_state(backend)
        if state.status != "normal":
            logger.info("[%s] recovered → normal", backend.name)
            self._clear_long_die_marker()
        self._reset_state(backend)
        # Also refresh health cache
        self._health_cache[backend.name] = (True, time.time())

    def _record_failure(self, backend: OllamaBackend):
        """Record a failure and possibly escalate state."""
        now = time.time()
        state = self._get_state(backend)
        state.consecutive_failures += 1
        state.last_failure_at = now

        # Invalidate health cache
        self._health_cache[backend.name] = (False, now)

        if state.consecutive_failures >= 2 and state.status == "normal":
            # → short_die
            state.status = "short_die"
            state.short_die_count += 1
            if state.first_short_die_at == 0:
                state.first_short_die_at = now
            logger.info("[%s] → short_die (#%d)", backend.name, state.short_die_count)

            # Check long_die escalation
            if state.short_die_count >= 2:
                if (now - state.first_short_die_at) <= LONG_DIE_WINDOW:
                    state.status = "long_die"
                    state.long_die_until = _next_time_boundary()
                    until_str = datetime.fromtimestamp(state.long_die_until).strftime("%H:%M")
                    logger.warning("[%s] → long_die until %s", backend.name, until_str)
                    self._write_long_die_marker(backend, until_str)
                else:
                    # 10-minute window expired, reset short_die counters
                    state.short_die_count = 1
                    state.first_short_die_at = now

        elif state.consecutive_failures >= 2 and state.status == "short_die":
            # Already in short_die, check if should escalate
            state.short_die_count += 1
            if state.short_die_count >= 2:
                if (now - state.first_short_die_at) <= LONG_DIE_WINDOW:
                    state.status = "long_die"
                    state.long_die_until = _next_time_boundary()
                    until_str = datetime.fromtimestamp(state.long_die_until).strftime("%H:%M")
                    logger.warning("[%s] → long_die until %s", backend.name, until_str)
                    self._write_long_die_marker(backend, until_str)

    def _get_state(self, backend: OllamaBackend) -> BackendState:
        if backend.name not in self._state:
            self._state[backend.name] = BackendState()
        return self._state[backend.name]

    def _reset_state(self, backend: OllamaBackend):
        self._state[backend.name] = BackendState()

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------

    def _check_health(self, backend: OllamaBackend) -> bool:
        """GET /api/tags — lightweight health check."""
        url = backend.base_url.rstrip("/") + "/api/tags"
        headers = {}
        if backend.auth:
            token = self._ensure_auth(backend)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        try:
            ctx = None
            if url.startswith("https"):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                return resp.status == 200
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Auth / Token management
    # -----------------------------------------------------------------------

    def _ensure_auth(self, backend: OllamaBackend, force: bool = False) -> Optional[str]:
        """Get auth token — from cache, file, or fresh login."""
        if not backend.auth:
            return None

        # Memory cache
        if not force and backend.name in self._token_cache:
            return self._token_cache[backend.name]

        # File cache
        if not force:
            token = self._load_token_from_file(backend.name)
            if token:
                self._token_cache[backend.name] = token
                return token

        # Login
        auth = backend.auth
        if auth.get("type") == "bearer_ldap":
            token = self._ldap_login(auth, backend.name)
            if token:
                self._token_cache[backend.name] = token
                self._save_token_to_file(backend.name, token)
                return token

        return None

    def _ldap_login(self, auth: dict, backend_name: str = "") -> Optional[str]:
        """POST to login_url with user/password, return JWT token."""
        import os
        login_url = auth.get("login_url", "")
        user = auth.get("user", "") or os.getlogin()
        password = self._resolve_password(auth)

        if not login_url or not user:
            logger.error("LDAP auth config incomplete (no login_url or user)")
            return None
        if not password:
            logger.warning("[%s] LDAP password file not found", backend_name)
            return None

        payload = json.dumps({"user": user, "password": password}).encode("utf-8")
        try:
            ctx = None
            if login_url.startswith("https"):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                login_url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read())
                token = data.get("token")
                if token:
                    logger.info("LDAP login success: %s", user)
                    return token
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if e.code == 400 and ("incorrect" in body.lower() or "invalid" in body.lower()):
                self._token_cache.pop(backend_name, None)
                try:
                    TOKEN_PATH.unlink(missing_ok=True)
                except OSError:
                    pass
            logger.error("[%s] LDAP login failed (HTTP %s): %s", backend_name, e.code, user)
        except Exception as e:
            logger.error("[%s] LDAP login failed: %s", backend_name, e)
        return None

    def _resolve_password(self, auth: dict) -> str:
        """Resolve password from: password_file > password_env > password."""
        import os
        # password_file
        pf = auth.get("password_file")
        if pf:
            path = Path(pf).expanduser()
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        # password_env
        pe = auth.get("password_env")
        if pe:
            val = os.environ.get(pe, "")
            if val:
                return val
        # direct password (not recommended)
        return auth.get("password", "")

    def _load_token_from_file(self, backend_name: str) -> Optional[str]:
        if TOKEN_PATH.exists():
            try:
                data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
                if data.get("backend") == backend_name:
                    return data.get("token")
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _save_token_to_file(self, backend_name: str, token: str):
        try:
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(
                json.dumps({
                    "backend": backend_name,
                    "token": token,
                    "obtained_at": datetime.now().isoformat(),
                }, ensure_ascii=False),
                encoding="utf-8",
            newline="\n")
        except OSError as e:
            logger.warning("Failed to save token: %s", e)

    def _load_cached_tokens(self):
        if TOKEN_PATH.exists():
            try:
                data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
                name = data.get("backend")
                token = data.get("token")
                if name and token:
                    self._token_cache[name] = token
            except (json.JSONDecodeError, OSError):
                pass

    # -----------------------------------------------------------------------
    # Long DIE marker (向使用者確認是否永久停用)
    # -----------------------------------------------------------------------

    LONG_DIE_MARKER = CLAUDE_DIR / "workflow" / ".backend_long_die.json"

    @staticmethod
    def _write_long_die_marker(backend: 'OllamaBackend', until_str: str):
        """Write marker when long_die triggers — hooks/sessions ask user to disable."""
        try:
            OllamaClient.LONG_DIE_MARKER.parent.mkdir(parents=True, exist_ok=True)
            OllamaClient.LONG_DIE_MARKER.write_text(json.dumps({
                "type": "long_die",
                "backend": backend.name,
                "until": until_str,
                "message": (
                    f"遠端 Ollama ({backend.name}) 連續失敗，已進入長期停用狀態"
                    f"（等到 {until_str} 才重試）。是否要永久停用此 backend？"
                    f"（可在 config.json 的 ollama_backends.{backend.name}.enabled 手動重新啟用）"
                ),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        except OSError:
            pass

    @staticmethod
    def _clear_long_die_marker():
        try:
            OllamaClient.LONG_DIE_MARKER.unlink(missing_ok=True)
        except OSError:
            pass


def check_long_die_status() -> Optional[Dict[str, str]]:
    """Check if a backend entered long_die and needs user decision.

    Returns None if no pending decision, or a dict with:
      {"type": "long_die", "backend": ..., "until": ..., "message": ...}

    After user decides, call disable_backend() or clear the marker.
    """
    marker = OllamaClient.LONG_DIE_MARKER
    if marker.exists():
        try:
            return json.loads(marker.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def disable_backend(backend_name: str) -> bool:
    """Permanently disable a backend by setting enabled=false in config.json."""
    if not CONFIG_PATH.exists():
        return False
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        backends = config.get("vector_search", {}).get("ollama_backends", {})
        if backend_name not in backends:
            return False
        backends[backend_name]["enabled"] = False
        CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        newline="\n")
        # Clear marker + reset singleton so next get_client() picks up change
        OllamaClient._clear_long_die_marker()
        global _client_instance
        _client_instance = None
        logger.info("[%s] permanently disabled in config", backend_name)
        return True
    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.error("Failed to disable backend %s: %s", backend_name, e)
        return False


def enable_backend(backend_name: str) -> bool:
    """Re-enable a previously disabled backend."""
    if not CONFIG_PATH.exists():
        return False
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        backends = config.get("vector_search", {}).get("ollama_backends", {})
        if backend_name not in backends:
            return False
        backends[backend_name]["enabled"] = True
        CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        newline="\n")
        OllamaClient._clear_long_die_marker()
        global _client_instance
        _client_instance = None
        logger.info("[%s] re-enabled in config", backend_name)
        return True
    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.error("Failed to enable backend %s: %s", backend_name, e)
        return False


# ---------------------------------------------------------------------------
# Time boundary helper
# ---------------------------------------------------------------------------

def _next_time_boundary() -> float:
    """Return timestamp of the next 6h boundary (00:00/06:00/12:00/18:00)."""
    now = datetime.now()
    for h in TIME_BOUNDARIES:
        t = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if t > now:
            return t.timestamp()
    # Next day 00:00
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.timestamp()


# ---------------------------------------------------------------------------
# Config loading + Singleton
# ---------------------------------------------------------------------------

_client_instance: Optional[OllamaClient] = None


def _build_backends_from_config(config: dict) -> List[OllamaBackend]:
    """Build backend list from config. Supports new and legacy formats."""
    vs = config.get("vector_search", config)
    backends_cfg = vs.get("ollama_backends", {})

    if backends_cfg:
        # New format
        backends = []
        for name, cfg in backends_cfg.items():
            enabled = cfg.get("enabled", True)
            backends.append(OllamaBackend(
                name=name,
                base_url=cfg.get("base_url", "http://127.0.0.1:11434"),
                auth=cfg.get("auth"),
                llm_model=cfg.get("llm_model"),
                embedding_model=cfg.get("embedding_model"),
                priority=cfg.get("priority", 99),
                enabled=enabled,
                think=cfg.get("think", False),
                llm_num_predict=cfg.get("llm_num_predict", 2048),
            ))
        return backends

    # Legacy format — single local backend
    return [OllamaBackend(
        name="local",
        base_url=vs.get("ollama_base_url", "http://127.0.0.1:11434"),
        auth=None,
        llm_model=vs.get("ollama_llm_model", "qwen3:1.7b"),
        embedding_model=vs.get("embedding_model", "qwen3-embedding"),
        priority=1,
    )]


def get_client(config: dict = None) -> OllamaClient:
    """Get or create singleton OllamaClient."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    if config is None:
        config = {}
        if CONFIG_PATH.exists():
            try:
                config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    backends = _build_backends_from_config(config)
    _client_instance = OllamaClient(backends)
    return _client_instance


def reset_client():
    """Reset singleton (for testing)."""
    global _client_instance
    _client_instance = None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    client = get_client()
    print(f"Backends: {[b.name for b in client._backends]}")

    # Test LLM
    llm_be = client._pick_backend("llm")
    print(f"LLM backend: {llm_be.name if llm_be else 'NONE'}")
    if llm_be:
        resp = client.generate("Reply with just the word 'OK'", timeout=30)
        print(f"Generate test: {repr(resp[:100])}")

    # Test embedding
    emb_be = client._pick_backend("embedding")
    print(f"Embedding backend: {emb_be.name if emb_be else 'NONE'}")
    if emb_be:
        vecs = client.embed(["hello world"])
        if vecs:
            print(f"Embed test: {len(vecs[0])} dims")
        else:
            print("Embed test: FAILED")

    print("Done.")
