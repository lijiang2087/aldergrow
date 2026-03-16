"""Agent brain: load mission, run one task with LLM (or scheduled daemon)."""

import argparse
import time
from pathlib import Path

from agent import config
from agent import llm
from agent import tools as agent_tools

DEFAULT_DAEMON_TASK = (
    "Review your mission and today's log. Decide what to do next and do it. Log to daily notes."
)


def run_one_cycle(task: str | None = None) -> str:
    """Load mission + today's notes, run one agent cycle. Returns the reply text."""
    mission_path = config.LIFE_ROOT / "identity" / "mission.md"
    if mission_path.exists():
        mission = mission_path.read_text(encoding="utf-8")
    else:
        mission = "You are Alder, an autonomous AI agent. You have no mission file yet."

    task = (task or "").strip() or "Read your mission and introduce yourself in one short paragraph."
    today_notes = agent_tools.read_today_notes()
    if today_notes.strip():
        user_message = f"Today's log so far:\n\n{today_notes}\n\n---\n\nTask: {task}"
    else:
        user_message = task

    # When the task mentions Twitter/X, put post_to_x first so the model reliably sees it (some APIs truncate the tool list).
    tool_definitions = list(agent_tools.TOOL_DEFINITIONS)
    task_lower = task.lower()
    if any(kw in task_lower for kw in ("twitter", "tweet", " post to x", "post to x", " x ", "on x,")):
        post_to_x_def = next((t for t in tool_definitions if t["name"] == "post_to_x"), None)
        if post_to_x_def:
            tool_definitions = [t for t in tool_definitions if t["name"] != "post_to_x"]
            tool_definitions.insert(0, post_to_x_def)

    reply = llm.complete_with_tools(
        system=mission,
        user=user_message,
        tool_definitions=tool_definitions,
        run_tool=agent_tools.run_tool,
        max_rounds=20,
    )
    return reply


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Alder agent")
    parser.add_argument("--task", type=str, default="", help="Task for the agent (e.g. read mission and introduce yourself)")
    parser.add_argument("--daemon", action="store_true", help="Run on a schedule: 7 AM daily + every 4 hours")
    args = parser.parse_args()

    if not args.daemon:
        reply = run_one_cycle(args.task)
        print(reply)
        return

    # Daemon: schedule 7 AM and every 4 hours
    import schedule
    from datetime import datetime

    def scheduled_cycle() -> None:
        try:
            run_one_cycle(DEFAULT_DAEMON_TASK)
            agent_tools.write_daily_note(f"Cycle completed at {datetime.now().isoformat()}.")
        except Exception as e:
            agent_tools.write_daily_note(f"Cycle failed at {datetime.now().isoformat()}: {e}")

    schedule.every().day.at("07:00").do(scheduled_cycle)
    schedule.every(4).hours.do(scheduled_cycle)
    print("Daemon running: 7 AM daily + every 4 hours. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
