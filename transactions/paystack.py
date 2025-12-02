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
        

HEADERS = {
    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    "Content-Type": "application/json"
}

BASE_URL = "https://api.paystack.co"


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
        print(json.dumps(response.json(), indent=2))
        return None


def initiate_transfer(amount_ngn: float, recipient_code: str, reason: str = "Payout from your app"):
    url = f"{BASE_URL}/transfer"
    
    # THE PAYLOAD - No special flags for auto-approval
    payload = {
        "source": "balance",              # From your Paystack balance (or 'dedicated' for subaccounts)
        "amount": int(amount_ngn * 100),  # In kobo (e.g., 15000 NGN = 1,500,000 kobo)
        "recipient": recipient_code,      # From create_recipient()
        "reason": reason,                 # Descriptive note (shows on recipient's bank statement)
        # Optional params (add if needed):
        # "narration": "Custom message",  # Extra note for your records
        # "reference": "TXREF_123",       # Unique ID (auto-generated if omitted)
        # "currency": "NGN"               # Default for Nigeria
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code in (200, 201):
        result = response.json()
        print("Transfer initiated successfully!")
        print(f"Transfer Reference: {result['data']['reference']}")
        print(f"Status: {result['data']['status']}")  # With auto-approval: "success" | Without: "otp"
        
        # If "otp", you'd normally approve manually or via API (see below)
        if result['data']['status'] == 'otp':
            print("OTP required - Approve in dashboard or use resolve endpoint.")
            # Optional: Auto-resolve if you have the PIN (see below)
        return result
    else:
        print("Transfer failed:")
        print(json.dumps(response.json(), indent=2))
        return None



def resolve_transfer_otp(transfer_reference: str, pin: str):
    url = f"{BASE_URL}/transfer/resolve"
    
    payload = {
        "reference": transfer_reference,  # From initiate_transfer response
        "otp": pin  # Your 4-digit transfer PIN (not the SMS OTP!)
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print("Transfer approved!")
        print(f"Final Status: {result['data']['status']}")  # Should be "success"
        return result
    else:
        print("Approval failed:")
        print(json.dumps(response.json(), indent=2))
        return None

# Usage: After initiate_transfer() returns "otp"
# resolve_transfer_otp("TRF_ref_from_response", "1234")  # Your PIN
# Example Usage (with auto-approval enabled)


def resolve_account_name(account_number: str, bank_code: str):
    url = "https://api.paystack.co/bank/resolve"
    
    params = {
        "account_number": account_number,
        "bank_code": bank_code
    }
    
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["status"]:
            account_name = data["data"]["account_name"]
            print(f"✅ Verified: {account_name}")
            return {
                "success": True,
                "account_name": account_name
            }
        else:
            print("Failed:", data["message"])
            return {"success": False, "message": data["message"]}
    else:
        print("API Error:", response.json())
        return {"success": False, "message": "Network or server error"}

def get_nigerian_banks():
    response = requests.get(
        "https://api.paystack.co/bank",
        headers={"Authorization": "Bearer " + PAYSTACK_SECRET_KEY}
    )
    banks = response.json()["data"]
    return {bank["name"]: bank["code"] for bank in banks}

# Save this dictionary in your app so users can select bank name → you convert to code
print(get_nigerian_banks())


def resolve_with_nubapi(account_number: str, bank_code: str):
    url = f"https://api.nubapi.com/v1/resolve"
    params = {
        "account_number": account_number,
        "bank_code": bank_code
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "success":
            account_name = data["data"]["account_name"]
            print(f"✅ Verified: {account_name}")
            return {"success": True, "account_name": account_name}
        else:
            print("Failed:", data.get("message"))
            return {"success": False, "message": data.get("message")}
    else:
        print("API Error:", response.text)
        return {"success": False, "message": "Network error"}

# Usage
result = resolve_with_nubapi("0123456789", "057")  # Zenith Bank
print(result)
# Example usage
if __name__ == "__main__":
    account_number = "0123456789"
    bank_code = "057"  # Zenith Bank
    
    result = resolve_account_name(account_number, bank_code)
    print(result)
if __name__ == "__main__":
    account_number = "0123456789"
    bank_code = "057"  # Zenith
    account_name = "Chukwudi Okeke"
    amount_to_send_ngn = 15000.00

    recipient_code = create_recipient(account_number, bank_code, account_name)
    if recipient_code:
        transfer = initiate_transfer(amount_to_send_ngn, recipient_code, "Auto-approved payout")
        print(json.dumps(transfer, indent=2))