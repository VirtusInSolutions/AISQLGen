
###########################################################################################################################################################################################
# MACHINE LEARNING, CALC LIBRARIES
import pandas as pd
import uuid, re, json, psycopg2, chardet
import numpy as np
import chardet  

#DJANGO LIBRARIES
from django.db import connection
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, Http404

#REST LIBRARIES
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView

#TREE LIBRARIES
from .models import UploadLog, DynamicTable
from .serializers import UploadLogSerializer, ReportSerializer

#AI LIBRARIES
from langchain.llms import HuggingFaceHub
from io import StringIO, BytesIO 
###################################################################################################################################################################

#replaces non-alphanumeric characters in a filename with underscores
def sanitize_filename(filename):
    base_name = re.sub(r'[^a-zA-Z0-9]', '_', filename.rsplit('.', 1)[0])
    return base_name

#creates a unique table name by combining a sanitized filename, a timestamp, and a short, unique ID
def generate_unique_table_name(filename):
    sanitized_name = sanitize_filename(filename)
    timestamp = now().strftime("%d-%m-%Y")
    unique_id = str(uuid.uuid4())[:8]
    return f"All_{timestamp}_{unique_id}"


#creates a dynamic PostgreSQL table based on a Pandas DataFrame, inferring data types and storing a sample of the data in a Django model.
def dynamic_table(table_name, df):
    with connection.cursor() as cursor:
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')

        columns_def = []
        for col, dtype in df.dtypes.items():
            if pd.api.types.is_datetime64_any_dtype(dtype):
                postgres_type = "DATE"
            elif pd.api.types.is_numeric_dtype(dtype):
                postgres_type = "DECIMAL"
            else:
                postgres_type = "TEXT"
            columns_def.append(f'"{col}" {postgres_type}')

        sql = f'CREATE TABLE "{table_name}" (id SERIAL PRIMARY KEY, {", ".join(columns_def)});'
        cursor.execute(sql)

        if not df.empty:
            try:
                sample_data = df.head().to_dict(orient='records')

                for row in sample_data:
                    for key, value in row.items():
                        if isinstance(value, (pd.Timestamp, np.datetime64)):
                            row[key] = pd.to_datetime(value).date().isoformat()
                        elif pd.isna(value):
                            row[key] = None
                        elif isinstance(value, (pd.Timedelta, pd.Interval, pd.Period)):
                            row[key] = str(value)
                        elif isinstance(value, np.ndarray):
                            row[key] = value.tolist() if value.size > 0 else None
                        else:
                            try:
                                json.dumps(value)
                            except TypeError:
                                row[key] = str(value)

                DynamicTable.objects.create(table_name=table_name, data=sample_data)
            except Exception as e:
                pass
        else:
            DynamicTable.objects.create(table_name=table_name, data={})

#This function attempts to convert non-object (string) columns in a Pandas DataFrame to numeric types, handling conversion errors by coercing them to NaN
def auto_convert_numeric_columns(df):
    for col in df.columns:
        try:
            if df[col].dtype != 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce')
        except ValueError:
            continue
    return df

#Creates a new report record using the provided data, validating it with a ReportSerializer and returning a success or error response
class ReportCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


#Handles file uploads (CSV and XLSX), processes the data, creates a dynamic database table, and logs the upload.
class FileUploadView(APIView):
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        title = request.data.get('title')
        description = request.data.get('description')
        encoding = request.data.get('encoding', None) 

        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_content = file.read()

            if encoding:
                try:
                    decoded_content = file_content.decode(encoding)
                except UnicodeDecodeError:
                    return Response({"error": f"Unable to decode file with encoding: {encoding}"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                try:
                    decoded_content = file_content.decode('utf-8')
                except UnicodeDecodeError:
                    result = chardet.detect(file_content)
                    encoding = result['encoding']
                    if encoding:
                        try:
                            decoded_content = file_content.decode(encoding)
                        except UnicodeDecodeError:
                            return Response({"error": "Unable to decode file with detected encoding."},
                                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({"error": "Unable to detect file encoding."},
                                        status=status.HTTP_400_BAD_REQUEST)

            try:
                if file.name.endswith('.csv'):
                    df = pd.read_csv(StringIO(decoded_content), keep_default_na=True, na_values=['', 'NULL', 'NaN'], parse_dates=True, dayfirst=True)
                elif file.name.endswith('.xlsx'):
                    df = pd.read_excel(BytesIO(file_content), keep_default_na=True, na_values=['', 'NULL', 'NaN'], parse_dates=True)
                else:
                    return Response({"error": "Invalid file type"}, status=status.HTTP_400_BAD_REQUEST)

                df = df.loc[:, ~df.columns.str.contains('^Unnamed', case=False, na=False)]

                if df.columns[0].startswith("Unnamed"):
                    df.columns = df.iloc[0]
                    df = df[1:]
                    df = df.reset_index(drop=True)

                df.columns = [col.lower().replace(" ", "_").strip() if isinstance(col, str) else f"col_{i}" for i, col in enumerate(df.columns)]
                df = auto_convert_numeric_columns(df)
                table_name = generate_unique_table_name(file.name)

                try:
                    dynamic_table(table_name, df)
                except Exception as dynamic_table_error:
                    print(f"Error in dynamic_table: {dynamic_table_error}")
                    return Response({"error": f"Error processing data: {dynamic_table_error}"},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                with connection.cursor() as cursor:
                    for _, row in df.iterrows():
                        values = [None if pd.isna(val) or val == "NaT" else val for val in row]
                        sql = f"""
                            INSERT INTO "{table_name}" ({", ".join(f'"{col}"' for col in df.columns)}) 
                            VALUES ({", ".join(["%s"] * len(df.columns))})
                        """
                        cursor.execute(sql, values)

                existing_upload = UploadLog.objects.filter(file_name=file.name, table_name=table_name).order_by(
                    '-version').first()
                version = 1
                if existing_upload:
                    version = existing_upload.version + 1

                UploadLog.objects.create(
                    report_id=uuid.uuid4(),
                    file_name=file.name,
                    table_name=table_name,
                    upload_timestamp=now(),
                    num_columns=len(df.columns),
                    num_rows=len(df),
                    version=version,
                    title=title,
                    description=description,
                )

                return Response({"message": "File uploaded and data inserted successfully"},
                                status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": f"Error processing file data: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"Error handling file upload: {e}"}, status=status.HTTP_400_BAD_REQUEST)

#Provides a list of UploadLog records, optionally filtered by filename and ordered by upload timestamp
class UploadLogView(ListAPIView):
    queryset = UploadLog.objects.all()
    serializer_class = UploadLogSerializer

    def get_queryset(self):
        filename = self.request.query_params.get('filename', None)
        if filename:
            return UploadLog.objects.filter(file_name=filename).order_by('-upload_timestamp')
        return UploadLog.objects.all()

# view provides detailed information about a single UploadLog record, allowing retrieval, updating, and deletion of the record based on its id
class ReportDetailView(RetrieveUpdateDestroyAPIView):
    queryset = UploadLog.objects.all()
    serializer_class = UploadLogSerializer
    lookup_field = 'id'


#retrieves and downloads a file associated with a given report_id
def get_file(request, report_id):
    try:
        report_id_uuid = uuid.UUID(str(report_id))
        upload_log = UploadLog.objects.get(report_id=report_id_uuid)
        table_name = upload_log.table_name

        dynamic_table = DynamicTable.objects.get(table_name=table_name)
        data = dynamic_table.data
        df = pd.DataFrame(data)

        if upload_log.file_name.endswith('.csv'):
            output = BytesIO()
            df.to_csv(output, index=False)
            content_type = 'text/csv'
        elif upload_log.file_name.endswith('.xlsx'):
            output = BytesIO()
            df.to_excel(output, index=False)
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            raise Http404("Unsupported file type.")

        output.seek(0)
        response = HttpResponse(output, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{upload_log.file_name}"'
        return response

    except UploadLog.DoesNotExist:
        raise Http404("Report not found.")
    except DynamicTable.DoesNotExist:
        raise Http404("Table data not found.")
    except ValueError:
        raise Http404("Invalid UUID.")
    except Exception as e:
        raise Http404(f"An error occurred: {e}")
###############################################################################################################################

#AI QUERY portion

model_id = "mistralai/Mistral-7B-Instruct-v0.2"
huggingface_token = "The Token"

llm = HuggingFaceHub(
    repo_id=model_id,
    model_kwargs={"temperature": 0.1, "max_length": 512},
    huggingfacehub_api_token=huggingface_token,
)

def execute_sql_query(sql_query):
    try:
        conn = psycopg2.connect(
            dbname="generator_db",
            user="postgres",
            password="Lazaruspit123",
            host="localhost",
            port="5432"
        )
        cursor = conn.cursor()
        cursor.execute(sql_query)
        columns = [desc[0] for desc in cursor.description]
        result = cursor.fetchall()
        conn.commit()
        cursor.close()
        conn.close()
        return columns, result
    except psycopg2.Error as e:
        print(f"Database Error: {e}")
        return [], []
    except Exception as e:
        print(f"General Error: {e}")
        return [], []

@csrf_exempt
def process_query(request, table_name):
    try:
        dynamic_table = get_object_or_404(DynamicTable, table_name=table_name)
        user_query = request.POST.get('query', '')

        if not user_query:
            return JsonResponse({"error": "Query not provided"}, status=400)

        df = pd.DataFrame(dynamic_table.data)
        column_names = ", ".join(df.columns)

        input_text = f"Generate a SQL query to answer the following question: {user_query}. Use only the columns provided. Do not use any other tables or columns. The table name is {dynamic_table.table_name} and the available columns are: {column_names}. Return ONLY valid SQL. Do not include any explanations or surrounding text."

        generated_sql = llm(input_text).strip()

        print(f"Generated SQL (before regex): {generated_sql}")

        sql_match = re.search(r"(?:```sql\s*)?(SELECT\s+.*\s+FROM\s+.*(?:\s+WHERE\s+.*)?)\s*;", generated_sql, re.DOTALL | re.IGNORECASE)

        if sql_match:
            generated_sql = sql_match.group(1).strip()
            print(f"Extracted SQL: {generated_sql}")
        else:
            print("Regex failed to match.")
            return JsonResponse({"error": f"Could not extract SQL from generated text: {generated_sql}"}, status=400)

        quoted_table_name = f'"{table_name}"'
        generated_sql = generated_sql.replace(f'FROM {table_name}', f'FROM {quoted_table_name}')

        columns, result = execute_sql_query(generated_sql)

        print(f"Database result: {result}")

        if columns and result:
            formatted_result = [dict(zip(columns, row)) for row in result]
        else:
            formatted_result = []

        return JsonResponse({
            "query": user_query,
            "generated_sql": generated_sql,
            "result": formatted_result
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
