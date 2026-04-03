from rest_framework.pagination import PageNumberPagination

class WalletTransactionPagination(PageNumberPagination):
    # Default number of transactions per page
    page_size = 5
    
    # Allows client to override page size with ?page_size=X
    page_size_query_param = 'page_size' 
    
    # Maximum allowed page size
    max_page_size = 50 
