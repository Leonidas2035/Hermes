import os
import sys
import json
import time
from pathlib import Path

QUEUE_PATH = Path("/home/layman/QuantumEdge/context/delegated_tasks.json")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 delegate.py <task_description>", file=sys.stderr)
        sys.exit(1)
        
    task_desc = sys.argv[1]
    
    # Load existing queue
    queue = []
    if QUEUE_PATH.exists():
        try:
            with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                queue = json.load(f)
        except Exception:
            queue = []
            
    # Add new task
    task = {
        "id": f"task_{int(time.time())}",
        "timestamp": int(time.time()),
        "status": "PENDING",
        "description": task_desc
    }
    
    queue.append(task)
    
    # Write back
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
        
    print(f"Task successfully delegated to Antigravity (ID: {task['id']}).")
    print("Antigravity will execute the task and reply directly in Telegram.")

if __name__ == "__main__":
    main()
