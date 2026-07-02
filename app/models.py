from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, JSON, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, index=True)
    contact_number = Column(String)
    profile_photo = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    role = Column(String, nullable=True, index=True)
    is_suspended = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)

    onboarded = Column(Boolean, default=False, index=True)
    simulations_completed = Column(Integer, default=0, nullable=False)
    simulation_paid = Column(Boolean, default=False, nullable=False)
    simulation_credits = Column(Integer, default=0, nullable=False)
    
    assessment = relationship("AssessmentResult", back_populates="user", uselist=False)
    given_ratings = relationship("CounselorRating", foreign_keys="[CounselorRating.student_id]", back_populates="student")
    received_ratings = relationship("CounselorRating", foreign_keys="[CounselorRating.counsellor_id]", back_populates="counsellor")

class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    phase_2_category = Column(String, index=True)
    personality = Column(String, index=True)
    goal_status = Column(String)
    confidence = Column(Float)
    reasoning = Column(Text)
    raw_answers = Column(JSON)
    
    # Phase 1 (Class Selection)
    selected_class = Column(String, nullable=True, index=True) # "10", "12", "Above 12"

    # Phase 3 Fields
    phase3_result = Column(String, nullable=True)
    phase3_answers = Column(JSON, nullable=True)
    phase3_analysis = Column(Text, nullable=True)

    # Phase 4 (Final Stream Assessment)
    final_answers = Column(JSON, nullable=True) # Stores raw a/b/c/d answers
    stream_scores = Column(JSON, nullable=True) # Stores {"PCM": 10, "COMM": 8...}
    recommended_stream = Column(String, nullable=True, index=True) # e.g. "Science (PCM)"
    final_analysis = Column(Text, nullable=True) # Detailed AI reasoning
    stream_pros = Column(JSON, nullable=True) # List of strings
    stream_cons = Column(JSON, nullable=True) # List of strings
    
    simulation_career = Column(String, nullable=True)
    simulation_questions = Column(JSON, nullable=True) # List of 7 generated questions
    simulation_answers = Column(JSON, nullable=True) # List of 7 user responses
    simulation_evaluation = Column(JSON, nullable=True) # {match_score, summary, strengths, improvement_areas}
    simulations_completed = Column(Integer, default=0, nullable=False)
    simulation_paid = Column(Boolean, default=False, nullable=False)
    simulation_credits = Column(Integer, default=0, nullable=False)
    
    # New Multi-Phase Assessment Columns (Grade 10 and 12 Integration)
    student_type = Column(String, default="10th", nullable=True)
    current_phase = Column(Integer, default=1, nullable=True)
    intake_turn = Column(Integer, default=1, nullable=True)
    intake_name = Column(String, nullable=True)
    intake_grade = Column(Integer, nullable=True)
    intake_stream = Column(String, nullable=True)
    telemetry_logs = Column(JSON, nullable=True)
    chat_messages = Column(JSON, nullable=True)
    chat_turn = Column(Integer, default=0, nullable=True)
    proxy_answers = Column(JSON, nullable=True)
    scenario_answers = Column(JSON, nullable=True)
    assessment_report = Column(JSON, nullable=True)
    
    user = relationship("User", back_populates="assessment")

from sqlalchemy import DateTime
from sqlalchemy.sql import func


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    sender = Column(String, index=True) # "user" or "ai"
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="messages")

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    content = Column(Text)
    rating = Column(Integer)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="feedbacks")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    subject = Column(String)
    description = Column(Text)
    status = Column(String, default="Open", index=True)
    admin_reply = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user = relationship("User", back_populates="tickets")

class CareerPath(Base):
    __tablename__ = "career_paths"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    career_title = Column(String, index=True)
    path_data = Column(JSON) # Detailed path steps
    reminders = Column(JSON) # List of reminders/milestones
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="career_paths")

# Update User model to include messages, feedback, and career paths relationships
User.messages = relationship("ChatMessage", back_populates="user", order_by="ChatMessage.timestamp")
User.feedbacks = relationship("Feedback", back_populates="user", order_by="Feedback.timestamp")
User.tickets = relationship("Ticket", back_populates="user", order_by="Ticket.timestamp")
User.career_paths = relationship("CareerPath", back_populates="user", order_by="CareerPath.created_at.desc()")

class CounsellorProfile(Base):
    __tablename__ = "counsellor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    fee = Column(Float, default=0.0)
    # Storing availability as JSON. E.g., {"Monday": ["10:00", "11:00"], "Tuesday": []}
    availability = Column(JSON, nullable=True)
    account_details = Column(JSON, nullable=True) # e.g. {"bank_name": "...", "account_num": "...", "ifsc": "...", "upi": "..."}
    certificates = Column(JSON, nullable=True) # List of file paths
    experience = Column(Text, nullable=True)
    
    # Rating Statistics
    average_rating = Column(Float, default=5.0)
    rating_count = Column(Integer, default=0)

    is_verified = Column(Boolean, default=False)
    verification_status = Column(String, default="pending", index=True) # pending, approved, rejected
    tnc_accepted = Column(Boolean, default=False)
    tnc_accepted_at = Column(DateTime, nullable=True)
    is_blocked = Column(Boolean, default=False)
    block_reason = Column(String, nullable=True)

    verification_remarks = Column(Text, nullable=True)

    fee_locked = Column(Boolean, default=False)  # True = only admin can change fee

    # Razorpay Route – Linked Account for split payments
    razorpay_account_id = Column(String, nullable=True)  # e.g. acc_XXXXXXXXXXXXX
    onboarding_status = Column(String, default="not_started")  # not_started, pending, activated

    # RazorpayX – Contact & Fund Account for UPI payouts
    razorpay_contact_id = Column(String, nullable=True)      # cont_XXXXXXXXXXXXX
    razorpay_fund_account_id = Column(String, nullable=True)  # fa_XXXXXXXXXXXXXXX

    # Founding Counsellor Badge & Commission Logic
    is_founding_counsellor = Column(Boolean, default=False)
    founding_badge_awarded_at = Column(DateTime, nullable=True)
    commission_free_until = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="counsellor_profile")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    counsellor_id = Column(Integer, ForeignKey("users.id"), index=True)
    appointment_time = Column(DateTime, index=True)
    status = Column(String, default="requested", index=True)  # requested, accepted, rejected, completed, cancelled
    payment_status = Column(String, default="pending", index=True)  # pending, paid
    meeting_link = Column(String, nullable=True, index=True)
    razorpay_order_id = Column(String, nullable=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)

    # Join tracking
    counsellor_joined = Column(Boolean, default=False, index=True)
    joined_at = Column(DateTime, nullable=True, index=True)
    student_joined = Column(Boolean, default=False, index=True)
    student_joined_at = Column(DateTime, nullable=True, index=True)
    actual_overlap_minutes = Column(Integer, default=0, index=True)

    # Cancellation tracking
    cancelled_by = Column(String, nullable=True, index=True)
    cancelled_by_role = Column(String, nullable=True, index=True)  # 'student' or 'counsellor'

    student = relationship("User", foreign_keys=[student_id], back_populates="student_appointments")
    counsellor = relationship("User", foreign_keys=[counsellor_id], back_populates="counsellor_appointments")
    rating_record = relationship("CounselorRating", back_populates="appointment", uselist=False)

class CollegeRecommendation(Base):
    __tablename__ = "college_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    career_title = Column(String, index=True)
    college_data = Column(JSON)  # AI-generated list of colleges
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="college_recommendations")

User.counsellor_profile = relationship("CounsellorProfile", back_populates="user", uselist=False)
User.student_appointments = relationship("Appointment", foreign_keys="Appointment.student_id", back_populates="student")
User.counsellor_appointments = relationship("Appointment", foreign_keys="Appointment.counsellor_id", back_populates="counsellor")
User.college_recommendations = relationship("CollegeRecommendation", back_populates="user", order_by="CollegeRecommendation.created_at.desc()")


class StudentConnection(Base):
    """LinkedIn-style connections between students sharing similar archetypes."""
    __tablename__ = "student_connections"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), index=True)
    status = Column(String, default="pending", index=True)  # pending, accepted, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requester = relationship("User", foreign_keys=[requester_id], backref="sent_connections")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_connections")

class StudentMessage(Base):
    """Messages between connected students."""
    __tablename__ = "student_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), index=True)
    content = Column(Text)
    attachment_path = Column(String, nullable=True)
    attachment_type = Column(String, nullable=True) # "image" or "file"
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False, index=True)

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_student_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_student_messages")

User.notifications = relationship("Notification", back_populates="user", order_by="Notification.created_at.desc()")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    type = Column(String, index=True)  # e.g. "fee_change", "blocked", etc.
    message = Column(Text)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")

class ModerationFlag(Base):
    __tablename__ = "moderation_flags"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    content = Column(Text)
    chat_type = Column(String)  # "ai" or "p2p"
    status = Column(String, default="pending_review", index=True)  # pending_review, dismissed, action_taken

    flag_type = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    admin_note = Column(Text, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="moderation_flags")

User.moderation_flags = relationship("ModerationFlag", back_populates="user", order_by="ModerationFlag.timestamp.desc()")


# ─── Payment & Transfer Models (Razorpay Split Payments) ───────────────────────

class Payment(Base):
    """Tracks every Razorpay payment for counseling sessions."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("appointments.id"), nullable=True, index=True)  # FK → Appointment
    razorpay_order_id = Column(String, unique=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, unique=True, index=True)
    amount = Column(Float)  # Total amount in INR
    currency = Column(String, default="INR")
    status = Column(String, default="created", index=True)  # created, captured, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    session = relationship("Appointment", backref="payment_record")
    transfers = relationship("Transfer", back_populates="payment")


class Transfer(Base):
    """Tracks each split transfer to a counselor's linked account."""
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), index=True)
    counsellor_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Float)  # Counselor's share in INR
    razorpay_transfer_id = Column(String, nullable=True, unique=True)
    status = Column(String, default="pending", index=True)  # pending, processed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    payment = relationship("Payment", back_populates="transfers")
    counsellor = relationship("User")

class CounselorRating(Base):
    __tablename__ = "counsellor_ratings"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True, index=True)
    counsellor_id = Column(Integer, ForeignKey("users.id"), index=True)
    student_id = Column(Integer, ForeignKey("users.id"), index=True)
    rating = Column(Integer, nullable=False, index=True) # 1-5
    review = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", foreign_keys=[student_id], back_populates="given_ratings")
    counsellor = relationship("User", foreign_keys=[counsellor_id], back_populates="received_ratings")
    appointment = relationship("Appointment", back_populates="rating_record")

class SimulationPayment(Base):
    __tablename__ = "simulation_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    razorpay_order_id = Column(String, nullable=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)
    amount = Column(Float, default=10.0, index=True)

    status = Column(String, default="success", nullable=True)

    career = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User")