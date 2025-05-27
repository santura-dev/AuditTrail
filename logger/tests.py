import json
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from logger.mongo import get_mongo_collection
from logger.utils import create_log_sync, verify_log_signature
from datetime import datetime, timedelta
from unittest.mock import patch
import os
from pymongo.errors import OperationFailure
from rest_framework_simplejwt.tokens import AccessToken

class LoggerTests(TestCase):
    def setUp(self):
        # Set up Celery to run tasks synchronously during tests
        self.settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)

        # Create users (regular and admin)
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.admin = User.objects.create_user(
            username='admin', password='adminpass', is_staff=True, is_superuser=True
        )
        self.client = Client()

        # Connect to MongoDB
        self.logs_collection = get_mongo_collection('audit_logs')
        self.archive_collection = get_mongo_collection('logs_archive')

        # Clear collections
        self.logs_collection.delete_many({})
        self.archive_collection.delete_many({})

        # Debug prints
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Initial MongoDB State: {list(self.logs_collection.find())}")

    def _get_tokens(self):
        self.user_token = str(RefreshToken.for_user(self.user).access_token)
        self.admin_token = str(RefreshToken.for_user(self.admin).access_token)
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Generated User Token: {self.user_token}")
            print(f"Token Payload: {AccessToken(self.user_token).payload}")  # Use AccessToken

    # Unit Tests
    def test_verify_log_signature_valid(self):
        self._get_tokens()
        log_entry = create_log_sync(action="test_action", user_id="user123", details={"ip": "192.168.1.1"})
        is_valid = verify_log_signature(log_entry)
        self.assertTrue(is_valid, "Signature should be valid")

    def test_verify_log_signature_invalid(self):
        self._get_tokens()
        log_entry = create_log_sync(action="test_action", user_id="user123", details={"ip": "192.168.1.1"})
        log_entry["action"] = "tampered_action"
        is_valid = verify_log_signature(log_entry)
        self.assertFalse(is_valid, "Signature should be invalid")

    def test_create_log_sync(self):
        self._get_tokens()
        log_entry = create_log_sync(action="signup", user_id="user456", details={"email": "test@example.com"})
        self.assertEqual(log_entry["action"], "signup")
        self.assertEqual(log_entry["user_id"], "user456")
        self.assertEqual(log_entry["details"], {"email": "test@example.com"})
        self.assertIn("signature", log_entry)
        saved_log = self.logs_collection.find_one({"_id": log_entry["_id"]})
        self.assertIsNotNone(saved_log)

    # Integration Tests
    @patch("logger.tasks.create_log_task.delay")
    def test_create_log_endpoint(self, mock_create_log_task):
        self._get_tokens()
        data = {"action": "login", "details": {"ip": "192.168.1.1"}}
        response = self.client.post(
            reverse("log-create"),
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}',
            HTTP_X_REQUEST_ID="test-request-123",
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Create Log Response: {response.content}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json(), {"message": "Log created"})
        mock_create_log_task.assert_called_once_with(
            action="login", user_id=str(self.user.id), details={"ip": "192.168.1.1"}
        )

    def test_create_log_unauthorized(self):
        data = {"action": "login", "details": {"ip": "192.168.1.1"}}
        response = self.client.post(
            reverse("log-create"),
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_logs_filter_action(self):
        self._get_tokens()
        create_log_sync(action="login", user_id=str(self.user.id), details={"ip": "192.168.1.1"})
        create_log_sync(action="logout", user_id=str(self.user.id), details={"ip": "192.168.1.2"})
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Inserted Logs: {list(self.logs_collection.find())}")

        response = self.client.get(
            f"{reverse('log-list')}?action__contains=login",
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}',
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
        self._get_tokens()
        log_entry = create_log_sync(
            action="signup",
            user_id=str(self.user.id),
            details={"email": "user@example.com"},
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Inserted Log: {log_entry}")
            print(f"MongoDB State: {list(self.logs_collection.find())}")

        list_response = self.client.get(
            f"{reverse('log-list')}?action__contains=signup",
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}',
            HTTP_X_REQUEST_ID="test-request-456",
        )
        if os.getenv("TEST_DEBUG", "False").lower() == "true":
            print(f"Create and List Response: {list_response.content}")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_data = list_response.json()
        self.assertEqual(list_data["count"], 1)
        self.assertEqual(list_data["results"][0]["action"], "signup")
        self.assertEqual(list_data["results"][0]["details"], {"email": "user@example.com"})

    # Log Export Tests (Updated for JSON-only)
    def test_export_all_logs_with_user(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'})
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'})
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'})

        url = f"{reverse('log-export')}?format=json"
        print(f"Export URL: {url}")
        response = self.client.get(
            url,
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}'
        )
        print(f"Response status: {response.status_code}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('attachment; filename="logs_export.json"', response['Content-Disposition'])

        content = b''.join(response.streaming_content).decode('utf-8')
        data = json.loads(content)
        self.assertEqual(len(data), 3)  # All 3 logs
        actions = {log["action"] for log in data}
        self.assertEqual(actions, {"login", "logout", "signup"})

    def test_export_all_logs_with_admin(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'})
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'})
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'})

        url = f"{reverse('log-export')}?format=json"
        response = self.client.get(
            url,
            HTTP_AUTHORIZATION=f'Bearer {self.admin_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('attachment; filename="logs_export.json"', response['Content-Disposition'])

        content = b''.join(response.streaming_content).decode('utf-8')
        data = json.loads(content)
        self.assertEqual(len(data), 3)  # All 3 logs
        actions = {log["action"] for log in data}
        self.assertEqual(actions, {"login", "logout", "signup"})

    def test_export_filtered_logs(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'})
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'})
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'})

        url = f"{reverse('log-export')}?action=logout&format=json"
        response = self.client.get(
            url,
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('attachment; filename="logs_export.json"', response['Content-Disposition'])

        content = b''.join(response.streaming_content).decode('utf-8')
        data = json.loads(content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['action'], 'logout')

    def test_export_time_range(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'}, timestamp=datetime.utcnow() - timedelta(days=40))
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'}, timestamp=datetime.utcnow() - timedelta(days=10))
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'}, timestamp=datetime.utcnow())

        recent_time = (datetime.utcnow() - timedelta(days=5)).isoformat()
        future_time = (datetime.utcnow() + timedelta(days=1)).isoformat()
        url = f"{reverse('log-export')}?start_time={recent_time}&end_time={future_time}&format=json"
        response = self.client.get(
            url,
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}'
        )
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content).decode('utf-8')
        data = json.loads(content)
        self.assertEqual(len(data), 1)  # 1 recent log (signup)

    def test_export_unauthorized(self):
        url = f"{reverse('log-export')}?format=json"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)
        content = response.json()
        self.assertEqual(content['detail'], 'Authentication credentials were not provided.')

    def test_export_empty_logs(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        url = f"{reverse('log-export')}?format=json"
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content).decode('utf-8')
        data = json.loads(content)
        self.assertEqual(len(data), 0)  # Empty array

    def test_export_large_dataset(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        for i in range(1000):
            create_log_sync(action=f"action_{i}", user_id="testuser", details={'index': i})
        url = f"{reverse('log-export')}?format=json"
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.user_token}')
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content).decode('utf-8')
        data = json.loads(content)
        self.assertEqual(len(data), 1000)  # All 1000 logs

    # Archive Tests
    @patch("logger.tasks.archive_logs_task.delay")
    def test_trigger_archive_endpoint_admin(self, mock_archive_task):
        self._get_tokens()
        self.logs_collection.delete_many({})
        self.archive_collection.delete_many({})
        log1 = create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'}, timestamp=datetime.utcnow() - timedelta(days=40))
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'}, timestamp=datetime.utcnow() - timedelta(days=10))
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'}, timestamp=datetime.utcnow())

        def mock_task(days):
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            logs_to_archive = self.logs_collection.find({'timestamp': {'$lt': cutoff_date}})
            for log in logs_to_archive:
                self.archive_collection.insert_one(log)
                self.logs_collection.delete_one({'_id': log['_id']})

        mock_archive_task.side_effect = mock_task

        initial_active_logs = self.logs_collection.count_documents({})
        initial_archived_logs = self.archive_collection.count_documents({})

        response = self.client.post(
            reverse("log-archive"),
            data=json.dumps({'days': 30}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.admin_token}'
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json()['message'],
            'Archival task triggered for logs older than 30 days.'
        )

        active_logs = self.logs_collection.count_documents({})
        archived_logs = self.archive_collection.count_documents({})
        self.assertEqual(active_logs, initial_active_logs - 1)
        self.assertEqual(archived_logs, initial_archived_logs + 1)

        archived_log = self.archive_collection.find_one({'_id': log1['_id']})
        self.assertIsNotNone(archived_log)
        self.assertEqual(archived_log['action'], 'login')

    def test_trigger_archive_endpoint_non_admin(self):
        self._get_tokens()
        response = self.client.post(
            reverse("log-archive"),
            data=json.dumps({'days': 30}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.user_token}'
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()['detail'],
            'You do not have permission to perform this action.'
        )

    def test_trigger_archive_invalid_days(self):
        self._get_tokens()
        response = self.client.post(
            reverse("log-archive"),
            data=json.dumps({'days': -5}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.admin_token}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['error'],
            'Days must be a non-negative integer.'
        )

    def test_archive_logic(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        self.archive_collection.delete_many({})
        log1 = create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'}, timestamp=datetime.utcnow() - timedelta(days=40))
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'}, timestamp=datetime.utcnow() - timedelta(days=10))
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'}, timestamp=datetime.utcnow())

        initial_active_logs = self.logs_collection.count_documents({})
        initial_archived_logs = self.archive_collection.count_documents({})

        cutoff_date = datetime.utcnow() - timedelta(days=30)
        logs_to_archive = self.logs_collection.find({'timestamp': {'$lt': cutoff_date}})
        for log in logs_to_archive:
            self.archive_collection.insert_one(log)
            self.logs_collection.delete_one({'_id': log['_id']})

        active_logs = self.logs_collection.count_documents({})
        archived_logs = self.archive_collection.count_documents({})
        self.assertEqual(active_logs, initial_active_logs - 1)
        self.assertEqual(archived_logs, initial_archived_logs + 1)

        archived_log = self.archive_collection.find_one({'_id': log1['_id']})
        self.assertIsNotNone(archived_log)
        self.assertEqual(archived_log['action'], 'login')

    def test_archive_partial(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        self.archive_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'}, timestamp=datetime.utcnow() - timedelta(days=40))
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'}, timestamp=datetime.utcnow() - timedelta(days=10))
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'}, timestamp=datetime.utcnow())

        initial_active_logs = self.logs_collection.count_documents({})
        initial_archived_logs = self.archive_collection.count_documents({})

        # Simulate archival with a 5-day cutoff
        cutoff_date = datetime.utcnow() - timedelta(days=5)
        logs_to_archive = self.logs_collection.find({'timestamp': {'$lt': cutoff_date}})
        for log in logs_to_archive:
            self.archive_collection.insert_one(log)
            self.logs_collection.delete_one({'_id': log['_id']})

        active_logs = self.logs_collection.count_documents({})
        archived_logs = self.archive_collection.count_documents({})
        self.assertEqual(active_logs, initial_active_logs - 2)  # log1, log2 archived
        self.assertEqual(archived_logs, initial_archived_logs + 2)

    def test_archive_no_logs(self):
        self._get_tokens()
        self.logs_collection.delete_many({})
        self.archive_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'}, timestamp=datetime.utcnow() - timedelta(days=40))
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'}, timestamp=datetime.utcnow() - timedelta(days=10))
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'}, timestamp=datetime.utcnow())

        initial_active_logs = self.logs_collection.count_documents({})
        initial_archived_logs = self.archive_collection.count_documents({})

        # Simulate archival with a future cutoff
        cutoff_date = datetime.utcnow() + timedelta(days=1)
        logs_to_archive = self.logs_collection.find({'timestamp': {'$lt': cutoff_date}})
        for log in logs_to_archive:
            self.archive_collection.insert_one(log)
            self.logs_collection.delete_one({'_id': log['_id']})

        active_logs = self.logs_collection.count_documents({})
        archived_logs = self.archive_collection.count_documents({})
        self.assertEqual(active_logs, 0)  # All logs archived
        self.assertEqual(archived_logs, initial_active_logs + initial_archived_logs)

    @patch("logger.mongo.get_mongo_collection")
    def test_archive_mongodb_error(self, mock_get_mongo_collection):
        self._get_tokens()
        self.logs_collection.delete_many({})
        self.archive_collection.delete_many({})
        create_log_sync(action="login", user_id="testuser", details={'ip_address': '192.168.1.1'}, timestamp=datetime.utcnow() - timedelta(days=40))
        create_log_sync(action="logout", user_id="testuser", details={'ip_address': '192.168.1.2'}, timestamp=datetime.utcnow() - timedelta(days=10))
        create_log_sync(action="signup", user_id="testuser", details={'ip_address': '192.168.1.3'}, timestamp=datetime.utcnow())

        initial_active_logs = self.logs_collection.count_documents({})
        initial_archived_logs = self.archive_collection.count_documents({})

        # Mock get_mongo_collection to return the correct collections
        mock_get_mongo_collection.side_effect = lambda x: self.archive_collection if x == 'logs_archive' else self.logs_collection

        # Directly mock insert_one on self.archive_collection
        with patch.object(self.archive_collection, 'insert_one', side_effect=OperationFailure("Simulated MongoDB error")):
            with self.assertRaises(OperationFailure):
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                logs_to_archive = self.logs_collection.find({'timestamp': {'$lt': cutoff_date}})
                for log in logs_to_archive:
                    self.archive_collection.insert_one(log)  # This should raise the error
                    self.logs_collection.delete_one({'_id': log['_id']})

        # Verify no changes occurred
        active_logs = self.logs_collection.count_documents({})
        archived_logs = self.archive_collection.count_documents({})
        self.assertEqual(active_logs, initial_active_logs)
        self.assertEqual(archived_logs, initial_archived_logs)