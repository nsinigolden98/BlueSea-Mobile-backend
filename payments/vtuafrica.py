import requests
import json

<<<<<<< HEAD
test_host = "https://vtuafrica.com.ng/portal/api/merchant-verify/"
a2c_host = "https://vtuafrica.com.ng/portal/api-test/airtime-cash/"

=======
>>>>>>> 93b8c5d3ecbc8631f73d0980db9834d677b948e2
headers = {
    "Content-Type": "application/json"
}

def top_up2(user_data, service):
    url = f"https://vtuafrica.com.ng/portal/api-test/{service}/"
    response = requests.post(url, headers=headers, json=user_data) 
    if service == "marchant":
        if response.json()["code"] == 101:
            return response.json()["description"]["Phone_Number"]
        else:
            return "Unavailable"
    
    else:
        return response.json()
        
        
<<<<<<< HEAD
def airtime2cash(user_data):
    response = requests.post(a2c_host, headers=headers, json=user_data) 
    return response.json()

=======
>>>>>>> 93b8c5d3ecbc8631f73d0980db9834d677b948e2
