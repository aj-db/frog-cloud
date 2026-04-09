import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from crawler.worker import _find_internal_db_artifact_from_stdout

stdout_log = Path(os.environ["SF_STDOUT_LOG"])
artifact = _find_internal_db_artifact_from_stdout(stdout_log)
print("STDOUT_EXISTS", stdout_log.exists())
print("ARTIFACT", artifact)
print("ARTIFACT_EXISTS", artifact.exists() if artifact else None)
