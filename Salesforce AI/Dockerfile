FROM node:24-bookworm-slim AS javascript
WORKDIR /build/frontend
COPY Frontend/package.json Frontend/package-lock.json ./
RUN npm ci
COPY Frontend/ ./
RUN npm run build
WORKDIR /build/checker
COPY tools/lwc/package.json tools/lwc/package-lock.json ./
RUN npm ci --omit=dev
COPY tools/lwc/check.cjs ./

FROM python:3.14-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 metaflow
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY --from=javascript /usr/local/bin/node /usr/local/bin/node
COPY Backend/ Backend/
COPY ["Prompt Engineering/", "Prompt Engineering/"]
COPY sfdx-project.json ./
COPY deployment/ deployment/
COPY --from=javascript /build/frontend/dist/ Frontend/dist/
COPY --from=javascript /build/checker/ tools/lwc/
RUN mkdir -p .app-data runtime force-app/main/default && chown -R metaflow:metaflow /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHON_DOTENV_DISABLED=1
USER metaflow
EXPOSE 10000
CMD ["python", "deployment/start.py", "web"]
