# CAT_SRTS Backend

This folder contains the Flask backend foundation for the CAT Smart Rental Tracking System.

The current backend only initializes Flask and enables CORS. It does not include business logic, CRUD routes, authentication, or MongoDB integration.

## Folder Structure

- `app.py`: Flask entry point. Run this file with `python app.py`.
- `config/`: Application settings and environment-based configuration.
- `routes/`: Future route registration and API endpoint modules.
- `controllers/`: Future request handlers that coordinate HTTP input and responses.
- `services/`: Future business logic and workflow modules.
- `models/`: Future data models and database access abstractions.
- `utils/`: Future shared helpers and utility functions.
- `requirements.txt`: Python dependencies for the backend.

## Run

```powershell
cd backend
python app.py
```

The app starts on `http://127.0.0.1:5000` by default.

Optional environment variables:

```powershell
$env:FLASK_RUN_HOST="127.0.0.1"
$env:FLASK_RUN_PORT="5000"
$env:FLASK_DEBUG="true"
```

## Current Scope

Implemented:

- Flask application initialization.
- CORS enabled.
- Scalable folder structure for future API development.

Not implemented yet:

- MongoDB connection.
- CRUD endpoints.
- Business logic.
- Authentication.

