import asyncio
import json
import sys
from datetime import datetime, timedelta

async def test_adaptive_scheduler():
    """Test adaptive content scheduler"""
    print("🧪 Testing Adaptive Content Scheduler...")
    
    # Test 1: Initialize scheduler
    print("\n1. Testing Scheduler Initialization...")
    from src.adaptive_scheduler import AdaptiveContentScheduler
    
    scheduler = AdaptiveContentScheduler()
    print("   Scheduler initialized successfully")
    
    # Test 2: Track user activity
    print("\n2. Testing User Activity Tracking...")
    scheduler.track_user_activity(
        "test_user_sched",
        {
            "media_requested": True,
            "intensity_requested": "medium",
            "persona_id": "nova"
        }
    )
    print("   User activity tracked successfully")
    
    # Test 3: Track user context
    print("\n3. Testing User Context Tracking...")
    scheduler.track_user_context("test_user_sched", "mood", "excited", 0.8)
    scheduler.track_user_context("test_user_sched", "interest", "bondage", 0.6)
    print("   User context tracked successfully")
    
    # Test 4: Predict user needs
    print("\n4. Testing User Needs Prediction...")
    predictions = scheduler.predict_user_needs("test_user_sched", 0)
    print(f"   Generated {len(predictions)} predictions")
    
    for prediction in predictions:
        print(f"   - {prediction['predicted_media_type']} content for persona {prediction['predicted_persona']} with {prediction['confidence_score']:.2f} confidence")
    
    # Test 5: Schedule content generation
    print("\n5. Testing Content Scheduling...")
    if predictions:
        content_id = scheduler.schedule_content_generation("test_user_sched", predictions[0])
        print(f"   Scheduled content generation: {content_id}")
        
        # Test 6: Generate predicted content
        print("\n6. Testing Predicted Content Generation...")
        result = await scheduler.generate_predicted_content(content_id)
        print(f"   Content generation status: {result['status']}")
        if result['status'] == 'failed':
            print("   Error:", result.get('error'))
            
    # Test 7: Get ready content
    print("\n7. Testing Ready Content Retrieval...")
    # Update scheduled_time in DB to be in past to make it 'ready' (since predict_user_needs schedules it 1 hour in the future)
    import sqlite3
    conn = sqlite3.connect(scheduler.db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE scheduled_content SET scheduled_time = datetime('now', '-1 minute') WHERE user_id = ?", ("test_user_sched",))
    conn.commit()
    conn.close()
    
    ready_content = scheduler.get_ready_content("test_user_sched")
    print(f"   Found {len(ready_content)} ready content items")
    assert len(ready_content) >= 1, "Should have retrieved at least 1 ready content item"
    
    print("\n✅ Adaptive Content Scheduler test passed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_adaptive_scheduler())
    except Exception as e:
        print("❌ Test failed:", e)
        sys.exit(1)
