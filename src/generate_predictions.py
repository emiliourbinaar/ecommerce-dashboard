"""
Loads trained models and generates the three prediction tables for Power BI:
  - sales_forecast.csv      (actuals + 4-week forward forecast, with is_future flag)
  - customer_churn_risk.csv
  - product_demand_predictions.csv
  - model_performance.csv   (long format: one row per model x metric)
"""
import pickle
import warnings
import numpy as np
import pandas as pd
from src.config import DATA_PROCESSED, DATA_POWERBI, FORECAST_HORIZON

warnings.filterwarnings("ignore")

MODELS_DIR = DATA_PROCESSED / "models"


def _load(name: str) -> dict:
    with open(MODELS_DIR / name, "rb") as f:
        return pickle.load(f)


# ── A: Sales Forecast ─────────────────────────────────────────────────────────

def generate_sales_forecast() -> pd.DataFrame:
    bundle = _load("sales_forecast.pkl")
    model, feature_cols = bundle["model"], bundle["features"]
    wk = bundle["weekly_df"].copy()
    model_name = bundle["name"]

    wk["predicted_revenue"] = model.predict(wk[feature_cols]).clip(0)
    wk["prediction_error"]  = (wk["revenue"] - wk["predicted_revenue"]).round(2)
    wk["model_name"]        = model_name

    in_sample = wk[["week_start", "revenue", "predicted_revenue",
                     "prediction_error", "model_name"]].copy()
    in_sample.rename(columns={"revenue": "actual_revenue"}, inplace=True)
    in_sample["is_future"] = False

    last_row = wk.iloc[-1].copy()
    future_rows = []
    for h in range(1, FORECAST_HORIZON + 1):
        row = last_row.copy()
        row["t"]         += h
        row["week_start"] = last_row["week_start"] + pd.Timedelta(weeks=h)
        row["week_num"]   = row["week_start"].isocalendar()[1]
        row["month"]      = row["week_start"].month
        row["quarter"]    = row["week_start"].quarter
        row["revenue_lag1"] = last_row["revenue"]
        row["revenue_lag2"] = wk.iloc[-2]["revenue"] if len(wk) > 1 else last_row["revenue"]
        row["revenue_lag4"] = wk.iloc[-4]["revenue"] if len(wk) > 3 else last_row["revenue"]
        row["revenue_roll4"]= wk["revenue"].iloc[-4:].mean()
        pred = float(model.predict(row[feature_cols].values.reshape(1, -1)).clip(0))
        future_rows.append({
            "week_start":        row["week_start"],
            "actual_revenue":    None,
            "predicted_revenue": round(pred, 2),
            "prediction_error":  None,
            "model_name":        model_name,
            "is_future":         True,
        })

    future_df = pd.DataFrame(future_rows)
    result = pd.concat([in_sample, future_df], ignore_index=True)
    result["week_start"] = pd.to_datetime(result["week_start"]).dt.date
    return result


# ── B: Customer Churn Risk ─────────────────────────────────────────────────────

def generate_churn_predictions() -> pd.DataFrame:
    bundle = _load("churn_model.pkl")
    model, feature_cols = bundle["model"], bundle["features"]
    cust = bundle["customer_df"].copy()

    proba = model.predict_proba(cust[feature_cols])[:, 1]
    cust["churn_risk_probability"] = proba.round(4)
    cust["risk_level"] = pd.cut(
        cust["churn_risk_probability"],
        bins=[-0.01, 0.33, 0.66, 1.01],
        labels=["Low", "Medium", "High"],
    )

    result = cust[[
        "customer_id", "customer_segment",
        "days_since_last_purchase", "total_revenue",
        "purchase_frequency", "avg_order_value",
        "churn_risk_probability", "risk_level",
    ]].copy()
    result["total_revenue"]   = result["total_revenue"].round(2)
    result["avg_order_value"] = result["avg_order_value"].round(2)
    return result.sort_values("churn_risk_probability", ascending=False)


# ── C: Product Demand Predictions ─────────────────────────────────────────────

def generate_demand_predictions() -> pd.DataFrame:
    bundle = _load("demand_model.pkl")
    model, feature_cols = bundle["model"], bundle["features"]
    cat_wk = bundle["cat_wk_df"].copy()

    cat_wk["predicted_units"] = model.predict(cat_wk[feature_cols]).clip(0).round(0)

    recent = cat_wk.groupby("product_category").apply(
        lambda g: g.sort_values("week_start").tail(4)["units"].mean()
    )
    prior = cat_wk.groupby("product_category").apply(
        lambda g: g.sort_values("week_start").iloc[-8:-4]["units"].mean()
        if len(g) >= 8 else g["units"].mean()
    )
    trend_df = pd.DataFrame({"recent": recent, "prior": prior})
    trend_df["ratio"] = trend_df["recent"] / trend_df["prior"].replace(0, np.nan)
    trend_df["demand_trend"] = trend_df["ratio"].apply(
        lambda r: "Increasing" if r > 1.05 else ("Decreasing" if r < 0.95 else "Stable")
    )

    cat_wk = cat_wk.merge(
        trend_df[["demand_trend"]].reset_index().rename(
            columns={"index": "product_category"}),
        on="product_category", how="left",
    )

    result = cat_wk[[
        "product_category", "week_start", "units", "predicted_units", "demand_trend",
    ]].copy()
    result.rename(columns={"units": "actual_units_sold",
                            "week_start": "week"}, inplace=True)
    result["week"] = pd.to_datetime(result["week"]).dt.date
    result["predicted_units_sold"] = result["predicted_units"].astype(int)
    result.drop(columns=["predicted_units"], inplace=True)
    return result.sort_values(["product_category", "week"])


# ── Model Performance (long format) ───────────────────────────────────────────

def build_model_performance_table(df_orders: pd.DataFrame) -> pd.DataFrame:
    """Re-evaluate all models; returns long format: one row per model x metric."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    rows = []

    def _add(model, algorithm, target, metric_type, metric_name, metric_value):
        rows.append({
            "model":        model,
            "algorithm":    algorithm,
            "target":       target,
            "metric_type":  metric_type,
            "metric_name":  metric_name,
            "metric_value": round(float(metric_value), 4) if metric_value is not None else None,
        })

    # Sales Forecast
    try:
        bundle = _load("sales_forecast.pkl")
        wk = bundle["weekly_df"]
        preds = bundle["model"].predict(wk[bundle["features"]])
        y = wk["revenue"]
        mae  = mean_absolute_error(y, preds)
        rmse = np.sqrt(mean_squared_error(y, preds))
        mape = np.mean(np.abs((y.values - preds) / y.values.clip(1))) * 100
        for name, val in [("MAE", mae), ("RMSE", rmse), ("MAPE_pct", mape)]:
            _add("Sales Forecast", bundle["name"], "weekly_revenue", "Regression", name, val)
    except Exception:
        pass

    # Customer Churn Risk
    try:
        from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
        bundle = _load("churn_model.pkl")
        cust  = bundle["customer_df"]
        proba = bundle["model"].predict_proba(cust[bundle["features"]])[:, 1]
        preds = (proba >= 0.5).astype(int)
        y     = cust["is_churned"].astype(int)
        for name, val in [
            ("Accuracy", accuracy_score(y, preds)),
            ("F1",       f1_score(y, preds, zero_division=0)),
            ("ROC_AUC",  roc_auc_score(y, proba)),
        ]:
            _add("Customer Churn Risk", bundle["name"], "is_churned", "Classification", name, val)
    except Exception:
        pass

    # Product Demand
    try:
        bundle = _load("demand_model.pkl")
        cat_wk = bundle["cat_wk_df"]
        preds  = bundle["model"].predict(cat_wk[bundle["features"]])
        y      = cat_wk["units"]
        mae  = mean_absolute_error(y, preds)
        rmse = np.sqrt(mean_squared_error(y, preds))
        for name, val in [("MAE", mae), ("RMSE", rmse)]:
            _add("Product Demand", bundle["name"], "weekly_units_by_category", "Regression", name, val)
    except Exception:
        pass

    return pd.DataFrame(rows)


def run() -> None:
    DATA_POWERBI.mkdir(parents=True, exist_ok=True)
    df_orders = pd.read_parquet(DATA_PROCESSED / "orders_features.parquet")

    tables = {
        "sales_forecast":             generate_sales_forecast,
        "customer_churn_risk":        generate_churn_predictions,
        "product_demand_predictions": generate_demand_predictions,
    }
    for name, fn in tables.items():
        tbl = fn()
        tbl.to_csv(DATA_POWERBI / f"{name}.csv", index=False)
        print(f"  Saved: data/powerbi/{name}.csv  ({len(tbl):,} rows)")

    perf = build_model_performance_table(df_orders)
    perf.to_csv(DATA_POWERBI / "model_performance.csv", index=False)
    print(f"  Saved: data/powerbi/model_performance.csv  ({len(perf)} rows)")


if __name__ == "__main__":
    run()
