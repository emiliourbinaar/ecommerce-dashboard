# Power BI Setup Guide

## Recommended Workflow

### Step 1 — Run the Python pipeline

```bash
python main.py
```

This generates all 12 CSV files in `data/powerbi/`.

### Step 2 — Open Power BI Desktop

Create a new blank report. Do **not** use the PBIP project files to open a report — the PBIP/SemanticModel folder is a TMDL reference only, not a pre-built report.

### Step 3 — Import each CSV

Home → Get Data → Text/CSV → import from `data/powerbi/`:

| File | Type |
|------|------|
| `fact_orders.csv` | Fact table |
| `dim_customers.csv` | Dimension |
| `dim_products.csv` | Dimension |
| `dim_date.csv` | Date dimension |
| `weekly_kpis.csv` | Weekly aggregates |
| `campaign_performance.csv` | Campaign aggregates |
| `sales_channel_performance.csv` | Channel aggregates |
| `segment_performance.csv` | Segment aggregates |
| `sales_forecast.csv` | ML forecast (use `is_future` to filter actual vs forecast) |
| `customer_churn_risk.csv` | ML churn scores |
| `product_demand_predictions.csv` | ML demand trends |
| `model_performance.csv` | Model metrics (long format) |

### Step 4 — Disable Auto Date/Time

File → Options and settings → Options → **Current File** → Data Load → uncheck **"Auto date/time"**.

This prevents Power BI from splitting `week_start` and `order_date` into Year/Quarter/Month/Day hierarchies, which breaks date-based charts.

### Step 5 — Create relationships (Model view)

```
fact_orders[customer_id]          → dim_customers[customer_id]    Many-to-One
fact_orders[product_id]           → dim_products[product_id]      Many-to-One
fact_orders[order_date]           → dim_date[date]                Many-to-One
customer_churn_risk[customer_id]  → dim_customers[customer_id]    Many-to-One
```

### Step 6 — Create DAX measures

See `reports/powerbi_page_plan.md` for all measures, copy-paste ready.

### Step 7 — Build visuals page by page

See `reports/powerbi_page_plan.md` for the 5-page layout plan.

---

## About the SemanticModel TMDL folder

`EcommercePerformanceDashboard.SemanticModel/` is a **reference artifact** containing:
- Table schema definitions (column names, data types)
- DAX measure definitions
- Relationship definitions
- The `DataFolderPath` parameter

It is useful if you want to use Power BI's TMDL import feature or the Power BI Modeling MCP server.
It is **not** a working .pbip project — do not open it directly in Power BI Desktop.

### Configuring DataFolderPath

If you use the TMDL model, update `definition/expressions.tmdl`:

```
expression DataFolderPath = "C:\\your\\path\\to\\data\\powerbi\\" meta [...]
```

Use double backslashes and include a trailing backslash.
