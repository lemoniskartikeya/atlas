"""Completion-probability model: train, evaluate (rolling-origin), explain.

Zero-variance / all-NaN feature columns are dropped before fitting. HistGradientBoosting's
binning requires >= 2 distinct values per feature, and a user with few habits produces
many constant columns; ``kept_indices`` records the surviving columns so inference selects
the same ones.

**Why the evaluation is not a single split.** It used to be one chronological
80/20 cut, which on a personal dataset means scoring against ~50 days holding
~17 non-completions. That is far too little to measure anything: on this
author's own data the 95% bootstrap interval for a single-split AUC ran
[0.436, 0.779] — wide enough to contain both pure chance and the previous
model's score. Moving *only* the cut point, with the data and code unchanged,
swung AUC between 0.552 and 0.703. A retrain looked like a 0.14 regression when
the measurement itself was worth ±0.15.

So the model is scored at several successive cut points and the folds are
averaged, with their spread kept alongside. The number is still noisy — a
personal habit tracker will never have much data — but the spread makes that
visible instead of implying a precision the estimate does not have.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score


@dataclass
class TrainResult:
    model: HistGradientBoostingClassifier
    feature_names: list[str]  # the kept feature names, in model column order
    kept_indices: list[int]  # indices into the full FEATURE_NAMES vector
    metrics: dict
    importances: list[dict]


def _make() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_depth=3,
        max_iter=200,
        learning_rate=0.06,
        l2_regularization=1.0,
        random_state=42,
    )


def _informative_columns(X: np.ndarray) -> list[int]:
    """Columns with at least two distinct non-NaN values."""
    keep: list[int] = []
    for j in range(X.shape[1]):
        col = X[:, j]
        if len(np.unique(col[~np.isnan(col)])) >= 2:
            keep.append(j)
    return keep or list(range(X.shape[1]))


#: Chronological cut points for the rolling-origin evaluation. Each one trains
#: on everything before it and scores everything after, so every fold respects
#: the arrow of time the way a real prediction has to.
_CUT_POINTS = (0.6, 0.7, 0.8, 0.9)


def _score_fold(Xs, ys, split: int) -> Optional[dict]:
    """Train on ``[:split]``, score ``[split:]``. ``None`` if not measurable."""
    y_tr, y_te = ys[:split], ys[split:]
    if len(y_te) < 5 or len(set(y_tr.tolist())) < 2 or len(set(y_te.tolist())) < 2:
        return None
    # Column selection happens inside the fold. Choosing it from the full
    # dataset would let the scored period influence which features the scored
    # model is allowed to see — small, but it is still the test set leaking
    # into training, and everything else in this pipeline is careful about that.
    keep = _informative_columns(Xs[:split])
    model = _make()
    model.fit(Xs[:split][:, keep], y_tr)
    proba = model.predict_proba(Xs[split:][:, keep])[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_te, proba)),
        "accuracy": float(accuracy_score(y_te, pred)),
        "brier": float(brier_score_loss(y_te, proba)),
        "n_test": int(len(y_te)),
        "n_test_neg": int((y_te == 0).sum()),
    }


def _evaluate(Xs, ys) -> dict:
    """Average several chronological folds; keep their spread."""
    n = len(ys)
    folds: list[dict] = []
    skipped: list[str] = []
    for frac in _CUT_POINTS:
        split = max(1, int(n * frac))
        try:
            fold = _score_fold(Xs, ys, split)
        except Exception as exc:  # a fold that won't fit is data, not a crash
            skipped.append(f"{frac:.0%}: {type(exc).__name__}")
            continue
        if fold is None:
            skipped.append(f"{frac:.0%}: too few examples or one-sided outcome")
        else:
            folds.append(fold)

    if not folds:
        # Say why rather than silently omitting the metrics, which reads as a
        # gap in the history chart and looks like a bug.
        return {"eval": "none", "eval_note": "; ".join(skipped) or "no usable folds"}

    aucs = [f["roc_auc"] for f in folds]
    metrics = {
        "eval": "rolling-origin",
        "n_folds": len(folds),
        "roc_auc": round(float(np.mean(aucs)), 3),
        "roc_auc_min": round(float(min(aucs)), 3),
        "roc_auc_max": round(float(max(aucs)), 3),
        "accuracy": round(float(np.mean([f["accuracy"] for f in folds])), 3),
        "brier": round(float(np.mean([f["brier"] for f in folds])), 3),
        # The smallest fold's minority-class count is what actually bounds how
        # much any of this can be trusted.
        "n_test": int(np.mean([f["n_test"] for f in folds])),
        "n_test_neg_min": min(f["n_test_neg"] for f in folds),
    }
    if skipped:
        metrics["eval_note"] = "; ".join(skipped)
    return metrics


def train_model(X: np.ndarray, y: np.ndarray, feature_names: list[str], dates: list) -> TrainResult:
    n = len(y)
    order = np.argsort([d.toordinal() for d in dates])
    Xs, ys = X[order], y[order]

    keep = _informative_columns(Xs)
    kept_names = [feature_names[j] for j in keep]
    Xk = Xs[:, keep]

    metrics: dict = {
        # Named for what it is: the whole corpus. The evaluation's own train and
        # test sizes are per-fold and reported separately.
        "n_examples": int(n),
        "positive_rate": round(float(ys.mean()), 3),
        **_evaluate(Xs, ys),
    }

    final = _make()
    final.fit(Xk, ys)

    importances: list[dict] = []
    try:
        scoring = "roc_auc" if len(set(ys.tolist())) > 1 else "accuracy"
        pi = permutation_importance(final, Xk, ys, n_repeats=5, random_state=42, scoring=scoring)
        importances = sorted(
            (
                {"feature": kept_names[i], "importance": round(float(pi.importances_mean[i]), 4)}
                for i in range(len(kept_names))
            ),
            key=lambda d: d["importance"],
            reverse=True,
        )
    except Exception:  # pragma: no cover - importance is best-effort
        importances = []

    return TrainResult(
        model=final,
        feature_names=kept_names,
        kept_indices=keep,
        metrics=metrics,
        importances=importances,
    )
