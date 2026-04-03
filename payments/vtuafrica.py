import requests
import json

headers = {
    "Content-Type": "application/json"
}

def top_up2(user_data, service):
    url = f"https://vtuafrica.com.ng/portal/api-test/{service}/"
    response = requests.post(url, headers=headers, json=user_data) 
    if service == "merchant-verify":
        if response.json()["code"] == 101:
            return response.json()["description"]["Phone_Number"]
        else:
            return "Unavailable"
    
    else:
        return response.json()
        