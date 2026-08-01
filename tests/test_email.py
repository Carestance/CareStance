import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

mail_server = os.getenv("MAIL_SERVER", "smtp.zoho.com")
mail_username = os.getenv("MAIL_USERNAME")
mail_password = os.getenv("MAIL_PASSWORD")

def test_port(port):
    print(f"\n--- Testing port {port} ---")
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(mail_server, port, timeout=10)
        else:
            server = smtplib.SMTP(mail_server, port, timeout=10)
            server.starttls()
        
        server.login(mail_username, mail_password)
        print(f"SUCCESS: Login successful on port {port}!")
        server.quit()
        return True
    except Exception as e:
        print(f"FAILED on port {port}: {e}")
        return False

test_port(587)
test_port(465)
