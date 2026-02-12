#!/usr/bin/env python
"""
Manual test script for context compaction feature.

This script:
1. Creates a TaskWeaver session with compaction enabled
2. Sends multiple messages to trigger compaction (threshold=5)
3. Prints compaction-related debug logs

Usage:
    python test_compaction_manual.py

Expected behavior:
    After 5 rounds, compaction should trigger and you'll see:
    - "ContextCompactor: Worker thread started"
    - "ContextCompactor: Compacting rounds 1-X ..."
    - "ContextCompactor: Compaction complete ..."
"""

import logging
import os
import sys
import time

# Set up logging to see DEBUG messages
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# Also capture the taskweaver logger at DEBUG level
taskweaver_logger = logging.getLogger("taskweaver")
taskweaver_logger.setLevel(logging.DEBUG)

# Add a custom filter to highlight compaction messages
class CompactionHighlighter(logging.Filter):
    def filter(self, record):
        if "Compactor" in record.getMessage() or "compaction" in record.getMessage().lower():
            record.msg = f"🔥 COMPACTION: {record.msg}"
        return True

for handler in logging.root.handlers:
    handler.addFilter(CompactionHighlighter())


def main():
    print("=" * 60)
    print("Context Compaction Manual Test")
    print("=" * 60)
    print()
    
    # Import after logging setup
    from taskweaver.app.app import TaskWeaverApp
    
    project_dir = os.path.join(os.path.dirname(__file__), "project")
    
    print(f"Project directory: {project_dir}")
    print()
    
    # Read current config to show compaction settings
    config_path = os.path.join(project_dir, "taskweaver_config.json")
    if os.path.exists(config_path):
        import json
        with open(config_path) as f:
            config = json.load(f)
        print("Current compaction config:")
        for key in ["planner.prompt_compression", "planner.compaction_threshold", 
                    "code_generator.prompt_compression", "code_generator.compaction_threshold"]:
            print(f"  {key}: {config.get(key, 'NOT SET')}")
        print()
    
    # Create app
    print("Creating TaskWeaver app...")
    app = TaskWeaverApp(app_dir=project_dir)
    
    # Create session
    print("Creating session...")
    session = app.get_session()
    print(f"Session ID: {session.session_id}")
    print()
    
    # Check if compactor was created
    if hasattr(session, 'planner') and session.planner.compactor:
        print("✅ Planner compactor is ENABLED")
        print(f"   Threshold: {session.planner.config.compaction_threshold}")
        print(f"   Retain recent: {session.planner.config.compaction_retain_recent}")
    else:
        print("❌ Planner compactor is DISABLED or not found")
        print("   Check planner.prompt_compression in config")
    print()
    
    # Messages to send (need threshold+1 to trigger compaction)
    messages = [
        "What is 2+2?",
        "Now multiply that by 3",
        "Divide the result by 2",
        "Add 10 to that",
        "What's the square root of 16?",
        "Now tell me the final number from step 4",  # This should trigger compaction
        "Summarize all calculations we did",
    ]
    
    threshold = session.planner.config.compaction_threshold if hasattr(session, 'planner') else 5
    print(f"Sending {len(messages)} messages (threshold={threshold})...")
    print("Compaction should trigger after round {threshold}.")
    print()
    print("-" * 60)
    
    for i, msg in enumerate(messages, 1):
        print(f"\n📤 Round {i}: {msg}")
        print("-" * 40)
        
        try:
            result = session.send_message(msg)
            
            # Get the response
            if result.post_list:
                response = result.post_list[-1].message
                print(f"📥 Response: {response[:200]}{'...' if len(response) > 200 else ''}")
            
            # Check compaction status after each round
            if hasattr(session, 'planner') and session.planner.compactor:
                compaction = session.planner.compactor.get_compaction()
                if compaction:
                    print(f"\n🔥 COMPACTION ACTIVE!")
                    print(f"   Compacted rounds: 1-{compaction.end_index}")
                    print(f"   Summary preview: {compaction.summary[:150]}...")
                else:
                    print(f"   (No compaction yet - {i} rounds, need {threshold})")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Small delay to allow background compaction to process
        time.sleep(0.5)
    
    print()
    print("-" * 60)
    print("\n📊 Final Compaction Status:")
    
    if hasattr(session, 'planner') and session.planner.compactor:
        compaction = session.planner.compactor.get_compaction()
        if compaction:
            print(f"✅ Compaction is ACTIVE")
            print(f"   Start index: {compaction.start_index}")
            print(f"   End index: {compaction.end_index}")
            print(f"   Full summary:\n{'-'*40}\n{compaction.summary}\n{'-'*40}")
        else:
            print("❌ No compaction was triggered")
            print("   This might indicate a bug in the compaction logic")
    
    # Cleanup
    print("\nStopping session...")
    session.stop()
    app.stop()
    print("Done!")


if __name__ == "__main__":
    main()
