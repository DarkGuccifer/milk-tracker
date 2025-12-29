import psycopg2

conn = psycopg2.connect(
    dbname="postgres",
    user="postgres.bjagqrlyskreptjbikzj",
    password="kzZPFVv3uW7t5OYA",
    hostaddr="3.111.225.200",   # ← IP from nslookup
    port=5432,
    sslmode="require"
)

print("CONNECTED SUCCESSFULLY")
conn.close()
