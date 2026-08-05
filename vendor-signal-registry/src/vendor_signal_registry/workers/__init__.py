"""Re-export worker helpers and implementations."""

from vendor_signal_registry.workers.base import Worker, data_dir, env_flag, fixtures_dir
from vendor_signal_registry.workers.changelog_parser import ChangelogParserWorker
from vendor_signal_registry.workers.deprecation_scraper import DeprecationScraperWorker
from vendor_signal_registry.workers.model_polling import ModelPollingWorker
from vendor_signal_registry.workers.openapi_diff import OpenAPIDiffWorker
from vendor_signal_registry.workers.sdk_release import SDKReleaseWorker

ALL_WORKERS = [
    OpenAPIDiffWorker,
    DeprecationScraperWorker,
    ModelPollingWorker,
    ChangelogParserWorker,
    SDKReleaseWorker,
]

__all__ = [
    "Worker",
    "data_dir",
    "env_flag",
    "fixtures_dir",
    "OpenAPIDiffWorker",
    "DeprecationScraperWorker",
    "ModelPollingWorker",
    "ChangelogParserWorker",
    "SDKReleaseWorker",
    "ALL_WORKERS",
]
