from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
import jwt
import requests
from jwt.algorithms import RSAAlgorithm
from typing import Dict, Tuple, Optional
import logging
from accounts.models import Profile
from wallet.models import Wallet
from django.db import transaction as db_transaction

logger = logging.getLogger(__name__)


class GoogleAuth:
    
    @staticmethod
    def verify_google_token(token: str) -> Tuple[bool, Optional[Dict]]:

        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                logger.error("Invalid issuer")
                return False, "Invalid token issuer"
            
            # Extract user information
            user_data = {
                'email': idinfo.get('email'),
                'email_verified': idinfo.get('email_verified', False),
                'given_name': idinfo.get('given_name', ''),
                'family_name': idinfo.get('family_name', ''),
                'picture': idinfo.get('picture', ''),
                'sub': idinfo.get('sub'),
            }
            
            logger.info(f"Successfully verified Google token for email: {user_data['email']}")
            return True, user_data
            
        except ValueError as e:
            logger.error(f"Google token verification failed: {str(e)}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during Google authentication: {str(e)}")
            return False, "Authentication failed"


class AppleAuth:
    
    APPLE_PUBLIC_KEY_URL = "https://appleid.apple.com/auth/keys"
    APPLE_ISSUER = "https://appleid.apple.com"
    
    @staticmethod
    def get_apple_public_key(token: str) -> Optional[str]:
        """
        Fetch Apple's public keys and return the matching key for the token
        
        Args:
            token: Apple identity token
            
        Returns:
            Public key string or None
        """
        try:
            # Decode token header to get the key id (kid)
            headers = jwt.get_unverified_header(token)
            kid = headers.get('kid')
            
            # Fetch Apple's public keys
            response = requests.get(AppleAuth.APPLE_PUBLIC_KEY_URL)
            apple_keys = response.json()
            
            # Find the matching key
            for key in apple_keys.get('keys', []):
                if key.get('kid') == kid:
                    # Convert JWK to PEM format
                    public_key = RSAAlgorithm.from_jwk(key)
                    return public_key
            
            logger.error(f"No matching Apple public key found for kid: {kid}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Apple public key: {str(e)}")
            return None
    
    @staticmethod
    def verify_apple_token(token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verify Apple identity token and extract user information
        
        Args:
            token: Apple identity token from the client
            
        Returns:
            Tuple of (success: bool, user_info: dict or error_message: str)
        """
        try:
            # Get Apple's public key
            public_key = AppleAuth.get_apple_public_key(token)
            if not public_key:
                return False, "Could not retrieve Apple public key"
            
            # Verify and decode the token
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=settings.APPLE_CLIENT_ID,
                issuer=AppleAuth.APPLE_ISSUER
            )
            
            # Extract user information
            user_data = {
                'email': decoded.get('email'),
                'email_verified': decoded.get('email_verified', False),
                'sub': decoded.get('sub'),
            }
            
            logger.info(f"Successfully verified Apple token for email: {user_data['email']}")
            return True, user_data
            
        except jwt.ExpiredSignatureError:
            logger.error("Apple token has expired")
            return False, "Token has expired"
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid Apple token: {str(e)}")
            return False, "Invalid token"
        except Exception as e:
            logger.error(f"Unexpected error during Apple authentication: {str(e)}")
            return False, "Authentication failed"


def get_or_create_social_user(provider: str, user_data: Dict, extra_data: Optional[Dict] = None):
    
    email = user_data.get('email')
    
    if not email:
        raise ValueError("Email is required for social authentication")
    
    try:
        # Try to get existing user
        user = Profile.objects.get(email=email)
        logger.info(f"Existing user found for email: {email}")
        
        # Update email verification status if needed
        if not user.email_verified and user_data.get('email_verified'):
            user.email_verified = True
            user.save()
        
        return user, False
        
    except Profile.DoesNotExist:
        # Create new user
        with db_transaction.atomic():
            logger.info(f"Creating new user for email: {email}")
            
            # Extract names
            if provider == 'google':
                surname = user_data.get('family_name', '')
                other_names = user_data.get('given_name', '')
            elif provider == 'apple':
                # For Apple, names come from extra_data on first sign-in
                if extra_data:
                    name = extra_data.get('name', {})
                    surname = name.get('lastName', '')
                    other_names = name.get('firstName', '')
                else:
                    surname = ''
                    other_names = ''
            else:
                surname = ''
                other_names = ''
            
            # If no names provided, use email username
            if not other_names and not surname:
                other_names = email.split('@')[0]
            
            # Create user
            user = Profile.objects.create(
                email=email,
                surname=surname,
                other_names=other_names,
                email_verified=user_data.get('email_verified', True),
                role='user',
                is_active=True
            )
            
            # Set unusable password for social login users
            user.set_unusable_password()
            user.save()
            
            # Create wallet for the new user
            try:
                Wallet.objects.create(user=user)
                logger.info(f"Successfully created wallet for: {email}")
            except Exception as wallet_error:
                logger.error(f"Failed to create wallet for {email}: {str(wallet_error)}")
                # Don't fail user creation if wallet creation fails
                # The wallet can be created later
            
            logger.info(f"Successfully created user and wallet for: {email}")
            return user, True