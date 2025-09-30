import requests
import json
import uuid
from datetime import datetime

BASE_URL = "https://sandbox.vtpass.com/api/pay"

headers = {
    "api-key": "9f44fd266a39628487cc752191c29ec4",
    "secret-key": "SK_2440fa66473d148a04135f09de475323037a97d37e4",
    "public-key" : "PK_524de00d4c278ff8509968b01dc0fd355ff8d7dd7a6",
    "Content-Type": "application/json"
}


def generate_reference_id():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    
    unique_part = str(uuid.uuid4()).split('-')[0].upper()
    
    reference_id = f"{now}-{unique_part}"
    return reference_id


def top_up(user_data):
    response = requests.post(BASE_URL, headers=headers, json=user_data) 
    return response.json()

if __name__ == "__main__":
    data = {
        "request_id": generate_reference_id(),
        "serviceID": "mtn",
        "amount": 1000,
        "phone": "08011111111" 
    }
    print(top_up(data)) # Added .json() to print the response body


#PK_539615071cdf1deca97d8443d5424b78c51450365ae
#SK_740ed33540d764195239ff4f65927c5a991c19f8da0


