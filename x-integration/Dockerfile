FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json listener.mjs listener.test.mjs demo.html high-scores.html ./
RUN node listener.test.mjs
CMD ["node", "listener.mjs"]
