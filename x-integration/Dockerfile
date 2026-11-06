FROM node:24-bookworm-slim
WORKDIR /app
COPY discord-member-auth.mjs discord-member-auth.test.mjs lobby-member-gate.test.mjs package.json listener.mjs listener.test.mjs poll-guard.test.mjs moderation.test.mjs demo.html high-scores.html lobby.html my-games.html moderation.html game-core.mjs game-core.test.mjs x-auth.mjs x-auth.test.mjs x-auth-concurrency.test.mjs lobby-api.mjs lobby-api.test.mjs host-utils.mjs host-utils.test.mjs rate-limit.mjs rate-limit.test.mjs public-feed.mjs public-feed.test.mjs lobby-rollback.test.mjs ./
RUN npm test
CMD ["node", "listener.mjs"]
