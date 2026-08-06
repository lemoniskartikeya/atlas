"""Completion-probability model: train, evaluate (time-based split), explain.

Zero-variance / all-NaN feature columns are dropped before fitting. HistGradientBoosting's
binning requires >= 2 distinct values per feature, and a user with few habits produces
many constant columns; ``kept_indices`` records the surviving columns so inference selects
the same ones.
"""
from __future__ import annotations

from dataclasses import dataclass

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


def train_model(X: np.ndarray, y: np.ndarray, feature_names: list[str], dates: list) -> TrainResult:
    n = len(y)
    order = np.argsort([d.toordinal() for d in dates])
    Xs, ys = X[order], y[order]

    keep = _informative_columns(Xs)
    kept_names = [feature_names[j] for j in keep]
    Xk = Xs[:, keep]

    split = max(1, int(n * 0.8))
    metrics: dict = {"n_train": int(n), "positive_rate": round(float(ys.mean()), 3)}

    # Held-out (chronological) evaluation — best-effort; a constant column inside the
    # split can still trip binning, so guard it and just skip metrics if so.
    try:
        X_tr, X_te = Xk[:split], Xk[split:]
        y_tr, y_te = ys[:split], ys[split:]
        if len(X_te) >= 5 and len(set(y_tr.tolist())) > 1:
            holdout = _make()
            holdout.fit(X_tr, y_tr)
            proba = holdout.predict_proba(X_te)[:, 1]
            pred = (proba >= 0.5).astype(int)
            metrics["accuracy"] = round(float(accuracy_score(y_te, pred)), 3)
            metrics["brier"] = round(float(brier_score_loss(y_te, proba)), 3)
            metrics["n_test"] = int(len(y_te))
            if len(set(y_te.tolist())) > 1:
                metrics["roc_auc"] = round(float(roc_auc_score(y_te, proba)), 3)
    except Exception:  # pragma: no cover - evaluation is best-effort
        pass

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
