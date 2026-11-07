FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json listener.mjs listener.test.mjs demo.html high-scores.html lobby.html game-core.mjs game-core.test.mjs x-auth.mjs x-auth.test.mjs lobby-api.mjs lobby-api.test.mjs host-utils.mjs host-utils.test.mjs ./
RUN node listener.test.mjs && node game-core.test.mjs && node x-auth.test.mjs && node lobby-api.test.mjs && node host-utils.test.mjs
CMD ["node", "listener.mjs"]
