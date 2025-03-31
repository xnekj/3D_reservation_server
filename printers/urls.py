from django.urls import path

from .views import PrinterListView, PrinterCreateView, PrinterDeleteView, PrinterDetailView
from .views import start_print, delete_printjob, reconnect_printer

urlpatterns = [
    path('<int:pk>/delete/', PrinterDeleteView.as_view(), name='printer_delete'),
    path('add/', PrinterCreateView.as_view(), name='printer_add'),
    path('<int:pk>/', PrinterDetailView.as_view(), name='printer_detail'),
    path('<int:pk>/start_print/', start_print, name='start_print'),
    path('printjob/<int:pk>/delete/', delete_printjob, name='delete_printjob'),
    path('<int:pk>/reconnect/', reconnect_printer, name='reconnect_printer'),
    path('', PrinterListView.as_view(), name='printer_list'),
]