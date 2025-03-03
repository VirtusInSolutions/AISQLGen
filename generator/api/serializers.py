from rest_framework import serializers
from .models import UploadLog, Report, DynamicTable

##############################################################################################################################################################
# DynamicTable Serializer - to serialize table data
class DynamicTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicTable
        fields = ['table_name', 'data']

##############################################################################################################################################################
# UploadLog Serializer
class UploadLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadLog
        fields = '__all__' 

##############################################################################################################################################################
# Report Serializer - displaying the report along with dynamic table data
class ReportSerializer(serializers.ModelSerializer):
    table = DynamicTableSerializer() # DynamicTableSerializer to display table data / Nested serializer

    class Meta:
        model = Report
        fields = ['id', 'title', 'description', 'table', 'created_at', 'updated_at']

##############################################################################################################################################################
# For querying the AI:
class AIQuerySerializer(serializers.Serializer):
    report_id = serializers.UUIDField()
    query = serializers.CharField(max_length=1024)