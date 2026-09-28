# Grafana & Prometheus setup

1. Add `.env.grafana` at the project root with the following content:
    ```
    GF_SECURITY_ADMIN_USER=admin
    GF_SECURITY_ADMIN_PASSWORD=<choose-a-password>
    GF_SERVER_ROOT_URL=https://asp.local:8081/grafana/
    GF_SERVER_SERVE_FROM_SUB_PATH=true
    ```
    The `GF_SECURITY_ADMIN_PASSWORD` will be the password you can access the Grafana UI later with the `admin` account.

2. Make sure you have `127.0.0.1 asp.local` in your known hosts (should already be the case, if you followed the nginx setup correctly).

    *Note: You can check if you can reach the host by calling `ping asp.local` in the terminal.*

3. You should now be able to open the UI at `https://asp.local:8081/grafana/login`.

    *Note: Of course you first need to run the services via `docker compose up -d --build`.*

    *Note: You should see a certificate warning because your certificate is self-signed. This is expected with our current development certificate. Proceed to the site using the browser's option to accept/continue past the certificate warning.*
