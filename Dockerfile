# Cloud Run 用。ローカルでは使わない（ローカルは run.command でOK）。
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false

# Cloud Run は $PORT を渡してくる（固定の8080ではない）ので、起動時に展開する
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0
