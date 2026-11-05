FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json listener.mjs listener.test.mjs demo.html high-scores.html lobby.html my-games.html game-core.mjs game-core.test.mjs x-auth.mjs x-auth.test.mjs x-auth-concurrency.test.mjs lobby-api.mjs lobby-api.test.mjs two-account-flow.test.mjs offline-persistence.test.mjs host-utils.mjs host-utils.test.mjs rate-limit.mjs rate-limit.test.mjs public-feed.mjs public-feed.test.mjs lobby-rollback.test.mjs launch-preflight.mjs launch-preflight.test.mjs ./
RUN node listener.test.mjs && node game-core.test.mjs && node x-auth.test.mjs && node x-auth-concurrency.test.mjs && node lobby-api.test.mjs && node host-utils.test.mjs && node rate-limit.test.mjs && node public-feed.test.mjs && node lobby-rollback.test.mjs && node two-account-flow.test.mjs && node offline-persistence.test.mjs && node launch-preflight.test.mjs
CMD ["node", "listener.mjs"]
