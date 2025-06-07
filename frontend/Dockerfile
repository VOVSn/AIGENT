# frontend/Dockerfile
FROM nginx:1.25-alpine

# Remove the default Nginx configuration file
RUN rm /etc/nginx/conf.d/default.conf

# The nginx.conf will be provided by a volume from the root nginx/ directory
# in docker-compose.yml.

# Copy the static assets from the public folder into the Nginx html directory
COPY ./public/ /usr/share/nginx/html

# Expose port 80 for the Nginx server
EXPOSE 80