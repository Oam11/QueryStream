import streamlit as st
import sqlite3
import pandas as pd
import os
from langchain_core.prompts import PromptTemplate
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
            model="llama-3.3-70b-versatile",
            temperature=0.8,
            max_tokens=None,
            timeout=None,
            max_retries=200,
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
    choice = st.radio("Navigation", ["Try Sample Databases", "Upload Your Database", "Ask Questions"])

# Try Sample Databases Section
if choice == "Try Sample Databases":
    st.title("Try Sample Databases")
    st.write("Select from our pre-loaded sample databases to test the query generator:")
    
    # Define sample databases with descriptions
    sample_databases = {
        "E-commerce Database": {
            "file": "sample_databases/ecommerce.db",
            "description": "Contains data about customers, products, orders, and categories. Perfect for testing sales analytics, inventory management, and customer behavior queries.",
            "sample_questions": [
                "What are the top 5 best-selling products?",
                "How many orders were placed in March 2024?",
                "Which customers have spent more than $1000?",
                "What is the total revenue by category?"
            ]
        },
        "Library Management": {
            "file": "sample_databases/library.db", 
            "description": "Library system with books, authors, members, and loan records. Great for testing queries about book availability, member activity, and borrowing patterns.",
            "sample_questions": [
                "Which books are currently overdue?",
                "How many books has each member borrowed?",
                "What are the most popular genres?",
                "Which authors have the most books in the library?"
            ]
        },
        "Employee Management": {
            "file": "sample_databases/employees.db",
            "description": "HR database with employees, departments, and projects. Ideal for testing organizational queries, salary analysis, and project management.",
            "sample_questions": [
                "What is the average salary by department?",
                "Which employees are working on multiple projects?",
                "How many employees were hired in 2021?",
                "What is the total budget for all active projects?"
            ]
        },
        "Music Store (Chinook)": {
            "file": "sample_databases/chinook.db",
            "description": "Classic music store database with artists, albums, tracks, customers, and sales. Perfect for testing complex queries involving music catalog and sales data.",
            "sample_questions": [
                "Which artist has sold the most albums?",
                "What are the top 10 longest tracks?",
                "Which countries have the most customers?",
                "What is the total sales by genre?"
            ]
        }
    }
    
    # Check which databases actually exist
    available_databases = {}
    for db_name, db_info in sample_databases.items():
        if os.path.exists(db_info["file"]):
            available_databases[db_name] = db_info
        else:
            st.warning(f"Database file not found: {db_info['file']}")
    
    if not available_databases:
        st.error("No sample databases are available. Please check the sample_databases folder.")
        st.stop()
    
    # Show available databases count
    st.info(f"📊 {len(available_databases)} sample databases available")    
    # Database selection
    selected_db = st.selectbox(
        "Choose a sample database:",
        options=list(available_databases.keys()),
        help="Each database contains different types of data to help you test various query scenarios"
    )
    
    if selected_db:
        db_info = available_databases[selected_db]
        
        # Display database information
        st.subheader(f"📊 {selected_db}")
        st.write(db_info["description"])
        
        # Display sample questions
        st.subheader("💡 Sample Questions to Try:")
        for i, question in enumerate(db_info["sample_questions"], 1):
            st.write(f"{i}. {question}")
        
        # Load button
        if st.button(f"Load {selected_db}", type="primary"):
            db_path = db_info["file"]
            if os.path.exists(db_path):
                st.session_state['db_file_path'] = db_path
                st.session_state['selected_sample_db'] = selected_db
                st.success(f"✅ {selected_db} loaded successfully! Go to 'Ask Questions' to start querying.")
                st.balloons()
            else:
                st.error(f"Database file not found: {db_path}")

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
        
        # Show which database is currently loaded
        if 'selected_sample_db' in st.session_state:
            st.info(f"🗄️ Currently using: **{st.session_state['selected_sample_db']}**")
        else:
            st.info(f"🗄️ Currently using uploaded database: **{os.path.basename(db_path)}**")
        
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
                            template='''You are provided with a relational database schema as input.

------------------------------------------------------
SCHEMA:
{schema}
------------------------------------------------------

TASK:
Given the following natural language question:

{question}

Generate an accurate and efficient SQL query that answers the question using the database schema.

------------------------------------------------------
✅ **Detailed Guidelines:**

1. **Schema Understanding:**
   - Parse all tables, columns, data types, and keys (primary and foreign).
   - Identify relationships between tables using foreign key references.
   - Understand table purposes and how they connect logically (e.g., junction tables, lookup tables).

2. **Query Intent Analysis:**
   - Break down the question semantically to identify the **core intent** (e.g., filtering, joining, grouping, aggregation, ordering).
   - Identify **which tables and columns** are relevant to the question.
   - Determine any **conditions**, **filters**, **sorting**, **aggregations**, or **groupings** required.
   - Apply **domain knowledge** and **inference**, if needed, to resolve ambiguities in the question.

3. **SQL Logic and Construction:**
   - Use appropriate `JOIN`s when data spans multiple tables.
   - Use `WHERE` clauses for filtering based on conditions.
   - Use `GROUP BY` and `HAVING` for summarization when required.
   - Use `ORDER BY` for sorting.
   - Ensure the query selects only **necessary columns** and avoids redundancy.
   - Apply aliases where they enhance readability.
   - Format the query cleanly with proper indentation.

4. **Accuracy and Optimization:**
   - The query must return **precise results** based on question intent.
   - Prefer **concise** and **efficient** SQL (avoid unnecessary subqueries or computations).
   - Avoid SELECT * unless explicitly required.

5. **Output Format:**
   - ❗️**Output ONLY the final SQL query. No explanations, no comments, and no additional text.**
'''
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
                            response_content = str(response)

                        if response_content:
                            # First try to extract SQL from code blocks (if the model uses them)
                            sql_match = re.search(r'```sql\n(.*?)\n```', response_content, re.DOTALL)
                            if sql_match:
                                generated_sql = sql_match.group(1).strip()
                            else:
                                # If no code blocks, try to extract SQL from the response directly
                                # Look for common SQL keywords at the start
                                lines = response_content.strip().split('\n')
                                generated_sql = ""
                                
                                for line in lines:
                                    line = line.strip()
                                    if line and (line.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH', 'CREATE', 'ALTER', 'DROP'))):
                                        # Found SQL, take this line and potentially following lines
                                        sql_lines = []
                                        for remaining_line in lines[lines.index(line.strip()):]:
                                            sql_lines.append(remaining_line.strip())
                                            # Stop if we hit a semicolon at the end of a line
                                            if remaining_line.strip().endswith(';'):
                                                break
                                        generated_sql = '\n'.join(sql_lines)
                                        break
                                
                                # If still no SQL found, use the entire response content as potential SQL
                                if not generated_sql:
                                    # Clean up the response - remove extra text and try to extract SQL
                                    cleaned_response = response_content.strip()
                                    # Remove any explanatory text before SQL
                                    if ':' in cleaned_response:
                                        parts = cleaned_response.split(':', 1)
                                        if len(parts) > 1:
                                            cleaned_response = parts[1].strip()
                                    generated_sql = cleaned_response

                            # Clean up the generated SQL
                            generated_sql = generated_sql.strip()
                            
                            # Remove any remaining non-SQL text
                            if generated_sql:
                                # Remove backticks if present
                                generated_sql = generated_sql.replace('```', '').replace('sql', '').strip()
                                
                                st.write("Generated SQL Query:")
                                st.code(generated_sql)

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
                                    st.write(f"Attempted SQL: {generated_sql}")
                            else:
                                st.error("No SQL query could be extracted from the response.")
                    except Exception as e:
                        st.error(f"Error generating SQL query: {str(e)}")
                    finally:
                        conn.close()  # Ensure the connection is closed after use
        
        # Add the download button for modified database
        if st.button("Download Modified Database"):
            with open(db_path, "rb") as file:
                st.download_button(
                    label="Download Database",
                    data=file,                    file_name="modified_database.db",
                    mime="application/octet-stream"
                )
    else:
        st.warning("Please upload a database or try one of our sample databases first.")
