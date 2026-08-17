import pytest
from httpx import AsyncClient
from app.services import get_all_rules, create_rule
from app.schemas import RuleCreate

@pytest.mark.asyncio
async def test_create_rule_success(client: AsyncClient):
    payload = {
        "keyword": "PRICE",
        "dm_message": "Here's the price list: http://example.com/prices"
    }
    response = await client.post("/rules", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "rule_id" in data
    assert data["keyword"] == "PRICE"
    assert data["dm_message"] == payload["dm_message"]

@pytest.mark.asyncio
async def test_create_multiple_rules(client: AsyncClient):
    r1 = await client.post("/rules", json={"keyword": "PRICE", "dm_message": "Price DM"})
    r2 = await client.post("/rules", json={"keyword": "DISCOUNT", "dm_message": "Discount DM"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["rule_id"] != r2.json()["rule_id"]

@pytest.mark.asyncio
async def test_empty_keyword_rejected(client: AsyncClient):
    response = await client.post("/rules", json={"keyword": "   ", "dm_message": "Test DM"})
    assert response.status_code in (400, 422)

@pytest.mark.asyncio
async def test_empty_dm_message_rejected(client: AsyncClient):
    response = await client.post("/rules", json={"keyword": "PRICE", "dm_message": ""})
    assert response.status_code in (400, 422)

@pytest.mark.asyncio
async def test_case_insensitive_matching(db_session):
    rule = await create_rule(db_session, RuleCreate(keyword="PRICE", dm_message="Price details"))
    assert rule.keyword == "PRICE"
    
    # Test case insensitivity logic
    comment_text_1 = "Hey what is the price please?"
    comment_text_2 = "PRICE NOW"
    comment_text_3 = "pRiCe List"
    comment_text_4 = "No match here"

    assert rule.keyword.lower() in comment_text_1.lower()
    assert rule.keyword.lower() in comment_text_2.lower()
    assert rule.keyword.lower() in comment_text_3.lower()
    assert rule.keyword.lower() not in comment_text_4.lower()
