"""Re-export worker helpers and implementations."""

from conduit.detect.modules.openai.workers.base import Worker, data_dir, env_flag, fixtures_dir
from conduit.detect.modules.openai.workers.changelog_parser import ChangelogParserWorker
from conduit.detect.modules.openai.workers.deprecation_scraper import DeprecationScraperWorker
from conduit.detect.modules.openai.workers.model_polling import ModelPollingWorker
from conduit.detect.modules.openai.workers.openapi_diff import OpenAPIDiffWorker
from conduit.detect.modules.openai.workers.sdk_release import SDKReleaseWorker

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
