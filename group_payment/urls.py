from django.urls import path
from .views import (
    CreateGroupView,
    AddGroupMemberView,
    ListMyGroupsView,
    GroupDetailsView,
    UpdateGroupView,
    JoinGroupView,
    LeaveGroupView,
    CancelGroupView,
)


urlpatterns = [
    path("create/", CreateGroupView.as_view(), name="create-group"),
    path("add-member/", AddGroupMemberView.as_view(), name="add-member"),
    path("join-group/", JoinGroupView.as_view(), name="join-group"),
    path("my-groups/", ListMyGroupsView.as_view(), name="my-groups"),
    path("<uuid:group_id>/", GroupDetailsView.as_view(), name="group-details"),
    path("<uuid:group_id>/update/", UpdateGroupView.as_view(), name="update-group"),
    path("leave/", LeaveGroupView.as_view(), name="leave-group"),
    path("cancel/", CancelGroupView.as_view(), name="cancel-group"),
]
