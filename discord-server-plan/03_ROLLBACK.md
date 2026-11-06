# Rollback

Manifest records only what **this plan created or changed**.

1. Rollback deletes **only** IDs in `created_category_ids` / `created_channel_ids`.
2. Pre-existing channels/messages/roles are never deleted.
3. Overwrites restored from `before` snapshots when captured.
4. Bot token, Railway service, and `/data` volume are never modified by rollback.
