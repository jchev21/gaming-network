GAMING NETWORK - DISCORD ACTIVITY

Batch 2 shell: single index.html + activity-sdk.js
- Selectable public feeds, layout controls, local games
- Embedded App SDK connection states (identify scope only)
- Never loads private Discord channel messages

Setup:
1. Host this folder over HTTPS.
2. Configure Discord Activity URL mappings (see ACTIVITY_URL_MAPPING.md).
3. Launch via Talk → Activity → Hub inside Discord.

Do not upload bot tokens or config.json.
Offline tests: python3 test_activity_interaction.py
