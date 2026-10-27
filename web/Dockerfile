FROM node:20-alpine AS build

ARG ACE_BUILD_SHA=unversioned
ENV ACE_BUILD_SHA=$ACE_BUILD_SHA
ENV NEXT_PUBLIC_ACE_BUILD_SHA=$ACE_BUILD_SHA
ENV NEXT_DEPLOYMENT_ID=$ACE_BUILD_SHA

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
RUN npm prune --omit=dev


FROM node:20-alpine AS runtime

ARG ACE_BUILD_SHA=unversioned
ENV NODE_ENV=production
ENV ACE_BUILD_SHA=$ACE_BUILD_SHA
ENV NEXT_PUBLIC_ACE_BUILD_SHA=$ACE_BUILD_SHA
WORKDIR /app

LABEL org.opencontainers.image.revision=$ACE_BUILD_SHA

COPY --from=build /app/package.json /app/package-lock.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
# Public assets must remain readable by node even when a release checkout
# inherits a restrictive umask. Keep ownership and write permissions intact.
RUN chmod -R a+rX ./public

USER node

EXPOSE 3000
CMD ["./node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
