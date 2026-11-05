FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json listener.mjs listener.test.mjs demo.html high-scores.html lobby.html my-games.html game-core.mjs game-core.test.mjs x-auth.mjs x-auth.test.mjs lobby-api.mjs lobby-api.test.mjs host-utils.mjs host-utils.test.mjs rate-limit.mjs rate-limit.test.mjs discord-announce.mjs discord-announce.test.mjs ./
RUN node listener.test.mjs && node game-core.test.mjs && node x-auth.test.mjs && node lobby-api.test.mjs && node host-utils.test.mjs && node rate-limit.test.mjs && node discord-announce.test.mjs
CMD ["node", "listener.mjs"]
