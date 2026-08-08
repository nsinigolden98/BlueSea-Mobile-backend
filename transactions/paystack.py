import json
import requests
from django.conf import settings


BASE_URL = "https://api.paystack.co"

HEADERS = {
    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    "Content-Type": "application/json"
}



def checkout(payload):
    url = f"{BASE_URL}/transaction/initialize"
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        # data = response.json()
        # print("Paystack response:", data)

        response_data = response.json()

        if response_data.get('status') == True:
            return True, response_data['data']['authorization_url']
        else:
            return False, "Failed to initiate payment! Please try again later"
    except Exception as e:
        # print("Paystack error:", str(e))
        return False, "An error occurred while processing the payment. Please try again later."
        


def get_nigerian_banks():
    response = requests.get(
       url= f"{BASE_URL}/bank",
        headers = HEADERS
    )
    banks = response.json()["data"]
    return {bank["name"]: bank["code"] for bank in banks}


def get_account_name(account_number: str, bank_code: str):
    url = f"{BASE_URL}/bank/resolve"
    params = {
        "account_number": account_number,
        "bank_code": bank_code
    }
    
    response = requests.get(url, params=params , headers=HEADERS)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status"):
            account_name = data["data"]["account_name"]
            return {"success": True, "account_name": account_name}
        else:
            return {"success": False, "message": data.get("message")}
    else:
        return {"success": False, "message": "Network error"}

