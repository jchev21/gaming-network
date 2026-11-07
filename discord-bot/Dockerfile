FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
# Production Hub bot + change-bridge + Member grant (#78)
COPY xyz_brand_icons.py test_xyz_brand_icons.py bot.py challenge_commands.py render.py \
     dashboard_refresh.py native_hub_feeds.py community_onboarding.py onboarding_roles.py change_commands.py \
     owner_api.py member_grant_api.py member_grant_wire.py member_grant_private_server.py /app/
COPY discord_bot_change_bridge /app/discord_bot_change_bridge
COPY tests /app/tests
COPY community-content /app/community-content
# Member route is integrated in committed bot.py but requires BOTH explicit
# owner-controlled environment flags. Never inject a permissive route at build.
RUN python - <<'PY'
from pathlib import Path
t = Path("bot.py").read_text()
private = Path("member_grant_private_server.py").read_text()
assert 'GN_MEMBER_GRANT_ROUTE_ENABLED' in private
assert 'GN_MEMBER_GRANT_ENABLED' in private
assert 'GN_MEMBER_GRANT_HMAC_SECRET' in private
assert "serve_private_member_grant" in t
assert 'attach_member_grant(app, bot, DATA_DIR)' not in t
import ast
ast.parse(t)
print("Member-grant route doubly gated in committed bot.py")
PY
# Offline unit tests (no Discord token, no live guild, no role grants)
RUN python -m unittest test_xyz_brand_icons \
 && python -m unittest tests.test_change_bridge tests.test_batch_a_commands tests.test_batch_b_publish tests.test_batches_c_h tests.test_async_apply_replay_guard tests.test_change_owner_permissions tests.test_read_only_preflight tests.test_overhaul_onboarding tests.test_community_content_pack tests.test_member_grant_api tests.test_member_grant_private_server -v \
 && python -c "import ast; ast.parse(open('bot.py').read()); print('bot.py parse ok')" \
 && python -c "import member_grant_api, member_grant_wire; print('member_grant import ok')" \
 && python -c "from pathlib import Path; t=Path('bot.py').read_text(); assert 'serve_private_member_grant' in t; assert 'attach_member_grant(app, bot, DATA_DIR)' not in t; print('private grant hook present')"
CMD ["python", "-u", "bot.py"]
