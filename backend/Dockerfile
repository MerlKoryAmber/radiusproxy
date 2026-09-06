FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal. To let the container validate/reload a FreeRADIUS
# instance running in a sibling container or on the host, mount the config and
# expose the relevant command via RADIUS_CHECK_CMD / RADIUS_RELOAD_CMD.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
