import requests
import json


VTPASS_SECRET_KEY="SK_9852a61f197eff92720ba13d5546290c2c324252887"
VTPASS_PUBLIC_KEY="PK_98658bf618cc8f7f32529a4c97647871e001f290a21"

BASE_URL = "https://sandbox.vtpass.com/api"
PUBLIC_KEY = VTPASS_PUBLIC_KEY
SECRET_KEY = VTPASS_SECRET_KEY

headers = {
        "X-Token": PUBLIC_KEY,
        "X-Secret": SECRET_KEY,
        "Content-Type": "application/json"
    }
def buy_airtime(**kwargs):
        response = requests.post(BASE_URL, headers=headers, data = kwargs)
        return response
        
def buy_data(**kwargs):
        response = requests.post(BASE_URL, headers=headers, data = kwargs)
        return response