from django.urls import path
from .views import (AnnouncementList,AnnouncementPublish,AnnouncementReadView,
  ConversationList,ConversationMessages,ConversationMarkRead,TicketList,TicketDetail,
  TicketReplyView,TicketTransition,NotificationInbox,NotificationMarkRead,StudentContacts)
urlpatterns=[
  path('students/<uuid:student_id>/contacts/',StudentContacts.as_view()),
  path('announcements/',AnnouncementList.as_view()),
  path('announcements/<uuid:notice_id>/publish/',AnnouncementPublish.as_view()),
  path('announcements/<uuid:notice_id>/read/',AnnouncementReadView.as_view()),
  path('conversations/',ConversationList.as_view()),
  path('conversations/<uuid:thread_id>/messages/',ConversationMessages.as_view()),
  path('conversations/<uuid:thread_id>/read/',ConversationMarkRead.as_view()),
  path('tickets/',TicketList.as_view()),
  path('tickets/<uuid:ticket_id>/',TicketDetail.as_view()),
  path('tickets/<uuid:ticket_id>/reply/',TicketReplyView.as_view()),
  path('tickets/<uuid:ticket_id>/transition/',TicketTransition.as_view()),
  path('notifications/',NotificationInbox.as_view()),
  path('notifications/<uuid:event_id>/read/',NotificationMarkRead.as_view()),
]
