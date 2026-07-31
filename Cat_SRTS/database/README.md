# CAT_SRTS Database Module

This folder contains the local MongoDB database module for the CAT Smart Rental Tracking System. The existing MongoDB Atlas database is the source of truth, and the exported JSON files in this folder provide a local seed snapshot for future backend development.

## Folder Structure

- `__init__.py`: Marks this folder as a Python package.
- `config.py`: Stores database name, collection names, and MongoDB connection configuration using environment variables.
- `database.py`: Provides reusable `pymongo` client and database helpers.
- `create_database.py`: Creates missing collections, creates indexes, and seeds from local JSON.
- `create_indexes.py`: Creates all required MongoDB indexes.
- `seed.py`: Reads local seed JSON files and inserts only records that do not already exist.
- `export_data.py`: Exports the current Atlas collections into local JSON files.
- `equipment_seed.json`: Exported equipment documents.
- `operators_seed.json`: Exported operator documents.
- `assignments_seed.json`: Exported assignment documents.
- `usage_logs_seed.json`: Exported usage log documents.
- `database_schema.md`: Human-readable schema, index, and relationship documentation.

## Environment Variables

Set either a full URI:

```powershell
$env:MONGODB_URI="mongodb+srv://<username>:<password>@cluster0.oqcnmna.mongodb.net/smart_rental_tracking_system?retryWrites=true&w=majority&appName=Cluster0"
```

Or set the password while using the default username, host, app name, and database name:

```powershell
$env:MONGODB_PASSWORD="<your-atlas-password>"
```

Optional overrides:

```powershell
$env:MONGODB_DATABASE="smart_rental_tracking_system"
$env:MONGODB_USERNAME="madhavan86776_db_user"
$env:MONGODB_HOST="cluster0.oqcnmna.mongodb.net"
$env:MONGODB_APP_NAME="Cluster0"
```

## Export Data

Export the current Atlas data into local seed JSON files:

```powershell
python -m database.export_data
```

## Seed Data

Insert local JSON seed data without duplicating existing records:

```powershell
python -m database.seed
```

## Create Indexes

Create all required indexes:

```powershell
python -m database.create_indexes
```

## Recreate the Database

Create missing collections, apply indexes, and seed records:

```powershell
python -m database.create_database
```

To intentionally drop and rebuild the configured database from local seed files:

```powershell
$env:CONFIRM_RECREATE="true"
python -m database.create_database
```

Use the destructive rebuild option only against an environment where replacing data is expected.

## Future Flask Connection

A future Flask backend can reuse the database helper directly:

```python
from database.database import get_database

db = get_database()
equipment_collection = db["equipment"]
```

Keep Atlas credentials in environment variables or a local secret manager. Do not commit passwords.

