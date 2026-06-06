import asyncio
import json
import sys
from pathlib import Path

async def test_universal_engine():
    """Test Universal Multi-Modal Engine"""
    print("🧪 Testing Universal Multi-Modal Engine...")
    
    # 1. Initialize engine
    print("\n1. Testing Engine Initialization...")
    from src.universal_multimodal_engine import UniversalMultiModalEngine
    
    engine = UniversalMultiModalEngine()
    print("   Engine initialized successfully")
    
    # 2. Test content mode settings
    print("\n2. Testing Content Mode Management...")
    user_id = "test_user_universal"
    
    # Enable safe and creative modes
    res1 = engine.set_content_mode(user_id, 'safe', enabled=True, settings={'theme': 'dark'})
    res2 = engine.set_content_mode(user_id, 'creative', enabled=True, settings={'preferred_style': 'watercolor'})
    res3 = engine.set_content_mode(user_id, 'nsfw', enabled=False) # Keep disabled
    
    assert res1['status'] == 'success'
    assert res2['status'] == 'success'
    assert res3['status'] == 'success'
    
    modes = engine.get_content_mode(user_id)
    print("   User active modes:")
    for mode_name, settings in modes.items():
        print(f"     - {mode_name}: enabled={settings['enabled']}")
        
    assert modes['safe']['enabled'] is True
    assert modes['creative']['enabled'] is True
    assert modes['nsfw']['enabled'] is False
    
    # 3. Test content preference setting
    print("\n3. Testing Content Preference Management...")
    pref_res1 = engine.set_content_preference(user_id, 'creative', 'styles', 'abstract', 'high', confidence=0.8)
    pref_res2 = engine.set_content_preference(user_id, 'creative', 'mediums', 'oil_paint', 'high', confidence=0.9)
    assert pref_res1['status'] == 'success'
    assert pref_res2['status'] == 'success'
    
    preferences = engine.get_content_preferences(user_id, 'creative')
    print("   Stored preferences for creative mode:", preferences)
    assert preferences['styles']['abstract']['value'] == 'high'
    assert preferences['mediums']['oil_paint']['confidence'] == 0.9
    
    # 4. Test experience generation
    print("\n4. Testing Full Experience Generation...")
    
    request = {
        'user_id': user_id,
        'content_mode': 'creative',
        'persona': {'id': 'painter', 'name': 'Vincent'},
        'message': 'Paint a starry night sky above a sleepy village',
        'context': {'scenario': 'art studio collab'},
        'intensity': 'medium',
        'include_text': True,
        'include_image': True,
        'include_voice': True
    }
    
    experience = await engine.create_full_experience(request)
    print("   Generated Experience Mode:", experience['content_mode'])
    print("   Generated Narrative Text:", experience['text']['text'])
    print("   Safety Score:", experience['text']['safety_score'])
    print("   Quality Score:", experience['text']['quality_score'])
    print("   Image Placeholder URL:", experience['image']['image'])
    print("   Voice Placeholder URL:", experience['voice']['voice'])
    
    assert experience['content_mode'] == 'creative'
    assert 'Vincent' in experience['text']['metadata']['prompt']
    assert experience['image']['image'] == "https://example.com/creative_image_placeholder.jpg"
    
    # 5. Test history retrieval
    print("\n5. Testing Experience Retrieval...")
    history = engine.get_user_experiences(user_id, 'creative', limit=5)
    print(f"   Retrieved {len(history)} stored creative experiences")
    assert len(history) >= 1
    
    print("\n✅ Universal Multi-Modal Engine test passed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_universal_engine())
    except Exception as e:
        print("❌ Test failed:", e)
        sys.exit(1)
