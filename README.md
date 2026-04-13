# PantryPilot

PantryPilot is a deterministic weekly meal-planning app built with Streamlit. It plans seven days of meals from local recipe data, filters unsafe recipes when allergen data is unknown, limits repetition, and estimates shopping costs from either:

- a built-in mock grocery catalog
- Kroger or Fry's pricing when API credentials are configured

If Kroger credentials are missing, no nearby store is selected, or Kroger pricing requests fail, PantryPilot automatically falls back to mock pricing.

## Phase 2 Submission

Our Phase 2 progress report and technical demonstration can be found here:

[Phase 2 Progress Report](docs/phase2_report.md)

## Requirements

- Python 3.12
- Windows PowerShell (commands below assume Windows)

## Local setup

1. Create and activate a virtual environment.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Kroger or Fry's pricing setup

PantryPilot reads Kroger credentials from environment variables only.

Required environment variables:

- `KROGER_CLIENT_ID`
- `KROGER_CLIENT_SECRET`

Optional environment variable:

- `KROGER_API_SCOPE`
  Default: `product.compact`

Example PowerShell session:

```powershell
$env:KROGER_CLIENT_ID="your-client-id"
$env:KROGER_CLIENT_SECRET="your-client-secret"
$env:KROGER_API_SCOPE="product.compact"
```

If you do not set these variables, the app still works and uses mock grocery pricing.

## Run the app

```powershell
python -m streamlit run mvp/app.py
```

Then open the local Streamlit URL shown in the terminal, usually `http://localhost:8501`.

## Using real store pricing

1. Start the app.
2. In the `Pricing` section, switch to `Real store`.
3. Enter a ZIP code.
4. Choose a nearby Kroger or Fry's store if locations are available.
5. Generate the weekly plan.

When a Kroger product has no usable price or a request fails mid-run, PantryPilot uses mock pricing for the missing item instead of crashing.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Phase 1 and Phase 2 coverage includes:

- allergy filtering
- shopping-list aggregation
- budget compliance
- provider fallback behavior
- missing-price handling

## Kroger API references

PantryPilot's Phase 2 implementation follows Kroger's public API documentation for:

- OAuth2 client credentials
- `/locations` ZIP-code lookup
- `/products` search with `filter.locationId`

Reference links:

- [Kroger Public APIs (Postman)](https://www.postman.com/kroger/the-kroger-co-s-public-workspace/documentation/ki6utqb/kroger-public-apis)
- [Kroger Developers](https://developer.kroger.com/)
