"""data_capture.py — data capture and publication for NetProbe.

Provides:
  - DeviceInfo.collect()     : host/OS/platform/python metadata (req 2.3)
  - resolve_user(cli_user)   : flag > NETPROBE_USER env > '' (req 3.1-3.4)
  - NotionConfig             : dataclass holding Notion credentials (req 4.2)
  - RunRecord.build(...)     : canonical flat run record (req 2.1-2.6)
  - LocalLogWriter.append()  : JSONL append writer (req 1.1-1.6, 5.1)
  - NotionPublisher.publish(): optional Notion row creation (req 4.1, 4.3-4.5)
  - record_run(...)          : orchestration entry point (req 1.6, 4.4, 5.1-5.3)
"""

from __future__ import annotations

import json
import os
import platform
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NamedTuple


# ---------------------------------------------------------------------------
# DeviceInfo
# ---------------------------------------------------------------------------

class DeviceInfo:
    @staticmethod
    def collect() -> dict[str, str]:
        """Return {'hostname', 'os', 'platform', 'python_version'}."""
        def _safe(fn: object) -> str:
            try:
                return str(fn())  # type: ignore[operator]
            except Exception:
                return ''

        return {
            'hostname': _safe(socket.gethostname),
            'os': _safe(platform.system),
            'platform': _safe(platform.platform),
            'python_version': _safe(lambda: sys.version),
        }


# ---------------------------------------------------------------------------
# resolve_user
# ---------------------------------------------------------------------------

def resolve_user(cli_user: str | None) -> str:
    """Return cli_user if non-empty, else NETPROBE_USER env, else empty string."""
    if cli_user:
        return cli_user
    return os.environ.get('NETPROBE_USER', '')


# ---------------------------------------------------------------------------
# NotionConfig
# ---------------------------------------------------------------------------

@dataclass
class NotionConfig:
    token: str
    database_id: str

    @staticmethod
    def from_env() -> 'NotionConfig | None':
        """Return NotionConfig when both credentials are present, else None."""
        token = os.environ.get('NOTION_TOKEN', '')
        database_id = os.environ.get('NOTION_DATABASE_ID', '')
        if not token or not database_id:
            return None
        return NotionConfig(token=token, database_id=database_id)


# ---------------------------------------------------------------------------
# RunRecord
# ---------------------------------------------------------------------------

class RunRecord:
    @staticmethod
    def build(
        results: dict,
        stats: dict,
        user: str,
        device: dict[str, str],
        timestamp: str,
    ) -> dict:
        """Return the canonical flat record dict."""
        latency_stats = stats.get('latency_stats') or {}
        jitter_stats = stats.get('jitter_stats') or {}
        packet_loss_stats = stats.get('packet_loss_stats') or {}
        dns_stats = stats.get('dns_stats') or {}
        bandwidth = results.get('bandwidth') or {}
        wifi = results.get('wifi_stability') or {}

        record: dict = {
            'timestamp': timestamp,
            'user': user,
            # device fields
            'hostname': device.get('hostname', ''),
            'os': device.get('os', ''),
            'platform': device.get('platform', ''),
            'python_version': device.get('python_version', ''),
            # run context
            'test_scenario': results.get('test_scenario'),
            # statistics
            'quality_score': stats.get('quality_score'),
            'latency_avg_ms': latency_stats.get('avg_ms'),
            'latency_min_ms': latency_stats.get('min_ms'),
            'latency_max_ms': latency_stats.get('max_ms'),
            'jitter_avg_ms': jitter_stats.get('avg_ms'),
            'packet_loss_percent': packet_loss_stats.get('avg_percent'),
            'dns_avg_ms': dns_stats.get('avg_ms'),
            'download_speed_mbps': bandwidth.get('download_speed_mbps'),
            'wifi_stability_score': wifi.get('wifi_stability_score'),
            'wifi_score_type': wifi.get('wifi_score_type'),
            'avg_snr_db': wifi.get('avg_snr_db'),
            'wifi_ssid': wifi.get('wifi_ssid'),
        }

        # Location fields — emit only when location is collected (2.5, 2.6)
        loc = results.get('location')
        if isinstance(loc, dict) and 'error' not in loc and loc.get('latitude') is not None:
            for key in ('name', 'latitude', 'longitude', 'city', 'country'):
                val = loc.get(key)
                if val is not None:
                    out_key = 'location_name' if key == 'name' else key
                    record[out_key] = val

        return record


# ---------------------------------------------------------------------------
# LocalLogWriter
# ---------------------------------------------------------------------------

class LocalLogWriter:
    def __init__(self, path: str) -> None:
        self.path = path

    def append(self, record: dict) -> bool:
        """Append record as one JSONL line. Return True on success, False on failure."""
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(record) + '\n')
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# PublishOutcome
# ---------------------------------------------------------------------------

class PublishOutcome(NamedTuple):
    ok: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# NotionPublisher
# ---------------------------------------------------------------------------

class NotionPublisher:
    def __init__(self, config: NotionConfig) -> None:
        self._config = config

    def publish(self, record: dict) -> PublishOutcome:
        """Create one DB row. Return PublishOutcome(ok, error)."""
        try:
            import notion_client  # lazy import — keeps tests independent of the package
            client = notion_client.Client(auth=self._config.token)
        except ImportError as exc:
            return PublishOutcome(ok=False, error=f'notion-client not installed: {exc}')
        except Exception as exc:
            return PublishOutcome(ok=False, error=f'Notion client error: {exc}')

        def _text(val: object) -> list:
            return [{'text': {'content': str(val) if val is not None else ''}}]

        def _number(val: object) -> dict | None:
            return {'number': val} if val is not None else None

        props: dict = {
            'Name': {'title': _text(record.get('timestamp', ''))},
            'Timestamp': {'date': {'start': record.get('timestamp')}},
            'User': {'rich_text': _text(record.get('user', ''))},
            'Hostname': {'rich_text': _text(record.get('hostname', ''))},
            'OS': {'rich_text': _text(record.get('os', ''))},
        }

        for notion_key, record_key in (
            ('Quality Score', 'quality_score'),
            ('Latency (ms)', 'latency_avg_ms'),
            ('Packet Loss (%)', 'packet_loss_percent'),
            ('Jitter (ms)', 'jitter_avg_ms'),
            ('DNS (ms)', 'dns_avg_ms'),
            ('Download (Mbps)', 'download_speed_mbps'),
            ('WiFi Score', 'wifi_stability_score'),
        ):
            num = _number(record.get(record_key))
            if num is not None:
                props[notion_key] = num

        for notion_key, record_key in (
            ('SSID', 'wifi_ssid'),
            ('Location Name', 'location_name'),
            ('City', 'city'),
            ('Country', 'country'),
        ):
            if record.get(record_key) is not None:
                props[notion_key] = {'rich_text': _text(record[record_key])}

        try:
            client.pages.create(
                parent={'database_id': self._config.database_id},
                properties=props,
            )
            return PublishOutcome(ok=True)
        except Exception as exc:
            return PublishOutcome(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# record_run — orchestration entry point
# ---------------------------------------------------------------------------

DEFAULT_LOG_PATH = 'netprobe-results.jsonl'


def record_run(
    results: dict,
    stats: dict,
    user: str,
    log_path: str,
    publish: bool,
    notion_config: 'NotionConfig | None',
) -> None:
    """Build the record, append it locally, then optionally publish to Notion."""
    timestamp = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    device = DeviceInfo.collect()
    record = RunRecord.build(results, stats, user=user, device=device, timestamp=timestamp)

    writer = LocalLogWriter(log_path)
    ok = writer.append(record)
    if ok:
        print(f'Run record saved to {log_path}')
    else:
        print(f'Warning: could not write run record to {log_path}')

    if not publish:
        return

    if notion_config is None:
        print('Warning: Notion credentials missing (NOTION_TOKEN / NOTION_DATABASE_ID). Skipping publication.')
        return

    publisher = NotionPublisher(notion_config)
    outcome = publisher.publish(record)
    if outcome.ok:
        print('Run record published to Notion.')
    else:
        print(f'Warning: Notion publication failed: {outcome.error}')
