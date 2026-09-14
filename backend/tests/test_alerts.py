"""Tests for alert endpoints."""


def test_get_alerts_empty(client):
    response = client.get("/api/alerts/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_there_is_no_subscription_that_never_delivers(client):
    """
    /alerts/subscribe was removed, and this records why.

    It accepted a webhook or FCM token, stored it, and answered
    {"status": "subscribed"} — but nothing ever read the subscriptions back and
    nothing delivered to them. The three tests that used to live here asserted
    that it SAID "subscribed", which is the one thing it did correctly.

    Driver notifications are delivered over /api/notifications/ws. If push
    delivery to closed tabs is ever wanted, build the delivery first; an
    endpoint that promises it without it is worse than no endpoint.
    """
    response = client.post("/api/alerts/subscribe", json={
        "user_id": "test-user-001", "endpoint": "https://example.com/webhook",
    })
    assert response.status_code in (404, 405), (
        "a subscription endpoint is back — does anything deliver to it?"
    )
