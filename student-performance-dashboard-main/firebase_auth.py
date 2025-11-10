import requests
import json

class FirebaseAuth:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = "https://identitytoolkit.googleapis.com/v1"

    def signup(self, email, password):
        url = f"{self.base}/accounts:signUp?key={self.api_key}"
        return requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}).json()

    def login(self, email, password):
        url = f"{self.base}/accounts:signInWithPassword?key={self.api_key}"
        return requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}).json()

    def reset_password(self, email):
        url = f"{self.base}/accounts:sendOobCode?key={self.api_key}"
        return requests.post(url, json={"requestType": "PASSWORD_RESET", "email": email}).json()

    def send_verify_email(self, id_token):
        url = f"{self.base}/accounts:sendOobCode?key={self.api_key}"
        return requests.post(url, json={"requestType": "VERIFY_EMAIL", "idToken": id_token}).json()

    def account_info(self, id_token):
        url = f"{self.base}/accounts:lookup?key={self.api_key}"
        return requests.post(url, json={"idToken": id_token}).json()
