"""ML service: orchestrates training, status, and today's explainable predictions.

Heavy imports (numpy/sklearn/joblib via app.learning.*) live here, so this module is
only imported when the optional ML router loads.
"""
from __future__ import annotations

from datetime import date
from math import isnan
from typing import Optional

from sqlalchemy.orm import Session

from app.learning import features, registry, simulate
from app.learning.model import train_model

MIN_SAMPLES = 40


def _clause(feature: str, v: float) -> Optional[str]:
    if v is None or (isinstance(v, float) and isnan(v)):
        return None
    if feature == "rate_7":
        return f"recent 7-day rate {v * 100:.0f}%"
    if feature == "rate_30":
        return f"30-day rate {v * 100:.0f}%"
    if feature == "streak_in":
        return f"a {int(v)}-day streak" if v > 0 else "no active streak"
    if feature == "done_prev":
        return "you did it last time" if v >= 0.5 else "you missed it last time"
    if feature == "is_weekend":
        return "it's the weekend" if v >= 0.5 else "it's a weekday"
    if feature == "days_since_last":
        return f"{int(v)}d since last done"
    if feature == "sleep_prev":
        return f"prior sleep {v:.1f}h"
    if feature == "mood_prev":
        return f"prior mood {v:.0f}/5"
    if feature == "energy_prev":
        return f"prior energy {v:.0f}/5"
    return None


def _explain(vec, top_features: list[str]) -> str:
    idx = {name: i for i, name in enumerate(features.FEATURE_NAMES)}
    clauses: list[str] = []
    for f in top_features:
        if f in idx:
            c = _clause(f, float(vec[idx[f]]))
            if c:
                clauses.append(c)
        if len(clauses) >= 3:
            break
    if not clauses:
        return "Based on your overall pattern."
    return "Weighed most by " + ", ".join(clauses) + "."


class MLService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def status(self) -> dict:
        meta = registry.latest_meta()
        if not meta:
            return {"trained": False}
        return {
            "trained": True,
            "version": meta["version"],
            "trained_at": meta["trained_at"],
            "model_type": meta.get("model_type"),
            "metrics": meta.get("metrics", {}),
        }

    def train(self) -> dict:
        X, y, dates = features.build_training(self.session)
        n = int(len(y))
        if n < MIN_SAMPLES or len(set(y.tolist())) < 2:
            return {
                "trained": False,
                "n_samples": n,
                "reason": (
                    f"Need at least {MIN_SAMPLES} settled examples across both outcomes "
                    f"to train (have {n})."
                ),
            }
        result = train_model(X, y, features.FEATURE_NAMES, dates)
        # Stamp the corpus size onto the saved metrics: the retrain job uses it
        # to tell how much new evidence has arrived since, and the model-history
        # chart uses it to show quality against data volume.
        metrics = {**result.metrics, "n_rows": self._log_count(), "n_samples": n}
        meta = registry.save(
            result.model,
            result.feature_names,
            result.kept_indices,
            metrics,
            result.importances,
        )
        return {"trained": True, "version": meta["version"], "metrics": metrics, "n_samples": n}

    def _log_count(self) -> int:
        """Total habit-log rows — the corpus the next retrain is measured against."""
        from sqlalchemy import func, select

        from app.models.habit import HabitLog

        return int(self.session.scalar(select(func.count()).select_from(HabitLog)) or 0)

    def predict_today(self, today: Optional[date] = None) -> dict:
        bundle = registry.latest_bundle()
        if not bundle:
            return {"trained": False, "predictions": []}
        model = bundle["model"]
        kept = bundle.get("kept_indices")
        top_features = [imp["feature"] for imp in bundle.get("importances", [])[:6]]

        predictions = []
        for habit, vec, done in features.build_inference(self.session, today):
            model_vec = vec[kept] if kept is not None else vec
            proba = float(model.predict_proba(model_vec.reshape(1, -1))[0, 1])
            predictions.append(
                {
                    "habit_id": habit.id,
                    "title": habit.title,
                    "color": habit.color,
                    "probability": round(proba, 3),
                    "done_today": done,
                    "explanation": _explain(vec, top_features),
                }
            )
        predictions.sort(key=lambda p: p["probability"])  # riskiest first

        metrics = bundle.get("metrics", {})
        reliability = metrics.get("roc_auc")
        if reliability is None:
            reliability = metrics.get("accuracy")
        return {
            "trained": True,
            "version": bundle["version"],
            "model_type": type(model).__name__,
            "reliability": reliability,
            "metrics": metrics,
            "predictions": predictions,
        }

    def simulate(self, overrides: dict, today: Optional[date] = None) -> dict:
        """Counterfactual: re-score today's due habits under a what-if scenario.

        Returns baseline vs. simulated completion probability per habit, the
        change in expected completions, and human-readable levers. Out-of-model
        levers (features the model dropped as uninformative) simply show no
        effect — which is itself honest.
        """
        bundle = registry.latest_bundle()
        if not bundle:
            return {"available": False}
        model = bundle["model"]
        kept = bundle.get("kept_indices")

        def prob(vec) -> float:
            model_vec = vec[kept] if kept is not None else vec
            return float(model.predict_proba(model_vec.reshape(1, -1))[0, 1])

        rows_in = features.build_inference(self.session, today)
        metrics = bundle.get("metrics", {})
        reliability = metrics.get("roc_auc") or metrics.get("accuracy")
        if not rows_in:
            return {
                "available": True,
                "reliability": reliability,
                "due": 0,
                "rows": [],
                "levers": simulate.describe_levers(overrides, {}),
                "summary": "Nothing due today to simulate.",
            }

        baseline_ctx = simulate.baseline_wellbeing(rows_in[0][1])
        drop = set(overrides.get("drop_habit_ids") or [])
        scope = overrides.get("habit_id")

        rows: list[dict] = []
        base_expected = sim_expected = 0.0
        for habit, vec, done in rows_in:
            if habit.id in drop:
                continue
            base = prob(vec)
            if scope and habit.id != scope:
                sim = base  # scenario scoped to another habit — leave this one flat
            else:
                sim = prob(simulate.apply_overrides(vec, overrides))
            if not done:
                base_expected += base
                sim_expected += sim
            rows.append(
                {
                    "habit_id": habit.id,
                    "title": habit.title,
                    "color": habit.color,
                    "done_today": done,
                    "baseline": round(base, 3),
                    "simulated": round(sim, 3),
                    "delta": round(sim - base, 3),
                }
            )

        rows.sort(key=lambda r: r["delta"], reverse=True)
        levers = simulate.describe_levers(overrides, baseline_ctx)
        delta_expected = sim_expected - base_expected

        return {
            "available": True,
            "reliability": reliability,
            "due": len(rows),
            "baseline_expected": round(base_expected, 2),
            "simulated_expected": round(sim_expected, 2),
            "delta_expected": round(delta_expected, 2),
            "levers": levers,
            "summary": self._sim_summary(levers, base_expected, sim_expected, rows),
            "rows": rows,
        }

    @staticmethod
    def _sim_summary(
        levers: list[str], base_expected: float, sim_expected: float, rows: list[dict]
    ) -> str:
        if not levers:
            return "Adjust a lever to see the impact on today's completions."
        delta = sim_expected - base_expected
        if delta > 0.05:
            verb = "lifts"
        elif delta < -0.05:
            verb = "lowers"
        else:
            verb = "barely changes"
        sign = "+" if delta >= 0 else ""
        summary = (
            f"This {verb} expected completions from {base_expected:.1f} to "
            f"{sim_expected:.1f} ({sign}{delta:.1f})."
        )
        movers = [r for r in rows if not r["done_today"] and abs(r["delta"]) >= 0.01]
        if movers:
            top = max(movers, key=lambda r: abs(r["delta"]))
            tsign = "+" if top["delta"] >= 0 else ""
            summary += f" Biggest change: {top['title']} {tsign}{round(top['delta'] * 100)}%."
        return summary
