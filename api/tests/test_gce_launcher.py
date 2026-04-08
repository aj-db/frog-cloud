from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from uuid import uuid4

from app.models import JobExecutor, JobStatus
from crawler import launcher


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, value):
        self._value = value

    def execute(self, _query):
        return _FakeResult(self._value)

    def refresh(self, _obj):
        return None


def test_launch_worker_vm_passes_template_on_insert_request(monkeypatch):
    job_id = uuid4()
    job = SimpleNamespace(
        id=job_id,
        tenant_id=uuid4(),
        executor=JobExecutor.gce,
        status=JobStatus.queued,
    )
    db = _FakeSession(job)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        launcher,
        "get_settings",
        lambda: SimpleNamespace(
            gcp_project_id="fox-seo-sandbox",
            gce_zone="us-central1-a",
            gce_instance_template="staging-frog-worker-template",
        ),
    )
    monkeypatch.setattr(launcher, "transition_job_status", lambda *args, **kwargs: True)

    class FakeItems:
        def __init__(self, **kwargs):
            self.key = kwargs["key"]
            self.value = kwargs["value"]

    class FakeMetadata:
        def __init__(self, **kwargs):
            self.items = kwargs["items"]

    class FakeInstance:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]
            self.metadata = kwargs["metadata"]
            self.source_instance_template = kwargs.get("source_instance_template")

    class FakeInsertInstanceRequest:
        def __init__(self, **kwargs):
            self.project = kwargs["project"]
            self.zone = kwargs["zone"]
            self.instance_resource = kwargs["instance_resource"]
            self.source_instance_template = kwargs.get("source_instance_template")

    class FakeInstancesClient:
        def insert(self, request):
            captured["request"] = request
            return SimpleNamespace(name="op-123")

    class FakeInstanceTemplatesClient:
        def get(self, **_kwargs):
            return SimpleNamespace(
                properties=SimpleNamespace(
                    metadata=SimpleNamespace(
                        items=[
                            FakeItems(key="enable-oslogin", value="TRUE"),
                            FakeItems(key="startup-script", value="echo bootstrap"),
                        ]
                    )
                )
            )

    fake_compute_v1 = ModuleType("compute_v1")
    fake_compute_v1.Items = FakeItems
    fake_compute_v1.Metadata = FakeMetadata
    fake_compute_v1.Instance = FakeInstance
    fake_compute_v1.InsertInstanceRequest = FakeInsertInstanceRequest
    fake_compute_v1.InstancesClient = FakeInstancesClient
    fake_compute_v1.InstanceTemplatesClient = FakeInstanceTemplatesClient

    monkeypatch.setitem(sys.modules, "google.cloud.compute_v1", fake_compute_v1)

    result = launcher.launch_worker_vm(db, job_id)

    assert result == "op-123"
    request = captured["request"]
    assert request.source_instance_template == (
        "projects/fox-seo-sandbox/global/instanceTemplates/staging-frog-worker-template"
    )
    assert request.instance_resource.source_instance_template is None
    metadata = {
        item.key: item.value for item in request.instance_resource.metadata.items
    }
    assert metadata["enable-oslogin"] == "TRUE"
    assert metadata["startup-script"] == "echo bootstrap"
    assert metadata["frog_job_id"] == str(job_id)
    assert metadata["frog_tenant_id"] == str(job.tenant_id)
