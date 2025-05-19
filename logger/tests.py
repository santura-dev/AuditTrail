import json
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from logger.mongo import logs_collection
from logger.utils import create_log_sync, verify_log_signature
from datetime import datetime, timezone
from unittest.mock import patch
from bson.objectid import ObjectId
import os

class LoggerUnitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.user.save()
        self.token = str(RefreshToken.for_user(self.user).access_token)
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Generated JWT Token: {self.token}")
        self.client = Client()

    def test_verify_log_signature_valid(self):
        log_entry = create_log_sync(action="test_action", user_id="user123", details={"ip": "192.168.1.1"})
        is_valid = verify_log_signature(log_entry)
        self.assertTrue(is_valid, "Signature should be valid")

    def test_verify_log_signature_invalid(self):
        log_entry = create_log_sync(action="test_action", user_id="user123", details={"ip": "192.168.1.1"})
        log_entry["action"] = "tampered_action"
        is_valid = verify_log_signature(log_entry)
        self.assertFalse(is_valid, "Signature should be invalid")

    def test_create_log_sync(self):
        log_entry = create_log_sync(action="signup", user_id="user456", details={"email": "test@example.com"})
        self.assertEqual(log_entry["action"], "signup")
        self.assertEqual(log_entry["user_id"], "user456")
        self.assertEqual(log_entry["details"], {"email": "test@example.com"})
        self.assertIn("signature", log_entry)
        saved_log = logs_collection.find_one({"_id": log_entry["_id"]})
        self.assertIsNotNone(saved_log)

class LoggerIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.user.save()
        self.token = str(RefreshToken.for_user(self.user).access_token)
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Generated JWT Token: {self.token}")
        self.client = Client()
        logs_collection.drop()
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Initial MongoDB State: {list(logs_collection.find())}")

    @patch("logger.tasks.create_log_task.delay")
    def test_create_log_endpoint(self, mock_create_log_task):
        data = {"action": "login", "details": {"ip": "192.168.1.1"}}
        response = self.client.post(
            reverse("log-create"),
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            HTTP_X_REQUEST_ID="test-request-123",
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Create Log Response: {response.content}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json(), {"message": "Log created"})
        mock_create_log_task.assert_called_once_with(action="login", user_id=str(self.user.id), details={"ip": "192.168.1.1"})

    def test_create_log_unauthorized(self):
        data = {"action": "login", "details": {"ip": "192.168.1.1"}}
        response = self.client.post(
            reverse("log-create"),
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_logs_filter_action(self):
        log_entry = create_log_sync(action="login", user_id=str(self.user.id), details={"ip": "192.168.1.1"})
        create_log_sync(action="logout", user_id=str(self.user.id), details={"ip": "192.168.1.2"})
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Inserted Logs: {list(logs_collection.find())}")

        response = self.client.get(
            reverse("log-list"),
            {"action__contains": "login"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"List Logs Response: {response.content}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["action"], "login")
        self.assertEqual(data["results"][0]["user_id"], str(self.user.id))

    def test_list_logs_unauthorized(self):
        response = self.client.get(reverse("log-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_and_list_logs(self):
        log_entry = create_log_sync(
            action="signup",
            user_id=str(self.user.id),
            details={"email": "user@example.com"},
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Inserted Log: {log_entry}")
            print(f"MongoDB State: {list(logs_collection.find())}")

        list_response = self.client.get(
            reverse("log-list"),
            {"action__contains": "signup"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            HTTP_X_REQUEST_ID="test-request-456",
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Create and List Response: {list_response.content}")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_data = list_response.json()
        self.assertEqual(list_data["count"], 1)
        self.assertEqual(list_data["results"][0]["action"], "signup")
        self.assertEqual(list_data["results"][0]["details"], {"email": "user@example.com"})