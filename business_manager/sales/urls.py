from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.collection_dashboard, name='dashboard'),
    path('mark-paid/<int:bill_id>/', views.mark_as_paid, name='mark_as_paid'),
    path('client-summary/', views.client_outstanding_summary,name='client_summary'),
    path('client/<int:client_id>/bills/', views.client_bills, name='client_bills'),
    path('client/<int:client_id>/statement/',views.client_statement,name='client_statement'),
    path('client/<int:client_id>/statement/pdf/',views.client_statement_pdf,name='client_statement_pdf'),
    path('send-reminder/<int:bill_id>/', views.send_overdue_reminder, name ='send_reminder'),
]