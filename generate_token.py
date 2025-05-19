import os
import sys
import django
from datetime import datetime, timezone
import pytz
import uuid
import string
import random
from typing import Optional, Tuple

# Set up Django environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "audittrail.settings")
django.setup()

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken
from django.core.exceptions import ObjectDoesNotExist

def generate_random_username(length: int = 8) -> str:
    """Generate a random username using letters and digits."""
    letters_and_digits = string.ascii_letters + string.digits
    return "user_" + "".join(random.choice(letters_and_digits) for _ in range(length))

def generate_token(user_id: Optional[int] = None, username: Optional[str] = None, create_if_missing: bool = False) -> Tuple[Optional[str], Optional[datetime]]:
    """
    Generate a JWT token for a specified user, creating a random user if none exist or specified user is missing.

    Args:
        user_id (int, optional): The ID of the user to generate a token for.
        username (str, optional): The username of the user to generate a token for.
        create_if_missing (bool, optional): If True, create a random user if none exist or specified user is not found.

    Returns:
        tuple: (token, expiration_datetime)
            - token: The JWT token as a string or None if failed.
            - expiration_datetime: The expiration datetime in CEST or None if failed.
    """
    try:
        # Try to retrieve the user
        user = None
        if user_id is not None:
            user = User.objects.filter(id=user_id).first()
        elif username is not None:
            user = User.objects.filter(username=username).first()

        # Create a random user if none exist or create_if_missing is True and user not found
        if not user and (create_if_missing or not User.objects.exists()):
            random_username = generate_random_username()
            default_password = os.getenv("DEFAULT_USER_PASSWORD", "randompassword123")  # Configurable via env
            user = User.objects.create_user(username=random_username, password=default_password)
            print(f"Created random user: username={random_username}, password={default_password}")

        if not user:
            raise ValueError("No user found and create_if_missing is False. Use --create-if-missing to create one.")

        # Generate the token
        token = AccessToken.for_user(user)

        # Get expiration time
        exp_timestamp = token.payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        
        # Convert UTC to CEST
        cest = pytz.timezone("Europe/Paris")  # CEST timezone
        exp_datetime_cest = exp_datetime.astimezone(cest)

        return str(token), exp_datetime_cest

    except Exception as e:
        print(f"Error generating token: {str(e)}")
        return None, None

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a JWT token for a user.")
    parser.add_argument("--user-id", type=int, help="The ID of the user to generate a token for.")
    parser.add_argument("--username", type=str, help="The username of the user to generate a token for.")
    parser.add_argument("--create-if-missing", action="store_true", help="Create a random user if none exist or specified user is not found.")
    args = parser.parse_args()

    if not args.user_id and not args.username and not args.create_if_missing:
        print("Error: Please provide either --user-id, --username, or --create-if-missing.")
        sys.exit(1)

    token, exp_datetime = generate_token(user_id=args.user_id, username=args.username, create_if_missing=args.create_if-missing)
    if token:
        print(f"Generated JWT Token: {token}")
        print(f"Expires at (CEST): {exp_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")