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
from app.core.logging import get_logger
from app.core.secrets_store import mask
from app.schemas.coach import CoachMessage
from app.services.dashboard_service import DashboardService
from app.services.habit_service import HabitService
from app.services.llm import ChatMessage, LLMError, Provider, get_provider, provider_catalog
from app.services.prediction_service import PredictionService
from app.services.review_service import WeeklyReviewService

log = get_logger("atlas.coach")

_MAX_TOKENS = 2000
#: One token is enough to prove a key works without spending on a real answer.
_TEST_TOKENS = 8
#: Local models on modest hardware are slow; the network providers are not.
_TIMEOUT = 120.0


def _friendly_api_error(exc: Exception) -> str:
    """Turn SDK exceptions into something a Settings panel can show."""
    name = type(exc).__name__
    text = str(exc)
    if "authentication" in name.lower() or "401" in text or "invalid x-api-key" in text.lower():
        return "That key was rejected by Anthropic. Check you copied it in full."
    if "permission" in name.lower() or "403" in text:
        return "That key isn't permitted to use this model."
    if "notfound" in name.lower().replace("_", "") or "404" in text:
        return "Model not found for this key."
    if "ratelimit" in name.lower().replace("_", "") or "429" in text:
        return "Rate limited — the key works, try again in a moment."
    if "connection" in name.lower() or "timeout" in name.lower():
        return "Couldn't reach Anthropic. Check your internet connection."
    return f"{name}: {text[:160]}"


class CoachService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)

    # ------------------------------------------------------------------ provider
    @staticmethod
    def _selected() -> tuple[Provider, Optional[str], str]:
        """The configured provider, its key, and the model to ask for."""
        settings = get_settings()
        provider = get_provider(settings.coach_provider)
        key = settings.coach_key_for(provider.info.id)
        model = (settings.coach_model or "").strip() or provider.info.default_model
        return provider, key, model

    # -------------------------------------------------------------------- status
    def status(self) -> dict:
        provider, key, model = self._selected()
        ready = self._ai_ready()
        return {
            "ai_available": ready,
            "provider": provider.info.id,
            "provider_label": provider.info.label,
            "model": model,
            "local_provider": provider.info.local,
            "needs_key": not provider.info.local,
            "sdk_installed": self._sdk_installed(),
            "has_key": bool(key),
            "key_hint": mask(key),
            "providers": provider_catalog(),
        }

    @staticmethod
    def _sdk_installed() -> bool:
        """Only Anthropic needs a client library; the rest are plain HTTP."""
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return True

    @classmethod
    def _ai_ready(cls) -> bool:
        provider, key, _ = cls._selected()
        if provider.info.local:
            return True  # reachability is proven by asking, not by config
        if provider.info.id == "anthropic" and not cls._sdk_installed():
            return False
        return bool(key)

    def test_key(self) -> dict:
        """Round-trip the smallest possible request so Settings can show a real
        verdict instead of "saved" and a coach that silently stays local."""
        provider, key, model = self._selected()
        if not provider.info.local and not key:
            return {"ok": False, "detail": f"No {provider.info.label} API key saved."}
        try:
            provider.complete(
                system="Reply with the single word: ok",
                messages=[ChatMessage(role="user", content="hi")],
                model=model,
                api_key=key,
                max_tokens=_TEST_TOKENS,
                timeout=_TIMEOUT,
            )
            return {"ok": True, "detail": f"Connected to {model} via {provider.info.label}."}
        except LLMError as exc:
            return {"ok": False, "detail": str(exc)}
        except Exception as exc:  # pragma: no cover - unexpected client failure
            return {"ok": False, "detail": _friendly_api_error(exc)}

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
                    # The resolved model, not the raw setting — that is blank
                    # whenever the provider's own default is in use.
                    "model": self._selected()[2],
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

    # --------------------------------------------------------------- the model
    def _ai_reply(self, messages: list[CoachMessage], ctx: dict) -> Optional[str]:
        """Ask the configured provider. None means "fall back to the local answer".

        Every failure lands here — no key, a rejected key, a provider that is
        down, Ollama not running. The user still gets an answer grounded in
        their own data; the mode badge tells them it came from Atlas itself.
        """
        provider, key, model = self._selected()
        try:
            return provider.complete(
                system=self._system_prompt(ctx),
                messages=[ChatMessage(role=m.role, content=m.content) for m in messages],
                model=model,
                api_key=key,
                max_tokens=_MAX_TOKENS,
                timeout=_TIMEOUT,
            )
        except LLMError as exc:
            log.info("coach.provider_unavailable", extra={"provider": provider.info.id, "error": str(exc)})
            return None
        except Exception as exc:  # pragma: no cover - unexpected client failure
            log.warning("coach.provider_failed", extra={"provider": provider.info.id, "error": str(exc)})
            return None

    def _system_prompt(self, ctx: dict) -> str:
        return (
            "You are Atlas Coach, a warm, sharp assistant built into the user's personal "
            "habit and productivity app. Their live Atlas data is below.\n\n"
            "You are a general-purpose assistant first and a coach second. Answer whatever "
            "the user actually asks — general knowledge, writing, code, explanations, "
            "brainstorming, or open-ended conversation — exactly as a capable assistant "
            "would. Do NOT deflect a general question back to their habits, and do not "
            "force their tracking data into an answer where it isn't relevant.\n\n"
            "When the question IS about them — their habits, streaks, tasks, mood, sleep, "
            "progress, or what to do next — ground the answer in the real numbers below.\n\n"
            "Guidelines:\n"
            "- Be concise and specific. Never invent Atlas data: if a number isn't below, "
            "say you don't have it.\n"
            "- For coaching answers, offer at most two or three concrete suggestions, each "
            "with a one-line reason.\n"
            "- Be encouraging but honest: celebrate wins, name slips plainly.\n"
            "- You are not a doctor or therapist. For health or mental-health concerns, "
            "gently suggest a professional; do not diagnose.\n"
            "- Plain text only: no markdown headers and no internal or system XML tags.\n\n"
            f"USER'S ATLAS DATA (as of {ctx['today'].isoformat()}):\n{self._digest_text(ctx)}"
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

        # Anything else is a general question. Answering it needs a real model —
        # so say that plainly instead of replying with an unrelated stats dump,
        # which is what makes an offline assistant feel broken.
        return (
            "I can't answer that one offline — the local coach only knows your Atlas data, "
            "so it handles questions about your habits, streaks, tasks, focus, wellbeing, "
            "and weekly review.\n\n"
            "To ask me anything else, add an Anthropic API key in Settings → AI Coach. "
            "That switches the coach to Claude, which answers general questions too and "
            "still sees your Atlas numbers.\n\n"
            + self._snapshot(ctx)
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
