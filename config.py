import urllib.parse

params = urllib.parse.quote_plus("DRIVER={ODBC Driver 17 for SQL Server};SERVER=sql.taacs;DATABASE=DEV-01;UID=balunlu;PWD=Luq#123450;Connection Timeout=60")
conn_str = 'mssql+pyodbc:///?odbc_connect={}'.format(params)