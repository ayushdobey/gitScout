def test_health_check(client):
    """Test health check endpoint reports operational status and DB health."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["app_name"] == "GitScout"


def test_auth_registration_and_login_flow(client):
    """
    Test end-to-end authentication lifecycle:
    1. Register user
    2. Attempt duplicate registration (must fail with 400)
    3. Login to obtain JWT access token
    4. Authenticate /me with Bearer token
    5. Access /me without token (must fail with 401)
    """
    # 1. Register
    reg_payload = {
        "email": "student@gitscout.io",
        "password": "Password123!",
        "full_name": "ADBMS Student"
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "student@gitscout.io"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # 2. Reject duplicate email
    dup_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_resp.status_code == 400

    # 3. Login
    login_payload = {
        "email": "student@gitscout.io",
        "password": "Password123!"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    # 4. Authenticate /me
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "student@gitscout.io"
    assert me_data["full_name"] == "ADBMS Student"

    # 5. Unauthorized access
    unauth_resp = client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

