from django.urls import path
from .views import CreateGroupView, AddGroupMemberView, ListMyGroupsView, GroupDetailsView


urlpatterns = [
    path('create/', CreateGroupView.as_view(), name='create-group'),
    path('add-member/', AddGroupMemberView.as_view(), name='add-member'),
    path('my-groups/', ListMyGroupsView.as_view(), name='my-groups'),
    path('<uuid:group_id>/', GroupDetailsView.as_view(), name='group-details'),
]