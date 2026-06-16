"""Full reset and re-import of all CSV files with enum discovery."""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from app.services.mongodb_import import import_csv_files_to_mongodb

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client["personal_knowledge_ai"]

# 1. Wipe ALL CSV metadata
result = db["_ingest_metadata"].delete_many({"filepath": {"$regex": "^csv/"}})
print(f"Cleared {result.deleted_count} CSV metadata entries")

# 2. Drop all CSV-backed collections
csv_cols = [
    "attendance_october_2024",
    "payroll_september_2024",
    "crm_customers",
    "sprint_tickets",
    "revenue_2024",
    "recruitment_pipeline",
    "model_registry",
    "infrastructure_costs_sep2024",
]
for col in csv_cols:
    db[col].drop()
    print(f"Dropped: {col}")

# 3. Re-import fresh
print("\nRe-importing...")
res = import_csv_files_to_mongodb(dir_path="raw/local")
print("Result:", res)

# 4. Verify counts + enum values
print("\n=== Document counts ===")
for col in csv_cols:
    print(f"{col}: {db[col].count_documents({})} docs")

print("\n=== Status enum values ===")
for col, fields in {
    "attendance_october_2024": ["status"],
    "payroll_september_2024": ["status"],
    "crm_customers": ["status", "tier"],
    "sprint_tickets": ["status", "priority", "type"],
    "recruitment_pipeline": ["status", "cv_result"],
    "model_registry": ["status", "deployment_env"],
    "infrastructure_costs_sep2024": ["service_category", "environment"],
}.items():
    print(f"  {col}:")
    for f in fields:
        vals = db[col].distinct(f)
        print(f"    {f}: {vals}")
