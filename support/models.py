# from django.db import models
# from accounts.utils import get_user_model

# user = get_user_model()

# class SupportTicket(models.Model):
#     user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
#     subject = models.CharField(max_length=255)
#     description = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     status = models.CharField(max_length=50, choices=[
#         ('open', 'Open'),
#         ('in_progress', 'In Progress'),
#         ('closed', 'Closed'),
#     ], default='open')
    
#     def __str__(self):
#         return f"Ticket #{self.id} - {self.subject}"