from django.urls import path
from .views import FileUploadView, UploadLogView, ReportDetailView, ReportCreateView, process_query, get_file 

urlpatterns = [
    
    path('upload/', FileUploadView.as_view(), name='file-upload'),
    path('upload/logs/', UploadLogView.as_view(), name='upload-logs'),

    path('reports/create/', ReportCreateView.as_view(), name='create-report'),
    path('reports/<uuid:report_id>/', ReportDetailView.as_view(), name='report-detail'),

    path('reports/<str:table_name>/query/', process_query, name='query_report'),
    path('upload/get_file/<uuid:report_id>/', get_file, name='get_file')
]