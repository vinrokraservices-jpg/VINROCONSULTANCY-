# M-Pesa C2B Webhook — Till 7599910

This package provides a small HTTPS-ready Flask service for receiving Safaricom
Daraja C2B confirmation/validation callbacks and storing received payments.

## Important

This is the webhook receiver. It does NOT contain your Safaricom Consumer Key,
Consumer Secret, or Passkey. Add secrets in Railway Variables instead.

Safaricom's C2B API uses a Confirmation URL and, if external validation is
enabled for the shortcode, a Validation URL. Production callback URLs must be
publicly reachable over HTTPS.

## Files

- `mpesa-webhook-server.py` — webhook application.
- `app.py` — Gunicorn import wrapper.
- `requirements.txt` — Python dependencies.
- `railway.json` — Railway deployment settings.
- `.env.example` — variables to configure.

## Railway setup

1. Create a GitHub repository and upload these files.
2. In Railway choose New Project → Deploy from GitHub Repo.
3. Select the repository.
4. Add these Variables:
   - `MPESA_SHORTCODE=7599910`
   - `WEBHOOK_API_KEY=<strong random value>`
   - `DB_PATH=/data/mpesa_payments.db`
5. Add a Railway Volume mounted at `/data`. Without a persistent volume,
   SQLite data can be lost when the service is redeployed.
6. Generate a public Railway domain.
7. Test:
   - `GET /health`
   - `GET /`
8. Your Safaricom production callback URLs will be:
   - `https://YOUR-DOMAIN/webhook/confirmation`
   - `https://YOUR-DOMAIN/webhook/validation`
9. Register the URLs through Daraja C2B URL registration for Till 7599910.
   External validation is optional; if it is not enabled, Safaricom will use
   the confirmation callback after successful payment.
10. Your ERP can read payments from:
   - `GET https://YOUR-DOMAIN/api/payments`
   - `GET https://YOUR-DOMAIN/api/payments/latest`

## ERP authentication

If `WEBHOOK_API_KEY` is set, the ERP must send:

`X-API-Key: <same value>`

Do not put Safaricom Consumer Secret or other private credentials in frontend
JavaScript.

## Safaricom credentials

The current webhook receiver does not need the Consumer Key/Secret merely to
receive callbacks. Those credentials are needed by the server when it calls
Daraja APIs such as Register URL. For production registration, use the
Safaricom/Daraja portal and the appropriate production credentials.

## Production note

Do not rely on the Flask development server. Railway is configured to use
Gunicorn. The service listens on Railway's `$PORT` environment variable.

## Next ERP connection

The `/api/payments` endpoint is intentionally simple so the ERP can poll it
every 15 seconds. The ERP should match `TransID` to an invoice/payment record
and make the operation idempotent so the same M-Pesa transaction cannot be
posted twice.
