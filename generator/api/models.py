from django.db import models
import uuid

#############################################################################################################################################
# model is used to store metadata about dynamically created tables in your PostgreSQL database
class DynamicTable(models.Model):
    table_name = models.CharField(max_length=255, unique=True)
    data = models.JSONField()  # Store dynamic table structure, makes schema flexible

    def __str__(self):
        return self.table_name
#############################################################################################################################################
# tracks uploaded files and their corresponding dynamically created tables
class UploadLog(models.Model):
    report_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file_name = models.CharField(max_length=255)
    table_name = models.CharField(max_length=255)
    upload_timestamp = models.DateTimeField()
    num_columns = models.IntegerField()
    num_rows = models.IntegerField()
    version = models.IntegerField(default=1)
    title = models.CharField(max_length=255, blank=True, null=True)  # Added title field
    description = models.TextField(blank=True, null=True)  # Added description field

    def save(self, *args, **kwargs):  # The save method ensures versioning by checking previous uploads of the same file and incrementing the version if re-uploaded
        if not self.pk:
            existing_uploads = UploadLog.objects.filter(file_name=self.file_name)
            if existing_uploads.exists():
                latest_version = existing_uploads.order_by('-version').first().version
                self.version = latest_version + 1
            else:
                self.version = 1

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.file_name} - {self.table_name} - {self.upload_timestamp} - v{self.version} - {self.title} - {self.description}"

#############################################################################################################################################
#The model represents a report, linking it to a dynamically created table

class Report(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    table = models.ForeignKey(DynamicTable, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title