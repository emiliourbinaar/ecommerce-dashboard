# Power BI Dashboard Plan
### Digital Commerce Performance Dashboard

> **How to build this dashboard**
> 1. Run `python main.py` to generate all CSVs in `data/powerbi/`
> 2. Open Power BI Desktop → new blank report
> 3. Import all 12 CSV files from `data/powerbi/`
> 4. Create relationships manually in Model view (see Section 2)
> 5. Create DAX measures (see Section 3)
> 6. Build visuals page by page (see Section 4)
>
> Do **not** try to open the PBIP files in `powerbi/` as a report — the SemanticModel folder
> is a schema reference only. Build your report directly from the CSV imports.

---

## 1. Tables to Import

| File | Type | Key column(s) |
|------|------|---------------|
| `fact_orders.csv` | Fact | `order_id` |
| `dim_customers.csv` | Dimension | `customer_id` |
| `dim_products.csv` | Dimension | `product_id` |
| `dim_date.csv` | Date dimension | `date` |
| `weekly_kpis.csv` | Weekly aggregate | `week_start` |
| `campaign_performance.csv` | Aggregate | `campaign_name` |
| `sales_channel_performance.csv` | Aggregate | `sales_channel` |
| `segment_performance.csv` | Aggregate | `customer_segment` |
| `sales_forecast.csv` | ML output | `week_start` — filter on `is_future` |
| `customer_churn_risk.csv` | ML output | `customer_id` |
| `product_demand_predictions.csv` | ML output | `(product_category, week)` |
| `model_performance.csv` | ML metadata | `(model, metric_name)` — long format |

---

## 2. Relationships to Create in Model View

```
fact_orders[customer_id]         → dim_customers[customer_id]   Many-to-One  *
fact_orders[product_id]          → dim_products[product_id]     Many-to-One  *
fact_orders[order_date]          → dim_date[date]               Many-to-One
customer_churn_risk[customer_id] → dim_customers[customer_id]   Many-to-One
```

`*` = active relationship (cross-filter direction: Single)

The aggregate tables (`weekly_kpis`, `campaign_performance`, `sales_channel_performance`,
`segment_performance`, `sales_forecast`, `product_demand_predictions`, `model_performance`)
are standalone — connect them only if you need a slicer to filter across tables.

---

## 3. DAX Measures

Create these in a dedicated hidden table (New Table → `_Measures`, set IsHidden = true).

### Revenue

```dax
Total Revenue =
CALCULATE(SUM(fact_orders[revenue]), fact_orders[is_completed] = TRUE())

Gross Margin =
CALCULATE(SUM(fact_orders[margin]), fact_orders[is_completed] = TRUE())

Gross Margin % =
DIVIDE([Gross Margin], [Total Revenue], 0)

Average Order Value =
DIVIDE([Total Revenue], [Total Orders], 0)
```

### Orders & Units

```dax
Total Orders =
CALCULATE(COUNTROWS(fact_orders), fact_orders[is_completed] = TRUE())

Units Sold =
CALCULATE(SUM(fact_orders[quantity]), fact_orders[is_completed] = TRUE())
```

### Customers

```dax
Active Customers =
CALCULATE(DISTINCTCOUNT(fact_orders[customer_id]), fact_orders[is_completed] = TRUE())

New Customers = SUM(weekly_kpis[new_customers])

Repeat Customers =
CALCULATE(
    COUNTROWS(dim_customers),
    dim_customers[purchase_frequency] >= 2
)

Repeat Customer Rate = DIVIDE([Repeat Customers], [Active Customers], 0)
```

### Funnel

```dax
Conversion Rate =
DIVIDE(
    CALCULATE(SUM(fact_orders[completed_orders])),
    CALCULATE(SUM(fact_orders[visits])),
    0
)

Cart Abandonment Rate =
1 - DIVIDE(
    CALCULATE(SUM(fact_orders[completed_orders])),
    CALCULATE(SUM(fact_orders[cart_additions])),
    0
)
```

### Week-over-Week Growth

> These measures read the pre-calculated `revenue_wow_growth` and `orders_wow_growth` columns
> from `weekly_kpis` (computed in Python). This avoids date arithmetic that Power BI cannot
> resolve reliably against stored week-start dates.

```dax
WoW Revenue Growth =
LASTNONBLANKVALUE(weekly_kpis[week_start], AVERAGE(weekly_kpis[revenue_wow_growth]))

WoW Orders Growth =
LASTNONBLANKVALUE(weekly_kpis[week_start], AVERAGE(weekly_kpis[orders_wow_growth]))
```

### Predictions

```dax
Predicted Revenue =
CALCULATE(
    SUM(sales_forecast[predicted_revenue]),
    sales_forecast[is_future] = TRUE()
)

Forecast Error % =
DIVIDE(
    ABS(SUM(sales_forecast[prediction_error])),
    SUM(sales_forecast[actual_revenue]),
    0
)

High Risk Customers =
CALCULATE(COUNTROWS(customer_churn_risk), customer_churn_risk[risk_level] = "High")

Churn Risk Rate =
DIVIDE(
    CALCULATE(COUNTROWS(customer_churn_risk), customer_churn_risk[risk_level] = "High"),
    CALCULATE(COUNTROWS(customer_churn_risk), ALL(customer_churn_risk[risk_level])),
    0
)

Increasing Demand Categories =
CALCULATE(
    DISTINCTCOUNT(product_demand_predictions[product_category]),
    product_demand_predictions[demand_trend] = "Increasing"
)
```

---

## 4. Dashboard Pages (5 pages)

### Page 1 — Executive Overview
**Purpose:** Single-glance KPI summary for leadership

Visuals:
- 4 KPI cards: Total Revenue, Total Orders, Active Customers, Gross Margin %
- Line chart: Total Revenue by week_start (from weekly_kpis)
- Bar chart: Revenue by customer_segment (from segment_performance)
- Bar chart: Revenue by sales_channel (from sales_channel_performance)
- Slicer: year (from dim_date)

---

### Page 2 — Weekly KPI Tracking
**Purpose:** Week-over-week trend monitoring

Visuals:
- Line chart: Total Revenue + WoW Revenue Growth over time (weekly_kpis)
- Line chart: Total Orders + WoW Orders Growth over time
- Column chart: New Customers vs Repeat Customers by week
- KPI cards: Conversion Rate, Cart Abandonment Rate, Avg Discount
- Slicer: Date range (week_start from weekly_kpis)

---

### Page 3 — Product & Category Analysis
**Purpose:** Product mix, category trends, demand signals

Visuals:
- Bar chart: Revenue by product_category (fact_orders)
- Table: Top 20 products by revenue (dim_products + fact_orders)
- Line chart: Actual vs Predicted units by category (product_demand_predictions)
- Color-coded table: demand_trend by product_category (Increasing/Stable/Decreasing)
- Slicer: product_category

---

### Page 4 — Customer & Segment Analysis
**Purpose:** Customer health, segment profitability, churn risk

Visuals:
- Donut chart: Revenue share by customer_segment (segment_performance)
- Table: Segment metrics — revenue, orders, avg order value, repeat rate (segment_performance)
- Bar chart: Churn risk distribution by risk_level (customer_churn_risk)
- Scatter plot: churn_risk_probability vs total_revenue per customer (customer_churn_risk)
- KPI cards: High Risk Customers, Churn Risk Rate, Repeat Customer Rate
- Slicer: customer_segment, risk_level

---

### Page 5 — Predictive Insights
**Purpose:** Sales forecast, forward outlook

Visuals:
- Line chart: actual_revenue vs predicted_revenue over time (sales_forecast)
  - Filter `is_future = FALSE` for actuals line
  - Show both actuals and forecast together, use color to distinguish
- Column chart: Forecast for next 4 weeks (is_future = TRUE)
- KPI cards: Predicted Revenue (next 4 weeks), Forecast Error %
- Bar chart: Demand trend by category (product_demand_predictions — latest week)
- Slicer: model_name (sales_forecast)

---

### Page 6 — Model Performance *(optional)*
**Purpose:** ML model accuracy for technical/data stakeholders. Skip this page for a business-facing dashboard; the `model_performance.csv` data is still available if needed.

Visuals:
- Matrix or table: model_performance filtered by metric_type = "Regression"
  - Rows: model, Columns: metric_name, Values: metric_value
- Matrix: model_performance filtered by metric_type = "Classification"
- KPI cards: Best model MAE, Best F1, Best ROC_AUC
- Text box explaining what each metric means

---

## 5. Slicers to Add (report-level)

Add these as sync'd slicers across multiple pages:
- **Year** — dim_date[year]
- **Quarter** — dim_date[quarter]
- **Customer Segment** — dim_customers[customer_segment]
- **Sales Channel** — fact_orders[sales_channel]

---

## 6. Color Theme

| Color | Use |
|-------|-----|
| `#1E8449` Dark green | Primary brand, positive trends |
| `#2980B9` Blue | Revenue, orders |
| `#8E44AD` Purple | Predictions, ML |
| `#C0392B` Red | Churn, negative trends |
| `#E67E22` Orange | Warnings, medium risk |
| `#F39C12` Amber | Growth metrics |

---

> **Warning:** Do not use the `powerbi/EcommercePerformanceDashboard.SemanticModel/` TMDL
> folder as a substitute for this workflow. That folder is a schema reference artifact.
> Build your report from scratch in Power BI Desktop using the CSV imports described above.
