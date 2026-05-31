# eval.py — run with: python eval.py
# Set TARGET_URL to localhost for local testing, or Cloud Run URL for live testing.

import asyncio
import json
import httpx
from datetime import datetime

TARGET_URL = "http://localhost:8080/ask"
SCORE_MAP = {0: "Wrong/hallucinated/refused incorrectly",
             1: "Mostly right but one issue",
             2: "Correct, clear, no invented numbers"}

async def run_eval():
    with open("eval_questions.json") as f:
        questions = json.load(f)

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n=== EVAL RUN: {run_time} | TARGET: {TARGET_URL} ===\n")

    async with httpx.AsyncClient(timeout=60.0) as client:
        for q in questions:
            print(f"--- Question {q['id']} ---")
            print(f"Q: {q['question']}")
            print(f"Expected: {q['expected']}")

            try:
                resp = await client.post(TARGET_URL, json={"question": q["question"]})
                data = resp.json()
                print(f"Headline: {data.get('headline')}")
                print(f"Has chart: {data.get('chart_data') is not None}")
                print(f"Uncertain: {data.get('uncertainty')}")
                print(f"Clarifying: {data.get('needs_clarification')}")
            except Exception as e:
                print(f"ERROR: {e}")

            while True:
                raw = input("Score (0/1/2): ").strip()
                if raw in ("0", "1", "2"):
                    q["last_score"] = int(raw)
                    break
                print("Enter 0, 1, or 2")
            print()

    total = sum(q["last_score"] for q in questions if q["last_score"] is not None)
    print(f"\n=== TOTAL SCORE: {total}/20 ===")

    if total < 12:
        print("ACTION: Score is below 12. Fix the system prompt before proceeding.")
    elif total < 16:
        print("ACTION: Score is below 16. Do not submit yet — continue prompt tuning.")
    else:
        print("PASS: Score is 16 or above. Ready to proceed.")

    with open("eval_questions.json", "w") as f:
        json.dump(questions, f, indent=2)

    # Append to score history
    with open("eval_history.md", "a") as f:
        f.write(f"| {run_time} | {total}/20 |\n")

asyncio.run(run_eval())
