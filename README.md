# FitBuddy — AI Fitness Plan Generator

FitBuddy is an AI-powered fitness planning application built using:

- FastAPI
- Jinja2
- SQLite
- SQLAlchemy
- Pydantic
- Google Gemini
- HTML
- CSS
- JavaScript

The application generates a structured 7-day fitness plan,
a nutrition/recovery tip, and can update the plan using user
feedback.

---

# Features

## 1. Workout Generation

Users enter:

- Name
- User ID
- Age
- Weight
- Fitness goal
- Workout intensity

FitBuddy sends the profile to Gemini and receives a structured
7-day workout plan.

---

# 2. Nutrition / Recovery Tip

Gemini generates a concise nutrition or recovery tip based
on the selected fitness goal and intensity.

---

# 3. Feedback

Users can submit feedback such as:

- Add more cardio
- Make the routine easier
- Include another recovery day

FitBuddy sends the original/latest plan and feedback to Gemini
to generate a revised seven-day plan.

---

# 4. Database

SQLite stores:

- User details
- Original workout plan
- Updated workout plan
- Nutrition tip
- Last feedback

---

# 5. Admin Dashboard

Open:

http://127.0.0.1:8000/view-all-users

The dashboard displays stored users and their plans.

---

# Installation

## Step 1

Install Python 3.11 or newer.

---

## Step 2

Open the FitBuddy folder in VS Code.

---

## Step 3

Open the VS Code terminal.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Step 4: Run the Application

Start the local web server:

```powershell
uvicorn app.main:app --reload
```

Open your browser and navigate to:
- **Web App**: http://127.0.0.1:8000/
- **Dashboard**: http://127.0.0.1:8000/view-all-users
- **API Documentation**: http://127.0.0.1:8000/docs