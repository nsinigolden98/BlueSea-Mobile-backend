import json
import requests
from django.conf import settings


def checkout(payload):
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        print("Paystack response:", data)

        response_data = response.json()
        # return response_data

        if response_data.get('status') == True:
            return True, response_data['data']['authorization_url']
        else:
            return False, "Failed to initiate payment! Please try again later"
    except Exception as e:
        print("Paystack error:", str(e))
        return False, "An error occurred while processing the payment. Please try again later."