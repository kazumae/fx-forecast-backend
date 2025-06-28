FROM postgres:15-alpine

# Set locale
ENV LANG ja_JP.utf8

# Copy initialization scripts if needed
# COPY ./init/*.sql /docker-entrypoint-initdb.d/

# Install additional extensions if needed
RUN apk add --no-cache \
    postgresql15-contrib