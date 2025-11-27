import requests

def withdraw(amount, accountNumber, ref_id, description, bankCode):
    request  =  requests.post(
    "https://sandbox.monnify.com/api/v2/disbursements/single",
    headers={
      "Authorization": "Bearer <token>",
      "Content-Type": "application/json"
    },
    json={
      "amount": amount,
      "reference": ref_id,
      "narration": description,
      "destinationBankCode": bankCode,
      "destinationAccountNumber": accountNumber,
      "currency": "NGN",
      "sourceAccountNumber": "3934178936",
      "async": True
    }
)