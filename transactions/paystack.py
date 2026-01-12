import json
import requests
from django.conf import settings


BASE_URL = "https://api.paystack.co"

HEADERS = {
    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    "Content-Type": "application/json"
}

1

def checkout(payload):
    url = f"{BASE_URL}/transaction/initialize"
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        data = response.json()
        print("Paystack response:", data)

        response_data = response.json()

        if response_data.get('status') == True:
            return True, response_data['data']['authorization_url']
        else:
            return False, "Failed to initiate payment! Please try again later"
    except Exception as e:
        print("Paystack error:", str(e))
        return False, "An error occurred while processing the payment. Please try again later."
        


def initiate_transfer(account_number: str, bank_code: str,amount_ngn: float, reference: str, account_name: str = None, reason: str = "Withdrawal By Customer"):
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

        url = f"{BASE_URL}/transfer"
    
        payload = {
        "source": "balance",        
        "amount": int(amount_ngn * 100),  
        "recipient": recipient_code,     
        "reason": reason,          
        "reference": reference,
        "currency": "NGN"               
        }
    
        response = requests.post(url, headers=HEADERS, json=payload)
    
        # if response.status_code in (200, 201):

        #     url = f"{BASE_URL}/transfer/resolve"

        #     payload = {
        #         "reference": reference,
        #         "pin": settings.PAYSTACK_PIN
        #             }

        #     response = requests.post(url, headers = HEADERS, json = payload)

        if response.status_code == 200:
            result = response.json()
            return result

            # else:
            #     return False

        else:
            return response
    else:
        
        return {"error" :"fail stsge 1", "state": True}

   


    

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

