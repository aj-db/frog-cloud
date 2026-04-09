import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from crawler.extractor import _load_crawl_artifact

p = Path(os.environ["SF_DB_PATH"])
print("EXISTS", p.exists())
try:
    crawl = _load_crawl_artifact(p, "/usr/bin/screamingfrogseospider")
    print("LOAD_OK", type(crawl).__name__)
except Exception as e:
    print("LOAD_FAIL", repr(e))
