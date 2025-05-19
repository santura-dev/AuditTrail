from locust import HttpUser, task, between
import os
from generate_token import generate_token

class AuditTrailUser(HttpUser):
    wait_time = between(1, 5)  # Wait between 1-5 seconds between tasks

    def on_start(self):
        # Generate a fresh token
        token, _ = generate_token(create_if_missing=True)
        if not token:
            raise Exception("Failed to generate JWT token")
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        if os.getenv("LOCUST_DEBUG", "False").lower() == "true":
            print(f"Using JWT Token: {self.token}")

    @task
    def create_log(self):
        payload = {
            "action": "login",
            "details": {"ip": "192.168.1.1"}
        }
        response = self.client.post("/api/logs/", json=payload, headers=self.headers)
        if os.getenv("LOCUST_DEBUG", "False").lower() == "true":
            print(f"Create Log Response: {response.status_code}, {response.text}")

    @task
    def list_logs(self):
        response = self.client.get("/api/logs/list/", headers=self.headers)
        if os.getenv("LOCUST_DEBUG", "False").lower() == "true":
            print(f"List Logs Response: {response.status_code}, {response.text}")