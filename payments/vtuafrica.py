import requests
import json

test_host = "https://vtuafrica.com.ng/portal/api/merchant-verify/"
A2C_host = "https://vtuafrica.com.ng/portal/api-test/airtime-cash/"

headers = {
    "Content-Type": "application/json"
}

def test_connection(user_data):
    response = requests.post(test_host, headers=headers, json=user_data) 
    if response.json()["code"] == 101:
        return response.json()["description"]["Phone_Number"]
    else:
        return "Unavailable"
        
def airtime2cash(user_data):
    response = requests.post(A2C_host, headers=headers, json=user_data) 
    return response.json()
