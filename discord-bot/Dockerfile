FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
# Production Hub bot + change-bridge modules
COPY xyz_brand_icons.py test_xyz_brand_icons.py bot.py challenge_commands.py render.py \
     dashboard_refresh.py native_hub_feeds.py community_onboarding.py change_commands.py \
     owner_api.py /app/
COPY discord_bot_change_bridge /app/discord_bot_change_bridge
COPY tests /app/tests
# Offline unit tests (no Discord token, no live guild)
RUN python -m unittest test_xyz_brand_icons \
 && python -m unittest tests.test_change_bridge tests.test_batch_a_commands tests.test_batch_b_publish tests.test_batches_c_h tests.test_async_apply_replay_guard -v \
 && python -c "import ast; ast.parse(open('bot.py').read()); print('bot.py parse ok')"
CMD ["python", "-u", "bot.py"]
