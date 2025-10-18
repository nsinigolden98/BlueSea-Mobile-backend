from rest_framework.exceptions import APIException
from rest_framework import status


class InsufficientFundsException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Insufficient funds in wallet'
    default_code = 'insufficient_funds'
    
    def __init__(self, detail=None, user=None, required_amount=None, available_amount=None):
        if detail is None:
            if user and required_amount and available_amount:
                detail = (
                    f"Insufficient funds for {user.get_full_name() if hasattr(user, 'get_full_name') else user.email}. "
                    f"Required: ₦{required_amount}, Available: ₦{available_amount}"
                )
            else:
                detail = self.default_detail
        super().__init__(detail)


class VTUAPIException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'VTU service temporarily unavailable'
    default_code = 'vtu_api_error'
    
    def __init__(self, detail=None, vtu_response=None):
        if detail is None:
            if vtu_response:
                detail = f"VTU API Error: {vtu_response.get('message', 'Unknown error')}"
            else:
                detail = self.default_detail
        super().__init__(detail)


class GroupPaymentException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Group payment processing failed'
    default_code = 'group_payment_error'


class InvalidSplitConfiguration(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid split configuration'
    default_code = 'invalid_split_config'
    
    def __init__(self, detail=None, split_type=None):
        if detail is None:
            if split_type:
                detail = f"Invalid split configuration for split_type: {split_type}"
            else:
                detail = self.default_detail
        super().__init__(detail)


class MemberNotActiveException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Member is not active in the group'
    default_code = 'member_not_active'


class PermissionDeniedException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission to perform this action'
    default_code = 'permission_denied'
    
    def __init__(self, detail=None, required_role=None):
        if detail is None:
            if required_role:
                detail = f"Only {required_role} can perform this action"
            else:
                detail = self.default_detail
        super().__init__(detail)


class WalletException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Wallet operation failed'
    default_code = 'wallet_error'


class TransactionRollbackException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Transaction failed and has been rolled back'
    default_code = 'transaction_rollback'
    
    def __init__(self, detail=None, original_error=None):
        if detail is None:
            if original_error:
                detail = f"Transaction failed: {str(original_error)}. All changes have been reversed."
            else:
                detail = self.default_detail
        super().__init__(detail)


class ServiceUnavailableException(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Service temporarily unavailable. Please try again later.'
    default_code = 'service_unavailable'


class InvalidAmountException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid amount specified'
    default_code = 'invalid_amount'
    
    def __init__(self, detail=None, amount=None, min_amount=None, max_amount=None):
        if detail is None:
            if amount is not None:
                if min_amount and amount < min_amount:
                    detail = f"Amount ₦{amount} is below minimum ₦{min_amount}"
                elif max_amount and amount > max_amount:
                    detail = f"Amount ₦{amount} exceeds maximum ₦{max_amount}"
                else:
                    detail = f"Invalid amount: ₦{amount}"
            else:
                detail = self.default_detail
        super().__init__(detail)