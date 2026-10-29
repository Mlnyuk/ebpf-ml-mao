import json
import os
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def epoch(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return dt.timestamp()


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def secret(path):
    try:
        return Path(path).read_text().strip()
    except FileNotFoundError:
        return ''


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'(?i)^(password|secret|token|api[_-]?key|authorization)$', k)
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)(bearer\s+)[\w.\-/+=]+', r'\1[REDACTED]', value)
        value = re.sub(r'(?i)((?:password|token|api[_-]?key|secret)\s*[=:]\s*)[^\s,;]+', r'\1[REDACTED]', value)
        value = re.sub(r'(https?://)[^\s/@:]+:[^\s/@]+@', r'\1[REDACTED]@', value)
    return value


class RemoteError(Exception):
    pass


def request(url, method='GET', body=None, headers=None, context=None, timeout=12, limit=2_000_000, raw=False):
    payload = compact(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=payload, method=method,
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(req, context=context, timeout=timeout) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise RemoteError('response exceeds byte limit')
            return data.decode() if raw else json.loads(data)
    except urllib.error.HTTPError as e:
        # Do not persist response bodies that can echo credentials or prompts.
        raise RemoteError(f'HTTP {e.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RemoteError(type(e).__name__) from None


class Settings:
    namespace = os.getenv('TARGET_NAMESPACE', 'rca-lab')
    database = os.getenv('DATABASE', '/data/rca.sqlite3')
    prometheus = os.getenv('PROMETHEUS_URL', 'http://my-monitoring-kube-prometh-prometheus.monitoring.svc:9090')
    provider = os.getenv('LLM_PROVIDER', 'openrouter')
    api_url = os.getenv('LLM_URL', 'https://openrouter.ai/api/v1/chat/completions' if provider == 'openrouter'
                        else 'https://api.z.ai/api/paas/v4/chat/completions')
    model = os.getenv('LLM_MODEL', 'z-ai/glm-5.3-flash' if provider == 'openrouter' else 'glm-5.3-flash')
    api_key_file = os.getenv('LLM_API_KEY_FILE', '/secrets/llm/api-key')
    llm_enabled = os.getenv('LLM_ENABLED', 'false').lower() == 'true'
    auth_file = os.getenv('AUTH_TOKEN_FILE', '/secrets/auth/token')
    max_requests = int(os.getenv('MAX_LLM_REQUESTS', '6'))
    max_tools = int(os.getenv('MAX_TOOL_CALLS', '8'))
    max_output = int(os.getenv('MAX_OUTPUT_TOKENS', '4096'))
    max_seconds = int(os.getenv('MAX_INVESTIGATION_SECONDS', '240'))
    max_daily = int(os.getenv('MAX_DAILY_INVESTIGATIONS', '20'))
    max_context_chars = int(os.getenv('MAX_CONTEXT_CHARS', '65000'))
    context_mode = os.getenv('RCA_CONTEXT_MODE', 'compact-v4')
    max_input_chars_total = int(os.getenv('MAX_INPUT_CHARS_TOTAL', '120000'))
    allow_ebpf = os.getenv('ALLOW_EBPF', 'true').lower() == 'true'
    routing = {}
    input_price = float(os.getenv('INPUT_USD_PER_MILLION', '0.15'))
    cached_price = float(os.getenv('CACHED_INPUT_USD_PER_MILLION', '0.03'))
    output_price = float(os.getenv('OUTPUT_USD_PER_MILLION', '0.50'))


class Kubernetes:
    def __init__(self):
        self.base = os.getenv('KUBE_API', 'https://kubernetes.default.svc')
        directory = '/var/run/secrets/kubernetes.io/serviceaccount'
        self.token_file = directory + '/token'
        self.context = ssl.create_default_context(cafile=directory + '/ca.crt')

    def get(self, path, raw=False):
        return request(self.base + path, headers={'Authorization': 'Bearer ' + secret(self.token_file)},
                       context=self.context, raw=raw)
