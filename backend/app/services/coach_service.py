"""AI coach.

Two modes, one contract:

* **Local (default, offline).** A deterministic answerer that composes replies
  from the user's own numbers (dashboard + prediction + weekly-review services).
  Always available, never leaves the device — the same privacy stance as the
  rest of Atlas.
* **Claude (opt-in).** When ``ATLAS_ANTHROPIC_API_KEY`` is set *and* the optional
  ``anthropic`` package is installed, the coach can call the Claude API for a
  genuinely conversational reply, grounded in a compact digest of the user's
  data. This sends that digest to Anthropic — so it's opt-in and clearly
  flagged in the UI. Any failure (missing dep, network, refusal) falls back to
  the local answerer, so the coach is never dead.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.coach import CoachMessage
from app.services.dashboard_service import DashboardService
from app.services.habit_service import HabitService
from app.services.prediction_service import PredictionService
from app.services.review_service import WeeklyReviewService

_MAX_TOKENS = 2000


class CoachService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)

    # -------------------------------------------------------------------- status
    def status(self) -> dict:
        ready = self._ai_ready()
        settings = get_settings()
        return {
            "ai_available": ready,
            "provider": "anthropic" if ready else None,
            "model": settings.coach_model if ready else None,
        }

    @staticmethod
    def _ai_ready() -> bool:
        if not get_settings().anthropic_api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return True

    # ----------------------------------------------------------------------- ask
    def ask(
        self,
        messages: list[CoachMessage],
        use_ai: bool = True,
        today: Optional[date] = None,
    ) -> dict:
        today = today or date.today()
        ctx = self._context(today)

        if use_ai and self._ai_ready():
            reply = self._ai_reply(messages, ctx)
            if reply:
                return {
                    "reply": reply,
                    "mode": "ai",
                    "model": get_settings().coach_model,
                    "grounded_on": today.isoformat(),
                }

        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        question = last_user.content if last_user else ""
        return {
            "reply": self._local_reply(question, ctx),
            "mode": "local",
            "model": None,
            "grounded_on": today.isoformat(),
        }

    # ------------------------------------------------------------------- context
    def _context(self, today: date) -> dict:
        return {
            "today": today,
            "dash": DashboardService(self.session).build(today),
            "pred": PredictionService(self.session).build(today),
            "review": WeeklyReviewService(self.session).build(0, today),
            "habits": list(self.habits.list_habits(include_archived=False)),
        }

    # ------------------------------------------------------------------- Claude
    def _ai_reply(self, messages: list[CoachMessage], ctx: dict) -> Optional[str]:
        try:
            import anthropic

            settings = get_settings()
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            api_messages = [
                {"role": m.role, "content": m.content}
                for m in messages
                if m.role in ("user", "assistant") and m.content.strip()
            ]
            if not api_messages or api_messages[0]["role"] != "user":
                api_messages = [
                    {"role": "user", "content": "Give me a short read on how I'm doing and what to focus on."}
                ] + api_messages

            resp = client.messages.create(
                model=settings.coach_model,
                max_tokens=_MAX_TOKENS,
                system=self._system_prompt(ctx),
                messages=api_messages,
            )
            if getattr(resp, "stop_reason", None) == "refusal":
                return None
            text = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
            )
            return text.strip() or None
        except Exception:  # pragma: no cover - network / optional dependency
            return None

    def _system_prompt(self, ctx: dict) -> str:
        return (
            "You are Atlas Coach, a warm, sharp habit and productivity coach built into "
            "the user's personal tracking app. You have their live data below.\n\n"
            "Guidelines:\n"
            "- Be concise and specific. Cite the user's real numbers (streaks, rates, mood, "
            "sleep) and never invent data.\n"
            "- Offer at most two or three concrete, doable suggestions, each with a one-line "
            "reason.\n"
            "- Be encouraging but honest: celebrate wins, name slips plainly.\n"
            "- You are not a doctor or therapist. For health or mental-health concerns, gently "
            "suggest a professional; do not diagnose.\n"
            "- Plain text only: no markdown headers and no internal or system XML tags.\n\n"
            f"USER DATA (as of {ctx['today'].isoformat()}):\n{self._digest_text(ctx)}"
        )

    def _digest_text(self, ctx: dict) -> str:
        d, p, r = ctx["dash"], ctx["pred"], ctx["review"]
        lines: list[str] = []
        lines.append(
            f"Life score {round(d.life_score)}/100; weekly consistency "
            f"{round(d.weekly_consistency * 100)}%."
        )
        lines.append(f"Today: {d.habits_completed} of {d.habits_total} habits done; {d.tasks_open} tasks open.")
        ec = p.expected_completion
        if ec.due:
            lines.append(f"On pace for ~{ec.expected_total:.1f} of {ec.due} due habits today.")
        wb = []
        if d.mood is not None:
            wb.append(f"mood {d.mood}/5")
        if d.energy is not None:
            wb.append(f"energy {d.energy}/5")
        if d.sleep_hours is not None:
            wb.append(f"{d.sleep_hours:g}h sleep")
        if wb:
            lines.append("Latest wellbeing: " + ", ".join(wb) + f"; burnout {p.burnout.level}.")
        if d.top_streaks:
            lines.append("Top streaks: " + ", ".join(f"{s.title} {s.current_streak}d" for s in d.top_streaks[:4]) + ".")
        if p.streak_risks:
            lines.append("At risk today: " + ", ".join(f"{r_.title} (~{round(r_.risk * 100)}%)" for r_ in p.streak_risks[:3]) + ".")
        lines.append("This week: " + r.narrative)
        if r.wins:
            lines.append("Wins: " + ", ".join(w.title for w in r.wins) + ".")
        if r.watchouts:
            lines.append("Watch-outs: " + ", ".join(w.title for w in r.watchouts) + ".")
        if d.recommendations:
            lines.append("Model insights: " + " ".join(rec.title.rstrip(".") + "." for rec in d.recommendations[:2]))
        lines.append("Habits tracked: " + ", ".join(h.title for h in ctx["habits"]) + ".")
        return "\n".join(lines)

    # -------------------------------------------------------------- local answers
    def _local_reply(self, question: str, ctx: dict) -> str:
        q = question.lower().strip()

        # Specific habit by name takes priority over generic intents.
        if q:
            for habit in ctx["habits"]:
                if habit.title.lower() in q:
                    return self._habit_answer(habit, ctx)

        if not q:
            return self._snapshot(ctx)
        if any(w in q for w in ("focus", "should i", "priorit", "what do i do", "next", "get done")):
            return self._focus(ctx)
        if "streak" in q:
            return self._streaks(ctx)
        if any(w in q for w in ("sleep", "energy", "mood", "tired", "burn", "rest", "wellbeing", "well-being")):
            return self._wellbeing(ctx)
        if any(w in q for w in ("week", "review", "recap", "summary", "how did i")):
            return self._review(ctx)
        if any(w in q for w in ("task", "todo", "to-do", "to do")):
            return self._tasks(ctx)
        if any(w in q for w in ("how am i", "doing", "going", "progress", "status", "overall")):
            return self._snapshot(ctx)
        return (
            self._snapshot(ctx)
            + " You can ask me what to focus on, about a specific habit, your streaks, or your wellbeing."
        )

    def _snapshot(self, ctx: dict) -> str:
        d, p = ctx["dash"], ctx["pred"]
        parts = [
            f"You're at {round(d.life_score)}/100 on your life score, with "
            f"{round(d.weekly_consistency * 100)}% weekly consistency."
        ]
        ec = p.expected_completion
        pace = f", on pace for ~{ec.expected_total:.0f} of {ec.due}" if ec.due else ""
        parts.append(f"Today you've done {d.habits_completed} of {d.habits_total} habits{pace}.")
        if d.top_streaks:
            s = d.top_streaks[0]
            parts.append(f"Your strongest streak is {s.title} at {s.current_streak} days.")
        if p.streak_risks:
            r = p.streak_risks[0]
            parts.append(f"Keep an eye on {r.title} — about {round(r.risk * 100)}% chance it slips today.")
        return " ".join(parts)

    def _focus(self, ctx: dict) -> str:
        d, p = ctx["dash"], ctx["pred"]
        parts: list[str] = []
        if p.streak_risks:
            r = p.streak_risks[0]
            parts.append(
                f"First, protect {r.title} — it's most likely to slip today "
                f"(~{round(r.risk * 100)}%), so do it early."
            )
        if d.recommendations:
            parts.append(d.recommendations[0].title.rstrip(".") + ".")
        if d.suggested_task:
            parts.append(f"On tasks, your top open one is “{d.suggested_task.title}”.")
        if not parts:
            parts.append("You're in good shape — nothing urgent. Pick one keystone habit and lock it in.")
        return " ".join(parts)

    def _streaks(self, ctx: dict) -> str:
        d, p = ctx["dash"], ctx["pred"]
        if not d.top_streaks:
            return "No active streaks yet — complete a habit today to start one."
        top = ", ".join(f"{s.title} ({s.current_streak}d)" for s in d.top_streaks[:4])
        out = [f"Active streaks: {top}."]
        if p.streak_risks:
            r = p.streak_risks[0]
            out.append(f"{r.title} is the one at risk today (~{round(r.risk * 100)}%) — front-load it.")
        return " ".join(out)

    def _wellbeing(self, ctx: dict) -> str:
        d, p = ctx["dash"], ctx["pred"]
        bits = []
        if d.mood is not None:
            bits.append(f"mood {d.mood}/5")
        if d.energy is not None:
            bits.append(f"energy {d.energy}/5")
        if d.sleep_hours is not None:
            bits.append(f"{d.sleep_hours:g}h sleep")
        lead = (
            "Latest check-in: " + ", ".join(bits) + "."
            if bits
            else "You haven't journaled recently — log today to track mood, energy, and sleep."
        )
        out = [lead, f"Your burnout signal is {p.burnout.level}."]
        if p.burnout.drivers:
            out.append("Drivers: " + ", ".join(p.burnout.drivers) + ".")
        if p.burnout.level != "low":
            out.append("Protect your sleep and trim today to your top one or two habits.")
        return " ".join(out)

    def _review(self, ctx: dict) -> str:
        r = ctx["review"]
        out = [r.narrative]
        if r.watchouts:
            out.append("Worth protecting: " + ", ".join(w.title for w in r.watchouts) + ".")
        if r.focus:
            out.append("Next week: " + r.focus[0])
        return " ".join(out)

    def _tasks(self, ctx: dict) -> str:
        d = ctx["dash"]
        out = [f"You have {d.tasks_open} open task{'s' if d.tasks_open != 1 else ''}."]
        if d.suggested_task:
            out.append(f"Start with “{d.suggested_task.title}” — your highest-priority one.")
        return " ".join(out)

    def _habit_answer(self, habit, ctx: dict) -> str:
        stats = self.habits.compute_stats(habit, ctx["today"])
        out = [
            f"{habit.title}: a {stats.current_streak}-day streak, "
            f"{round(stats.success_rate * 100)}% all-time and "
            f"{round(stats.consistency_30d * 100)}% over the last 30 days."
        ]
        if stats.best_weekday:
            tail = f" and slip most on {stats.worst_weekday}" if stats.worst_weekday else ""
            out.append(f"You do best on {stats.best_weekday}{tail}.")
        risk = next((r for r in ctx["pred"].streak_risks if r.habit_id == habit.id), None)
        if risk:
            out.append(f"Today it's ~{round(risk.risk * 100)}% likely to slip — worth front-loading.")
        return " ".join(out)
