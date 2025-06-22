# frontend/Dockerfile
FROM nginx:1.25-alpine

# Remove the default Nginx configuration file
RUN rm /etc/nginx/conf.d/default.conf

# COPY our custom, bundled configuration into the image
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

# Copy the static assets from the public folder into the Nginx html directory
COPY ./public/ /usr/share/nginx/html

# Expose port 80 for the Nginx server (inside the container)
EXPOSE 80