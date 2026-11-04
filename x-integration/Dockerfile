FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json listener.mjs listener.test.mjs ./
RUN node listener.test.mjs
CMD ["node", "listener.mjs"]
