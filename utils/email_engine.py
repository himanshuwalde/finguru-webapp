import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_financial_alert(recipient_email, subject, html_content):
    """Sends an HTML email using Gmail SMTP."""
    sender_email = os.environ.get("GMAIL_USER") 
    sender_password = os.environ.get("GMAIL_APP_PASSWORD") 

    if not sender_email or not sender_password:
        print("Email credentials missing in environment variables.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"FinGuru AI <{sender_email}>"
    msg["To"] = recipient_email

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        # Connect to Gmail's secure SMTP server
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"✅ Alert successfully sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {recipient_email}: {e}")
        return False