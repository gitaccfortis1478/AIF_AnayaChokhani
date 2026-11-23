import json

import httpx
import pytest
from fastapi import HTTPException

from formaos.api.supabase_projects import SupabaseProjectStore, restore_images


@pytest.fixture
def store_for():
    clients = []

    def make_store(handler):
        store = SupabaseProjectStore("https://example.test", "sb_secret_test")
        store._client.close()
        store._client = httpx.Client(base_url="https://example.test/rest/v1/", transport=httpx.MockTransport(handler))
        clients.append(store._client)
        return store

    yield make_store
    for client in clients:
        client.close()


def test_draft_update_filters_by_owner_and_excludes_image_bytes(store_for):
    def send(request):
        assert request.method == "PATCH"
        assert request.url.path == "/rest/v1/yourspace_projects"
        assert request.url.params["project_id"] == "eq.project-1"
        assert request.url.params["user_id"] == "eq.owner-1"
        assert json.loads(request.content) == {
            "project_name": "Living room",
            "draft_progress": {"step": 2, "photos": [{"name": "room.jpg"}]},
        }
        return httpx.Response(200, json=[{"project_id": "project-1"}])

    store_for(send).save_draft("project-1", "owner-1", "Living room", {
        "step": 2, "photos": [{"name": "room.jpg", "dataUrl": "data:image/jpeg;base64,example"}],
    })


def test_draft_cannot_claim_another_owners_project(store_for):
    def send(request):
        if request.method == "POST":
            assert "resolution=ignore-duplicates" in request.headers["Prefer"]
        else:
            assert request.url.params["user_id"] == "eq.other-owner"
        return httpx.Response(200, json=[])

    with pytest.raises(HTTPException) as denied:
        store_for(send).save_draft("project-1", "other-owner", "Living room", {"step": 2})
    assert denied.value.status_code == 404


def test_design_round_trip_uses_project_owner_and_keeps_images_local(store_for):
    image = "data:image/jpeg;base64,example"
    generated_at = "2026-11-22T00:00:00+00:00"
    summary = {
        "design_id": "design-1", "project_id": "project-1", "project_name": "Living room",
        "session_id": "local-1", "user_id": "owner-1", "generated_at": generated_at,
        "status": "passed", "room_type": "living_room", "total_price_inr": 0,
        "item_count": 0, "style_words": ["modern"],
    }
    design = {**summary, "concept_image": {"revision_id": "r1", "image_data_url": image}}
    row = {}

    def send(request):
        if request.url.path.endswith("/yourspace_projects"):
            assert request.url.params["user_id"] == "eq.owner-1"
            return httpx.Response(200, json=[{"project_id": "project-1"}])
        if request.method == "POST":
            row.update(json.loads(request.content))
            assert row["style_words"] == ["modern"]
            assert image not in request.content.decode()
            assert "image_data_url" not in row
            row["project"] = {"project_id": "project-1", "project_name": "Living room", "user_id": "owner-1"}
            return httpx.Response(201)
        assert "yourspace_projects!inner" in request.url.params["select"]
        rows = [row] if request.url.params["project.user_id"] == "eq.owner-1" else []
        return httpx.Response(200, json=rows)

    store = store_for(send)
    store.save_design(design, summary)
    assert store.get_design("design-1", "other-owner") is None
    remote = store.get_design("design-1", "owner-1")
    assert remote["concept_image"] == {"revision_id": "r1"}
    assert restore_images(remote, design)["concept_image"]["image_data_url"] == image
