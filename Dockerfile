FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ .

# Copy frontend
COPY frontend/ /app/frontend/

# Copy data
COPY data/ /app/data/

# Create data directory if needed
RUN mkdir -p /app/data/extracted_csv /app/data/manual_cn

EXPOSE 10000

CMD ["sh", "-c", "python3 -c 'from database import init_db, import_goods_csv, seed_regulations, seed_cn_names, rebuild_name_index; init_db(); import_goods_csv(); seed_regulations(); seed_cn_names(); rebuild_name_index()' && uvicorn main:app --host 0.0.0.0 --port 10000"]
