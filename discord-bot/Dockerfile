FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY bot.py challenge_commands.py render.py dashboard_refresh.py native_hub_feeds.py /app/
CMD ["python", "-u", "bot.py"]
