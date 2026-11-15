from uuid import uuid4
import httpx
import pytest

from app.core.config import settings
from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_multitenant_rls_isolation(client: httpx.AsyncClient):
    suffix = uuid4().hex[:8]

    # Registrar Organización A y crear una parcela
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Org A {suffix}",
            "email": f"owner_a_{suffix}@agrostake.mx",
            "password": "ClaveSeguraOrgA2026!",
            "full_name": "Owner A",
        },
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["access_token"]

    parcel_res = await client.post(
        "/api/v1/parcels",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Parcela Secreta A", "latitude": 25.42, "longitude": -101.0},
    )
    assert parcel_res.status_code == 201
    parcel_a_id = parcel_res.json()["id"]

    # Registrar Organización B e intentar leer o modificar recursos de Org A
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Org B {suffix}",
            "email": f"owner_b_{suffix}@agrostake.mx",
            "password": "ClaveSeguraOrgB2026!",
            "full_name": "Owner B",
        },
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    list_b = await client.get("/api/v1/parcels", headers=headers_b)
    assert list_b.status_code == 200
    assert list_b.json() == []

    detail_b = await client.get(f"/api/v1/parcels/{parcel_a_id}", headers=headers_b)
    assert detail_b.status_code == 404

    cross_stake = await client.post(
        "/api/v1/stakes",
        headers=headers_b,
        json={"parcel_id": parcel_a_id, "device_uid": f"HACK-{suffix}"},
    )
    assert cross_stake.status_code == 404


async def test_rbac_viewer_cannot_write(client: httpx.AsyncClient):
    suffix = uuid4().hex[:8]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Org RBAC {suffix}",
            "email": f"owner_{suffix}@agrostake.mx",
            "password": "ClaveSeguraOwner2026!",
            "full_name": "Owner RBAC",
        },
    )
    owner_token = reg.json()["access_token"]

    viewer_email = f"viewer_{suffix}@agrostake.mx"
    viewer_pwd = "ClaveSeguraViewer2026!"
    create_viewer = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "email": viewer_email,
            "password": viewer_pwd,
            "full_name": "Usuario Viewer",
            "role": "viewer",
        },
    )
    assert create_viewer.status_code == 201

    login_viewer = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer_email, "password": viewer_pwd},
    )
    viewer_token = login_viewer.json()["access_token"]

    forbidden_parcel = await client.post(
        "/api/v1/parcels",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"name": "Intento Viewer", "latitude": 25.4, "longitude": -101.0},
    )
    assert forbidden_parcel.status_code == 403


async def test_refresh_token_rotation_blocks_replay(client: httpx.AsyncClient):
    suffix = uuid4().hex[:8]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Org Token {suffix}",
            "email": f"tok_{suffix}@agrostake.mx",
            "password": "ClaveSeguraToken2026!",
            "full_name": "Owner Token",
        },
    )
    first_refresh = reg.json()["refresh_token"]

    rot = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rot.status_code == 200
    assert rot.json()["refresh_token"] != first_refresh

    # Reutilizar el refresh token anterior debe fallar con 401
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert replay.status_code == 401


async def test_iot_gateway_auth_and_range_validation(client: httpx.AsyncClient):
    bad_key = await client.post(
        "/api/v1/iot/telemetry",
        headers={"X-IoT-API-Key": "clave_incorrecta"},
        json={"device_uid": "ESP32-TEST", "soil_temperature_c": 22.0},
    )
    assert bad_key.status_code == 401

    invalid_temp = await client.post(
        "/api/v1/iot/telemetry",
        headers={"X-IoT-API-Key": settings.IOT_INGEST_API_KEY},
        json={"device_uid": "ESP32-TEST", "soil_temperature_c": -999},
    )
    assert invalid_temp.status_code == 422
