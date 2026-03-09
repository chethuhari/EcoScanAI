# Smart Waste Segregation AI

AI-powered waste classification web app with analytics dashboard. Upload waste images, get predictions (Plastic, Paper, Metal, Glass, Organic), and track environmental impact.

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **Backend:** Python Flask
- **Database:** SQLite
- **Charts:** Chart.js

## Setup & Run

1. **Create virtual environment (recommended):**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**
   ```bash
   python app.py
   ```

4. Open **http://127.0.0.1:5000** in your browser.

## Default Login

- **Admin:** `admin@waste.ai` / `admin123`
- Register new users via Sign up.

## Features

- **Login / Signup** — Email auth, redirect after signup to login
- **Dashboard** — Total waste, per-category counts, avg confidence, CO₂ saved, trees saved, pie/line/bar charts
- **Detect Waste** — Upload image, get waste type + confidence, result stored in DB
- **History** — Table of detections with filter by type and delete
- **Analytics** — 60-day trend, confidence, classification frequency, environmental impact
- **Admin** — All detections, delete records, download CSV report, user list, stats

## Project Structure

```
project/
  app.py              # Flask app, API, SQLite
  requirements.txt
  templates/          # login, signup, dashboard, detect, history, analytics, admin
  static/
    css/style.css
    js/script.js
    uploads/          # uploaded images
  models/             # optional: waste_model.h5 for real ML
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/signup | Register |
| POST | /api/login | Login |
| POST | /api/logout | Logout |
| POST | /api/predict | Upload image, get waste type + confidence |
| GET | /api/detections | List detections (optional ?waste_type=) |
| DELETE | /api/detections/<id> | Delete detection |
| GET | /api/analytics | Dashboard/analytics data |
| GET | /api/admin/users | Admin: user list |
| GET | /api/admin/stats | Admin: stats |

Prediction is currently **simulated** (random category + confidence). Replace `predict_waste_type()` in `app.py` with your model inference to use a real ML model.
