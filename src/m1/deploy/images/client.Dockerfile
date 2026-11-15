FROM nginx:1.30.6-alpine@sha256:901e593c95dc85f5a729f5765516321366ef4ac401821431d408897e95287d0a

COPY dist/ /usr/share/nginx/html/
USER 101:101
EXPOSE 8080
# The chart supplies the non-root configuration and same-origin API upstream.
ENTRYPOINT ["nginx", "-g", "daemon off;"]
