from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

ACCESS_TOKEN_EXPIRED: ErrorReason
ACCESS_TOKEN_SCOPE_INSUFFICIENT: ErrorReason
ACCESS_TOKEN_TYPE_UNSUPPORTED: ErrorReason
ACCOUNT_STATE_INVALID: ErrorReason
API_KEY_ANDROID_APP_BLOCKED: ErrorReason
API_KEY_HTTP_REFERRER_BLOCKED: ErrorReason
API_KEY_INVALID: ErrorReason
API_KEY_IOS_APP_BLOCKED: ErrorReason
API_KEY_IP_ADDRESS_BLOCKED: ErrorReason
API_KEY_SERVICE_BLOCKED: ErrorReason
BILLING_DISABLED: ErrorReason
CONSUMER_INVALID: ErrorReason
CONSUMER_SUSPENDED: ErrorReason
CREDENTIALS_MISSING: ErrorReason
DESCRIPTOR: _descriptor.FileDescriptor
ERROR_REASON_UNSPECIFIED: ErrorReason
LOCATION_TAX_POLICY_VIOLATED: ErrorReason
ORG_RESTRICTION_HEADER_INVALID: ErrorReason
ORG_RESTRICTION_VIOLATION: ErrorReason
RATE_LIMIT_EXCEEDED: ErrorReason
RESOURCE_PROJECT_INVALID: ErrorReason
RESOURCE_QUOTA_EXCEEDED: ErrorReason
RESOURCE_USAGE_RESTRICTION_VIOLATED: ErrorReason
SECURITY_POLICY_VIOLATED: ErrorReason
SERVICE_DISABLED: ErrorReason
SESSION_COOKIE_INVALID: ErrorReason
SYSTEM_PARAMETER_UNSUPPORTED: ErrorReason
USER_BLOCKED_BY_ADMIN: ErrorReason
USER_PROJECT_DENIED: ErrorReason

class ErrorReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
