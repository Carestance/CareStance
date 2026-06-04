import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

def send_email(to_email: str, subject: str, body_html: str):
    """
    Sends a professional HTML email using SMTP settings from environment variables.
    """
    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.getenv("MAIL_PORT", 587))
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    app_name = os.getenv("APP_NAME", "NextStep")

    if not mail_username or not mail_password:
        print(f"SKIPPING EMAIL: SMTP credentials not set. Would have sent '{subject}' to {to_email}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{app_name} <{mail_username}>"
        msg["To"] = to_email

        html_part = MIMEText(body_html, "html")
        msg.attach(html_part)

        with smtplib.SMTP(mail_server, mail_port) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)
        
        print(f"EMAIL SENT: '{subject}' to {to_email}")
        return True
    except Exception as e:
        print(f"EMAIL ERROR: Failed to send email to {to_email}. Error: {e}")
        return False

def get_booking_template(user_name, other_name, appointment_time, meeting_link, role="student"):
    """
    Returns a professional HTML template for a session booking.
    """
    role_text = "counsellor" if role == "student" else "student"
    
    html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #f8fafc;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #4f46e5; margin-bottom: 8px;">Session Confirmed! 🚀</h1>
            <p style="color: #64748b; font-size: 16px;">Hello {user_name}, your career coaching session is all set.</p>
        </div>
        
        <div style="background-color: #ffffff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #1e293b; font-size: 18px; margin-top: 0; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px;">Appointment Details</h2>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
                <tr>
                    <td style="padding: 8px 0; color: #64748b; font-weight: 500;">{role_text.capitalize()}</td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: 700; text-align: right;">{other_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b; font-weight: 500;">Time</td>
                    <td style="padding: 8px 0; color: #1e293b; font-weight: 700; text-align: right;">{appointment_time}</td>
                </tr>
            </table>
            
            <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid #f1f5f9; text-align: center;">
                <p style="color: #64748b; font-size: 14px; margin-bottom: 16px;">Use the link below to join your video session:</p>
                <a href="{meeting_link}" style="display: inline-block; padding: 12px 24px; background-color: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px;">Join Video Call</a>
            </div>
        </div>
        
        <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
            &copy; 2026 CareStance. Empowering your career choices.
        </p>
    </div>
    """
    return html

def get_cancellation_template(user_name, other_name, appointment_time, role="student"):
    """
    Returns a professional HTML template for a session cancellation.
    """
    html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #fff1f2;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #e11d48; margin-bottom: 8px;">Session Cancelled ⚠️</h1>
            <p style="color: #64748b; font-size: 16px;">Hello {user_name}, the session has been removed from the schedule.</p>
        </div>
        
        <div style="background-color: #ffffff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <p style="color: #1e293b; line-height: 1.6;">
                The appointment with <strong>{other_name}</strong> which was scheduled for <strong>{appointment_time}</strong> has been cancelled.
            </p>
            
            <p style="color: #64748b; font-size: 14px; margin-top: 16px;">
                If you believe this was a mistake or need to reschedule, please visit your dashboard.
            </p>
            
            <div style="text-align: center; margin-top: 24px;">
                <a href="https://nextstep.com/dashboard" style="display: inline-block; padding: 10px 20px; border: 1px solid #e2e8f0; color: #475569; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px;">Go to Dashboard</a>
            </div>
        </div>
        
        <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
            &copy; 2026 CareStance.
        </p>
    </div>
    """
    return html

def get_reset_password_template(user_name, reset_link):
    """
    Returns a professional HTML template for password reset.
    """
    html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #f8fafc;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #4f46e5; margin-bottom: 8px;">Reset Your Password 🔒</h1>
            <p style="color: #64748b; font-size: 16px;">Hello {user_name}, we received a request to reset your password.</p>
        </div>
        
        <div style="background-color: #ffffff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <p style="color: #1e293b; line-height: 1.6; text-align: center;">
                If you didn't make this request, you can safely ignore this email. Otherwise, use the button below to set a new password. This link is valid for 1 hour.
            </p>
            
            <div style="margin-top: 24px; text-align: center;">
                <a href="{reset_link}" style="display: inline-block; padding: 12px 24px; background-color: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px;">Reset Password</a>
            </div>
        </div>
        
        <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
            &copy; 2026 CareStance. Security first.
        </p>
    </div>
    """
    return html
def get_connection_request_template(receiver_name, sender_name, profile_link):
    """
    Returns a professional HTML template for a connection request.
    """
    html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #f0f9ff;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #0ea5e9; margin-bottom: 8px;">New Connection Request! 👋</h1>
            <p style="color: #64748b; font-size: 16px;">Hello {receiver_name}, someone wants to connect with you on NextStep.</p>
        </div>
        
        <div style="background-color: #ffffff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <p style="color: #1e293b; line-height: 1.6; text-align: center;">
                <strong>{sender_name}</strong> sent you a connection request. Building a network of like-minded students can help you grow together!
            </p>
            
            <div style="margin-top: 24px; text-align: center;">
                <a href="{profile_link}" style="display: inline-block; padding: 12px 24px; background-color: #0ea5e9; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px;">View Request</a>
            </div>
        </div>
        
        <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
            &copy; 2026 CareStance. Grow your network.
        </p>
    </div>
    """
    return html

def get_profile_completion_template(user_name):
    """
    Returns a professional HTML template for profile completion reminder.
    """
    html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #f8fafc;">
        <div style="background-color: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6;">Dear {user_name or 'Sir/Madam'},</p>
            
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6;">We hope you are doing well.</p>
            
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6;">To help us provide you with the most accurate and personalized recommendations, we kindly request you to complete your profile.</p>
            
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6;">Please ensure that you fill in all the required details, including your personal information, qualifications, experience, and areas of interest. A complete profile enables us to better understand your needs and connect you with the most relevant opportunities and recommendations.</p>
            
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6; margin-bottom: 24px;">Kindly log in to your account and update your profile at your earliest convenience.</p>
            
            <div style="text-align: center; margin-bottom: 24px;">
                <a href="https://www.carestance.in/login" style="display: inline-block; padding: 12px 32px; background-color: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 16px;">Login to Your Account</a>
            </div>
            
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6;">If you need any assistance while completing your profile, feel free to reach out to us.</p>
            
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6; margin-top: 24px;">We look forward to supporting you on your journey.</p>
            
            <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #f1f5f9;">
                <p style="color: #1e293b; font-size: 16px; font-weight: 600; margin-bottom: 4px;">Best regards,</p>
                <p style="color: #4f46e5; font-size: 18px; font-weight: 800; margin-top: 0;">Team CareStance</p>
            </div>
        </div>
        
        <p style="text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px;">
            &copy; 2026 CareStance. Empowering your career choices.
        </p>
    </div>
    """
    return html
