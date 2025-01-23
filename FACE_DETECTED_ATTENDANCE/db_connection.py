import mysql.connector
from mysql.connector import Error

def create_connection():
    """
    Establishes a connection to the MySQL database.
    Returns the connection object if successful, or raises an exception on failure.
    """
    try:
        connection = mysql.connector.connect(
            host='localhost',         
            user='shraddha',              
            password='shraddha',        
            database='face_attendance' 
        )
        if connection.is_connected():
            print("Connection to MySQL successful")
            return connection
    except Error as e:
        print(f"Error: {e}")
        raise

def close_connection(connection):
    """
    Closes the provided MySQL connection.
    """
    if connection.is_connected():
        connection.close()
        print("MySQL connection closed")
