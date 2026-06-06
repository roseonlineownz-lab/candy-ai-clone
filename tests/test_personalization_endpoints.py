import httpx
import sys

def test_personalization_endpoints():
    url = "http://127.0.0.1:8069"
    user_id = "test_user_integration_999"
    
    print("1. Setting user preferences (establishing pain and bondage as hard boundaries)...")
    payload = {
        "user_id": user_id,
        "intensity": 0.75, # hard intensity
        "visual_preference": 1.0,
        "boundary.pain": "hard",
        "boundary.bondage": "hard"
    }
    
    response = httpx.post(f"{url}/api/user/preferences", json=payload, timeout=30.0)
    print("Response status:", response.status_code)
    print("Response body:", response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    print("\n2. Getting user preferences...")
    response = httpx.get(f"{url}/api/user/preferences/{user_id}", timeout=30.0)
    print("Response body:", response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["boundaries"].get("boundary.pain") == "hard"
    assert data["boundaries"].get("boundary.bondage") == "hard"
    
    print("\n3. Testing boundary violation (sending message containing 'bondage')...")
    chat_payload = {
        "message": "I want to try some bondage play",
        "session_id": "test_session_nsfw",
        "user_id": user_id
    }
    response = httpx.post(f"{url}/api/chat/nsfw", json=chat_payload, timeout=30.0)
    print("Response status:", response.status_code)
    print("Response body:", response.json())
    assert response.status_code == 200
    chat_data = response.json()
    assert chat_data.get("status") == "boundary_violation"
    assert "Ik voel me hier niet comfortabel bij" in chat_data.get("response")
    
    print("\n4. Testing safe message (sending message 'hello')...")
    chat_payload = {
        "message": "Hallo, hoe gaat het?",
        "session_id": "test_session_nsfw",
        "user_id": user_id
    }
    response = httpx.post(f"{url}/api/chat/nsfw", json=chat_payload, timeout=30.0)
    print("Response status:", response.status_code)
    print("Response body:", response.json())
    assert response.status_code == 200
    chat_data = response.json()
    assert chat_data.get("status") != "boundary_violation"
    assert "response" in chat_data
    
    print("\n5. Checking learning summary...")
    response = httpx.get(f"{url}/api/user/learning/{user_id}", timeout=30.0)
    print("Response body:", response.json())
    assert response.status_code == 200
    summary = response.json()
    # Should have tracked the safe interaction
    assert summary["interaction_count"] >= 1
    
    print("\n🎉 All tests passed successfully!")

if __name__ == "__main__":
    try:
        test_personalization_endpoints()
    except Exception as e:
        print("❌ Test failed:", e)
        sys.exit(1)
