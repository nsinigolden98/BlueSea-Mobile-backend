BlueSea Mobile Backend

Overview

BlueSea Mobile Backend is a Django-based REST API service that manages user wallets, transactions, and payment processing. The system provides secure endpoints for user registration, wallet management, and payment processing through Paystack integration.

It also supports ngrok for exposing your local server to the internet, which is required for testing Paystack webhooks and other external services during development.

Features

User Authentication & Authorization

Email-based registration with OTP verification

JWT-based authentication

Role-based access control


Wallet Management

Automatic wallet creation for new users

Balance tracking and management

Transaction history


Payment Processing

Paystack integration for payment processing

Webhook handling for payment notifications

Secure payment verification


Group Payment System

Create group payments

Join existing group payments


Transaction Management

Credit and debit operations

Transaction history tracking

Payment status management



Tech Stack

Python 3.13

Django REST Framework

JWT Authentication

SQLite Database

Paystack Payment Gateway

ngrok (for webhook testing)


Project Structure

BlueSea-Mobile-backend/
├── accounts/                 # User authentication and management
├── wallet/                   # Wallet management
├── transactions/             # Payment and transaction handling
├── group_payment/            # Group payment functionality
└── bluesea_mobile/           # Project configuration

Installation

Prerequisites

Python 3.13+

pip (Python package manager)

Virtual environment (recommended)

ngrok (for webhook testing)


Setup

1. Clone the repository



git clone https://github.com/nsinigolden98/BlueSea-Mobile-backend.git
cd BlueSea-Mobile-backend

2. Create and activate virtual environment



python -m venv venv
source venv/bin/activate  # For Unix/macOS
venv\Scripts\activate     # For Windows

3. Install dependencies



pip install -r requirements.txt

4. Environment Variables
Create a .env file in the root directory with the following variables:



SECRET_KEY=your_secret_key
DEBUG=True
PAYSTACK_SECRET_KEY=your_paystack_secret_key
PAYSTACK_PUBLIC_KEY=your_paystack_public_key
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=your_email_host
EMAIL_PORT=your_email_port
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_email_password

5. Database Setup



python manage.py migrate

6. Create superuser (optional)



python manage.py createsuperuser

7. Run the server



python manage.py runserver

8. Start ngrok (for Paystack webhooks)



ngrok http 8000

This will give you a public URL (e.g., https://random-id.ngrok.app) which you should configure in Paystack as your webhook URL, e.g.:

https://random-id.ngrok.app/transactions/webhook/paystack/

API Documentation

(… same as before …)

Webhook Testing with ngrok

Start your Django server locally (python manage.py runserver)

Run ngrok http 8000 to expose it

Copy the ngrok HTTPS URL and set it as your webhook endpoint in Paystack dashboard

Example webhook endpoint:

https://<ngrok-id>.ngrok.app/transactions/webhook/paystack/


Testing

Run tests using:

python manage.py test

For webhook-related tests:

1. Keep Django server running


2. Run ngrok (ngrok http 8000)


3. Trigger a test event from Paystack dashboard



Contributing

1. Fork the repository


2. Create your feature branch


3. Commit your changes


4. Push to the branch


5. Create a Pull Request



License

This project is licensed under the MIT License - see the LICENSE file for details.

Acknowledgments

Django REST Framework

Paystack Payment Gateway

ngrok for webhook tunneling

Contributors and maintainers


Contact

Project maintained by nsinigolden98
