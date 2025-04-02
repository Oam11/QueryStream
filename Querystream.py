import streamlit as st
import sqlite3
import pandas as pd
import os
from langchain.prompts import PromptTemplate
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_groq import ChatGroq
import re

# Function to get the schema (table names and columns) from the database
def get_database_schema(conn):
    try:
        cursor = conn.cursor()
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        cursor.execute(tables_query)
        tables = cursor.fetchall()
        
        schema = {}
        for table in tables:
            table_name = table[0]
            schema[table_name] = []
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            for column in columns:
                schema[table_name].append(column[1])
        return schema
    except Exception as e:
        st.error(f"Error fetching database schema: {str(e)}")
        return None

# Initialize Groq Mixtral model
def initialize_groq_mixtral():
    try:
        api_key = st.secrets["groq"]["api_key"]
        llm = ChatGroq(
            model="llama3-70b-8192",
            temperature=0.2,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=api_key
        )
        return llm
    except Exception as e:
        st.error(f"An error occurred while initializing Groq Mixtral model: {str(e)}")
        return None

# Sidebar options
with st.sidebar:
    st.image("https://www.onepointltd.com/wp-content/uploads/2020/03/inno2.png")
    st.title("Database Query Generator")
    choice = st.radio("Navigation", ["Upload Your Database", "Ask Questions"])

# Upload Database Section
if choice == "Upload Your Database":
    st.title("Upload Your Database")
    db_file = st.file_uploader("Upload SQLite Database", type=["db", "sqlite", "sqlite3"])

    if db_file:
        # Create a temporary directory to store the database file
        temp_dir = "tempdir"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Save the uploaded file temporarily
        db_path = os.path.join(temp_dir, db_file.name)
        with open(db_path, "wb") as f:
            f.write(db_file.getbuffer())

        # Store the path in session state so it can be accessed later
        st.session_state['db_file_path'] = db_path
        st.success("Database uploaded successfully!")

# Ask Questions Section
if choice == "Ask Questions":
    st.title("Ask Questions About Your Data")

    if 'db_file_path' in st.session_state:
        db_path = st.session_state['db_file_path']
        conn = sqlite3.connect(db_path)
        schema = get_database_schema(conn)  # Get the schema from the database
        
        if schema:
            st.write("Database Schema:")
            st.json(schema)  # Display the schema for reference

        question = st.text_input("Enter your question:")

        if st.button("Ask"):
            if question:
                llm = initialize_groq_mixtral()

                if llm:
                    try:
                        # Convert schema to a text format to give context to the LLM
                        schema_str = "\n".join([f"Table: {table}, Columns: {', '.join(columns)}" for table, columns in schema.items()])
                        
                        # Create the prompt for Groq Mixtral, including the schema
                        prompt_template = PromptTemplate(
                            input_variables=["schema", "question"],
                            template='''You are given the following database schema:

                                Given the schema:

                                {schema}

                                Write an SQL query to answer this question:

                                {question}

                                **Guidelines:**
                                1. Analyze the schema to understand table structures.
                                2. Interpret the question and generate the SQL query accordingly.
                                3. Provide only the SQL query.'''
                        )
                        
                        prompt = prompt_template.format(schema=schema_str, question=question)
                        
                        # Generate the SQL query using the LLM
                        response = llm.invoke(prompt)
                        
                        response_content = ""
                        if isinstance(response, dict) and 'content' in response:
                            response_content = response['content']
                        elif hasattr(response, 'content'):
                            response_content = response.content
                        elif hasattr(response, 'text'):
                            response_content = response.text
                        else:
                            st.error("Unexpected response format from the model.")
                            st.write("Response Type: ", type(response))
                            response_content = ""

                        if response_content:
                            # Extract SQL query using regular expressions
                            sql_match = re.search(r'```sql\n(.*?)\n```', response_content, re.DOTALL)
                            if sql_match:
                                generated_sql = sql_match.group(1).strip()
                                
                                # Ensure proper SQL syntax by handling common issues
                                if generated_sql.lower().startswith("select count(*)"):
                                    generated_sql = generated_sql.replace("COUNT()", "COUNT(*)")
                                
                                st.write("Generated SQL Query:")
                                st.code(generated_sql)  # Display the generated SQL for debugging

                                # Execute the generated SQL query
                                try:
                                    if generated_sql:
                                        df = pd.read_sql_query(generated_sql, conn)
                                        
                                        if df.empty:
                                            st.write("No data returned by the SQL query.")
                                        else:
                                            st.write("Query Results:")
                                            st.dataframe(df)
                                    else:
                                        st.error("No SQL query was generated.")
                                except Exception as e:
                                    st.error(f"Error executing SQL query: {str(e)}")
                            else:
                                st.error("No SQL query found in the response.")
                    except Exception as e:
                        st.error(f"Error generating SQL query: {str(e)}")
                    finally:
                        conn.close()  # Ensure the connection is closed after use
        
        # Add the download button for modified database
        if st.button("Download Modified Database"):
            with open(db_path, "rb") as file:
                st.download_button(
                    label="Download Database",
                    data=file,
                    file_name="modified_database.db",
                    mime="application/octet-stream"
                )
    else:
        st.warning("Please upload a database first.")
