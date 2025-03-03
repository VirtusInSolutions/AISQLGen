import streamlit as st
import requests
import pandas as pd
import json
from io import BytesIO

API_BASE_URL = "http://localhost:8000/api/"

def upload_file():
    st.header("Upload File and Report Details")
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])

    report_title = st.text_input("Report Title")
    report_description = st.text_area("Report Description")

    encoding_options = ["utf-8", "latin-1", "windows-1252", None]
    selected_encoding = st.selectbox("Select Encoding (optional)", encoding_options, index=3)

    if uploaded_file is not None:
        if not report_title:
            st.error("Please enter a report title.")
            return
        if not report_description:
            st.error("Please enter a report description.")
            return

        files = {"file": uploaded_file}
        data = {"title": report_title, "description": report_description, "encoding": selected_encoding}

        response = requests.post(f"{API_BASE_URL}upload/", files=files, data=data)

        if response.status_code == 201:
            st.success("File uploaded successfully!")
        else:
            try:
                error_message = response.json().get("detail", "Unknown error")
                st.error(f"Error uploading file: {error_message}")
            except json.JSONDecodeError:
                st.error(f"Error uploading file. Status code: {response.status_code}, Response: {response.text}")

def ai_query():
    st.header("AI Query")
    response = requests.get(f"{API_BASE_URL}upload/logs/")
    if response.status_code != 200:
        st.error(f"Error fetching upload logs: {response.status_code}, {response.text}")
        return

    logs = response.json()
    if not logs:
        st.info("No upload logs found. Please upload a file first.")
        return

    df = pd.DataFrame(logs)
    report_titles = df['title'].unique().tolist()
    report_title_selected = st.selectbox("Select Report Title", report_titles)

    filtered_df = df[df['title'] == report_title_selected]
    if filtered_df.empty:
        st.error("No report found with the selected title.")
        return

    selected_report = filtered_df.iloc[0]

    st.write(f"Upload Timestamp: {selected_report['upload_timestamp']}")
    st.write(f"Description: {selected_report['description']}")

    file_url = f"{API_BASE_URL}upload/get_file/{selected_report['report_id']}/"
    file_content = requests.get(file_url).content

    try:
        if selected_report['file_name'].endswith('.csv'):
            file_df = pd.read_csv(BytesIO(file_content))
        elif selected_report['file_name'].endswith('.xlsx'):
            file_df = pd.read_excel(BytesIO(file_content))
        st.dataframe(file_df)
    except pd.errors.ParserError as e:
        st.error(f"Error parsing file: {e}. Please check the file format. Line number of error: {e.args[0].split('line ')[1].split(',')[0]}")
    except Exception as e:
        st.error(f"Error processing file: {e}")

    query = st.text_input("Enter your query")
    if st.button("Submit Query"):
        data = {"query": query}
        try:
            response = requests.post(f"{API_BASE_URL}reports/{selected_report['table_name']}/query/", data=data)
            if response.status_code == 200:
                results = response.json()
                st.write("Generated SQL:")
                st.code(results['generated_sql'], language="sql")
                st.write("Results:")
                results_df = pd.DataFrame(results['result'])
                st.dataframe(results_df)
            else:
                try:
                    error_message = response.json().get("detail", "Unknown error")
                    st.error(f"Error processing query: {error_message}")
                except json.JSONDecodeError:
                    st.error(f"Error processing query: {response.status_code}, {response.text}")

        except requests.exceptions.RequestException as e:
            st.error(f"Request error: {e}")

def main():
    st.header("AI SQL Generator")

    menu = ["Upload File", "AI Query"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Upload File":
        upload_file()
    elif choice == "AI Query":
        ai_query()

if __name__ == "__main__":
    main()