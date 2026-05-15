import json
import logging
from typing import Dict, List
from datetime import datetime, timedelta
import base64
import urllib.parse

from .common.login_handler import LoginHandler
from .consts import *

# Logger
logger = logging.getLogger(__name__)


class CraveLoginHandler(LoginHandler):
    access_token: str = None
    refresh_token: str = None
    expiry: datetime = None
    capi_access_token: str = None

    scopes: List[str] = None
    subscriptions: List[str] = None
    packages: List[str] = None

    def __init__(self, cache_dir, session, username=None, password=None):
        super().__init__(cache_dir, session, username, password)
        if self.username is None or self.password is None:
            self._load_cache()
        else:
            self._load_cache()
            if self.username != username or self.password != password:
                self.access_token = None
                self.refresh_token = None
                self.expiry = None
                self.subscriptions = None
                self.scopes = None
                self.packages = None
                self.capi_access_token = None
                self.username = username
                self.password = password
                self._save_cache()
        self.ensure_login(False)

    # ===================================================================
    #   LOGIN
    # ===================================================================

    def login(self, username: str, password: str) -> bool:
        logger.debug('Logging in...')
        # Set username and password
        self.username = username
        self.password = password
        self.access_token = None
        self.refresh_token = None
        self.expiry = None
        self.subscriptions = None
        self.capi_access_token = None
        # Make login
        return self.ensure_login()

    def logout(self) -> None:
        logger.debug('Logging out...')
        self.username = None
        self.password = None
        self.access_token = None
        self.refresh_token = None
        self.expiry = None
        self.subscriptions = None
        self.capi_access_token = None
        self._save_cache()

    def ensure_login(self, force_refresh: bool = False) -> bool:
        # ===========================================================
        # Check credentials
        # ===========================================================
        if self.username is None or self.password is None:
            self.access_token = None
            self.refresh_token = None
            self.expiry = None
            self.subscriptions = None
            self._save_cache()
            logger.info(
                'Cannot ensure logging: No username or password provided')
            return False

        # ===========================================================
        # Skip if current token is valid
        # ===========================================================
        if not self._check_expiry() and not force_refresh:
            return True

        # ===========================================================
        # Refresh token if possible
        # ===========================================================
        logger.debug('Refreshing token...')
        response = None
        if self.refresh_token is not None:
            response = self._make_refresh_request()
            if response.status_code != 200:
                logger.debug('Refreshing token failed')
                response = None

        # ===========================================================
        # Do a username/password login if required
        # ===========================================================
        if response is None:
            logger.debug('Trying username/password login...')
            response = self._make_login_request()

        # ===========================================================
        # Handle refresh + login failure
        # ===========================================================
        if response.status_code != 200:
            logger.info('Login failed')
            # Reset attributes
            self.access_token = None
            self.refresh_token = None
            self.expiry = None
            self.subscriptions = None
            self.capi_access_token = None
            self._save_cache()
            return False

        # ===========================================================
        # Parse refresh/login response
        # ===========================================================
        try:
            response_parsed = json.loads(response.text)
            self.access_token = response_parsed['access_token']
            self.refresh_token = response_parsed['refresh_token']
            self.expiry = datetime.now() + timedelta(0,
                                                     response_parsed['expires_in'])
            # If the token has no profile_id, fetch profiles and upgrade
            # to a profile-scoped token (required by playback service)
            if not self._get_profile_id_from_token(self.access_token):
                self._upgrade_to_profile_token()
            # Get v2.1 CAPI token (CAPI doesn't accept v2.2 JWT format)
            # Also use v2.1 scope for subscription detection (v2.2 removed subscription scopes)
            self.capi_access_token = self._get_capi_token()
            # Scopes from v2.1 token (has subscription:X scopes)
            self.scopes = []
            capi_scope = self._get_scope_from_token(self.capi_access_token) if self.capi_access_token else ''
            raw_scope = capi_scope or response_parsed.get('scope', '')
            if isinstance(raw_scope, list):
                raw_scope = ' '.join(raw_scope)
            for scope in raw_scope.split(' '):
                if scope.startswith('subscription:'):
                    self.scopes = scope.replace('subscription:', '').split(',')
            # Subscriptions from scopes
            self.subscriptions = []
            for scope in self.scopes:
                if scope in SCOPE_TO_SUBSCRIPTION_NAME:
                    self.subscriptions.append(
                        SCOPE_TO_SUBSCRIPTION_NAME[scope])
            # Packages from scopes
            self.packages = []
            for subscription in self.subscriptions:
                if subscription in SUBSCRIPTION_NAME_TO_PACKAGE_NAME:
                    self.packages.append(
                        SUBSCRIPTION_NAME_TO_PACKAGE_NAME[subscription])
            self._save_cache()
            logger.debug('New token acquired. Valid until: {}'.format(
                self.expiry.strftime("%Y/%m/%d %H:%M:%S")))
            return True
        except Exception as e:
            # ===========================================================
            # Handle invalid refresh/login response
            # ===========================================================
            logger.info('Refresh/login response invalid: {} | status={} | body={}'.format(
                str(e), response.status_code, response.text[:500]))
            self.access_token = None
            self.refresh_token = None
            self.expiry = None
            self.subscriptions = None
            self.capi_access_token = None
            self._save_cache()
            return False

    # ===================================================================
    #   REQUESTS
    # ===================================================================

    def _upgrade_to_profile_token(self) -> None:
        '''Fetch profiles list and re-auth with the master profile id so the
        token includes profile scopes required by the playback service.'''
        try:
            url = 'https://account.bellmedia.ca/api/profile/v1.1'
            headers = {
                'accept-encoding': 'gzip',
                'authorization': 'Bearer ' + self.access_token,
                'connection': 'Keep-Alive',
                'content-type': 'application/json',
                'user-agent': 'okhttp/4.9.0'
            }
            response = self.session.get(url=url, headers=headers)
            if response.status_code != 200:
                logger.debug('Failed to fetch profiles ({})'.format(response.status_code))
                return
            profiles = json.loads(response.text)
            if not profiles:
                return
            master = next((p for p in profiles if p.get('master')), profiles[0])
            profile_id = master.get('id')
            if not profile_id:
                return
            logger.debug('Upgrading to profile-scoped token (profile_id={})'.format(profile_id))
            login_url = 'https://account.bellmedia.ca/api/login/v2.2?grant_type=refresh_token'
            login_headers = {
                'accept-encoding': 'gzip',
                'authorization': 'Basic {}'.format(self._get_authorization()),
                'connection': 'Keep-Alive',
                'content-type': 'application/x-www-form-urlencoded',
                'user-agent': 'okhttp/4.9.0'
            }
            data = 'refresh_token={}&profile_id={}&profile_pin='.format(
                urllib.parse.quote(self.refresh_token, safe=''), profile_id)
            r = self.session.post(url=login_url, headers=login_headers, data=data)
            if r.status_code != 200:
                logger.debug('Profile token exchange failed ({})'.format(r.status_code))
                return
            parsed = json.loads(r.text)
            self.access_token = parsed['access_token']
            self.refresh_token = parsed['refresh_token']
            self.expiry = datetime.now() + timedelta(0, parsed['expires_in'])
        except Exception as e:
            logger.debug('Profile upgrade exception: {}'.format(e))

    def _make_refresh_request(self):
        logger.debug('Making a refresh request...')
        url = 'https://account.bellmedia.ca/api/login/v2.2?grant_type=refresh_token'
        headers = {
            'accept-encoding': 'gzip',
            'authorization': 'Basic {}'.format(self._get_authorization()),
            'connection': 'Keep-Alive',
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'okhttp/4.9.0'
        }
        profile_id = self._get_profile_id_from_token(self.refresh_token)
        data = 'refresh_token={}&profile_id={}&profile_pin='.format(
            urllib.parse.quote(self.refresh_token, safe=''), profile_id)
        return self.session.post(url=url, headers=headers, data=data)

    def _make_login_request(self):
        logger.debug('Logging in with username and password...')
        url = 'https://account.bellmedia.ca/api/login/v2.2?grant_type=password'
        headers = {
            'accept-encoding': 'gzip',
            'authorization': 'Basic {}'.format(self._get_authorization()),
            'connection': 'Keep-Alive',
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'okhttp/4.9.0'
        }
        password = self.password.replace('&', '%26').replace('?', '%3F')
        data = 'password={}&username={}'.format(password, self.username)
        return self.session.post(url=url, headers=headers, data=data)

    def _get_profile_id_from_token(self, token: str) -> str:
        try:
            parts = token.split('.')
            if len(parts) >= 2:
                b64 = parts[1]
                b64 += '=' * (4 - len(b64) % 4)
                payload = json.loads(base64.b64decode(b64))
                return payload.get('context', {}).get('profile_id', '')
        except Exception:
            pass
        return ''

    def _get_brand_ids_from_token(self, token: str) -> list:
        try:
            parts = token.split('.')
            if len(parts) >= 2:
                b64 = parts[1]
                b64 += '=' * (4 - len(b64) % 4)
                payload = json.loads(base64.b64decode(b64))
                return payload.get('context', {}).get('brand_ids', []) or []
        except Exception:
            pass
        return []

    def _get_scope_from_token(self, token: str) -> str:
        try:
            parts = token.split('.')
            if len(parts) >= 2:
                b64 = parts[1]
                b64 += '=' * (4 - len(b64) % 4)
                payload = json.loads(base64.b64decode(b64))
                scope = payload.get('scope', '')
                if isinstance(scope, list):
                    return ' '.join(scope)
                return scope
        except Exception:
            pass
        return ''

    def _get_capi_token(self) -> str:
        try:
            url = 'https://account.bellmedia.ca/api/login/v2.1?grant_type=password'
            headers = {
                'accept-encoding': 'gzip',
                'authorization': 'Basic {}'.format(self._get_authorization()),
                'connection': 'Keep-Alive',
                'content-type': 'application/x-www-form-urlencoded',
                'user-agent': 'okhttp/4.9.0'
            }
            password = self.password.replace('&', '%26').replace('?', '%3F')
            data = 'password={}&username={}'.format(password, self.username)
            response = self.session.post(url=url, headers=headers, data=data)
            logger.debug('CAPI v2.1 token response: status={}'.format(response.status_code))
            if response.status_code == 200:
                token = json.loads(response.text).get('access_token')
                logger.debug('CAPI v2.1 token obtained successfully')
                return token
            else:
                logger.debug('CAPI v2.1 token failed: {}'.format(response.text[:200]))
        except Exception as e:
            logger.debug('CAPI v2.1 token exception: {}'.format(str(e)))
        logger.debug('Falling back to v2.2 access_token for CAPI')
        return self.access_token

    def _get_authorization(self) -> str:
        decoded = '{}:{}'.format(CLIENT_ID, CLIENT_PASS)
        encoded = decoded.encode()
        b64 = base64.b64encode(encoded)
        return b64.decode()

    # ===================================================================
    #   TOKEN EXPIRY HANDLER
    # ===================================================================

    def _check_expiry(self) -> bool:
        # Check if credentials are provided
        if self.expiry is None or self.access_token is None or self.refresh_token is None:
            return True
        if self.expiry < datetime.now() - timedelta(0, 3600):
            return True
        return False

    # ===================================================================
    #   OVERLOADS
    # ===================================================================

    def _process_cache_obj(self, cache_obj) -> bool:
        if cache_obj is not None:
            try:
                self.username = cache_obj['username']
                self.password = cache_obj['password']
                self.access_token = cache_obj['access_token']
                self.refresh_token = cache_obj['refresh_token']
                self.subscriptions = cache_obj['subscriptions']
                self.scopes = cache_obj['scopes']
                self.packages = cache_obj['packages']
                self.capi_access_token = cache_obj.get('capi_access_token') or self.access_token
                try:
                    self.expiry = datetime.strptime(
                        cache_obj['expiry'], '%Y/%m/%d %H:%M:%S')
                except:
                    self.expiry = None
                return True
            except:
                pass
            self.username = None
            self.password = None
            self.access_token = None
            self.refresh_token = None
            self.expiry = None
            self.subscriptions = None
            self.scopes = None
            self.packages = None
            self.capi_access_token = None
            return False

    def _create_cache_obj(self) -> Dict[str, str]:
        try:
            expiry = self.expiry.strftime("%Y/%m/%d %H:%M:%S")
        except:
            expiry = None
        return {
            'username': self.username,
            'password': self.password,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expiry': expiry,
            'subscriptions': self.subscriptions,
            'scopes': self.scopes,
            'packages': self.packages,
            'capi_access_token': self.capi_access_token
        }
