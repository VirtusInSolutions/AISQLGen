from django.contrib import admin
from .models import UploadLog, Report, DynamicTable

class UploadLogAdmin(admin.ModelAdmin):
    list_display = ('report_id', 'file_name', 'table_name', 'upload_timestamp', 'num_columns', 'num_rows', 'version', 'title', 'description') #added title and description
    search_fields = ('file_name', 'table_name', 'title', 'description') #added title and description

class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'table', 'created_at', 'updated_at')
    search_fields = ('title', 'description')

class DynamicTableAdmin(admin.ModelAdmin):
    list_display = ('table_name', 'data')
    search_fields = ('table_name',)

admin.site.register(UploadLog, UploadLogAdmin)
admin.site.register(Report, ReportAdmin)
admin.site.register(DynamicTable, DynamicTableAdmin)