import os
import asyncpg
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
dsn = os.getenv('DATABASE_URL')
print(f"DATABASE_URL: {dsn}")

# Test connection
async def test_connection():
    try:
        print("Attempting to connect...")
        conn = await asyncpg.connect(dsn=dsn)
        print("Connection successful!")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    asyncio.run(test_connection())