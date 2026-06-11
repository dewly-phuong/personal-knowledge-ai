# Payment Processing Pipeline

The Payment Processing Pipeline is a scheduled cron job that runs every hour.
It processes pending transactions and sends transaction receipts.
This pipeline depends on the Auth Service to authenticate payment requests.
It is operated by the Finance Service.
