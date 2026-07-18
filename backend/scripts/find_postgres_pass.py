import psycopg2

passwords = ["postgres", "admin", "root", "123456", "password", "postgres123", "shb", "shb123", ""]

print("Testing local PostgreSQL passwords...")
found = False

for pwd in passwords:
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password=pwd,
            host="localhost",
            port=5432
        )
        print(f"✅ SUCCESS! Connected to PostgreSQL with password: '{pwd}'")
        conn.close()
        found = True
        break
    except psycopg2.OperationalError as e:
        if "authentication failed" in str(e):
            continue
        elif "database" in str(e):
            print(f"✅ User 'postgres' and password '{pwd}' are valid, but default db doesn't exist.")
            found = True
            break
        else:
            print(f"Error for password '{pwd}': {e}")

if not found:
    print("❌ Could not connect with standard passwords.")
