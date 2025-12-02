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
        


def create_recipient(account_number: str, bank_code: str, account_name: str = None):
    url = f"{BASE_URL}/transferrecipient"
    
    payload = {
        "type": "nuban",
        "name": account_name or "Customer",
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN"
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code == 201:
        data = response.json()
        recipient_code = data['data']['recipient_code']
        print("Recipient created successfully!")
        print(f"Recipient Code: {recipient_code}")
        return recipient_code
    else:
        print("Failed to create recipient:")
        return None


def initiate_transfer(amount_ngn: float, recipient_code: str, reference: str, reason: str = "Payout from your app", ):
    url = f"{BASE_URL}/transfer"
    
    payload = {
        "source": "balance",              # From your Paystack balance (or 'dedicated' for subaccounts)
        "amount": int(amount_ngn * 100),  # In kobo (e.g., 15000 NGN = 1,500,000 kobo)
        "recipient": recipient_code,      # From create_recipient()
        "reason": reason,                 # Descriptive note (shows on recipient's bank statement)
        "reference": reference,
        "currency": "NGN"               
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code in (200, 201):
        result = response.json()
        return result
    else:
        print("Transfer failed:")
        return None

def resolve_transfer_otp(reference: str, pin = settings.PAYSTACK_PIN):

    url = f"{BASE_URL}/transfer/resolve"

    payload = {
        "reference": reference,
        "pin": pin
    }

    response = requests.post(url, headers = HEADERS, json = payload)

    if response.status_code == 200:
        result = response.json()
        return result

    else:
        return None

def get_nigerian_banks():
    response = requests.get(
       url= f"{BASE_URL}/bank",
        headers = HEADERS
    )
    banks = response.json()["data"]
    return {bank["name"]: bank["code"] for bank in banks}


def get_account_name(account_number: str, bank_code: str):
    url = "https://api.nubapi.com/v1/resolve"
    params = {
        "account_number": account_number,
        "bank_code": bank_code
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "success":
            account_name = data["data"]["account_name"]
            return {"success": True, "account_name": account_name}
        else:
            return {"success": False, "message": data.get("message")}
    else:
        return {"success": False, "message": "Network error"}

